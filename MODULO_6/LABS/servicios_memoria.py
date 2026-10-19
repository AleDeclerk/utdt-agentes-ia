"""Dos servicios de memoria de largo plazo para ADK 2. Los dos son subclases de `BaseMemoryService`: el agente
no cambia, solo cambia lo que hay detrás de `search_memory` y `add_session_to_memory`.

  SqliteFaissMemoryService  — guarda cada turno tal cual, lo indexa con FAISS y lo persiste en SQLite (así
                              sobrevive a un proceso nuevo). Sin LLM: es determinista.
  LocalMemoryBankService    — réplica local del PATRÓN de un «memory bank»: un LLM extrae HECHOS discretos de
                              la sesión y los CONSOLIDA (si un hecho nuevo corrige a uno anterior, lo
                              reemplaza en vez de acumular dos). Alcance por `user_id`, vigencia e historial.
                              NO es el servicio administrado de Google Cloud: ver el README.

El embedding es local (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones, el mismo de `rag_pipeline.py`).
"""
import asyncio
import re
import sqlite3
from datetime import datetime, timezone

import faiss
import numpy as np
from google.adk.memory import BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

MODELO_EMB = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


class _Embedder:
    _modelo = None

    @classmethod
    def vec(cls, textos: list[str]) -> np.ndarray:
        if cls._modelo is None:
            from sentence_transformers import SentenceTransformer
            cls._modelo = SentenceTransformer(MODELO_EMB)
        return np.asarray(cls._modelo.encode(textos, normalize_embeddings=True), dtype="float32")


def texto_evento(e) -> str:
    """Texto plano de un Event de sesión ('' si no tiene)."""
    if not (e.content and e.content.parts):
        return ""
    return "\n".join(p.text for p in e.content.parts if getattr(p, "text", None)).strip()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _entrada(texto: str, autor: str | None, ts: str | None, **meta) -> MemoryEntry:
    return MemoryEntry(content=Content(role="user", parts=[Part(text=texto)]), author=autor, timestamp=ts,
                       custom_metadata=meta or None)


# ═════════════════════════════════════════════════════════════════════════════════════════════
class SqliteFaissMemoryService(BaseMemoryService):
    """Cada turno de la sesión, tal cual, con su vector. FAISS busca; SQLite persiste (texto + vector)."""

    def __init__(self, ruta_db: str, top_k: int = 3):
        self.top_k = top_k
        self.db = sqlite3.connect(ruta_db, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT, app TEXT, usuario TEXT, sesion TEXT, autor TEXT,
            texto TEXT, ts TEXT, emb BLOB, UNIQUE(app, usuario, sesion, autor, texto))""")
        self.db.commit()
        self._cargar()

    def _cargar(self) -> None:
        """Reconstruye el índice FAISS desde SQLite (lo que hace que sobreviva a un proceso nuevo)."""
        self.idx = faiss.IndexFlatIP(DIM)
        self.filas: list[tuple[str, str, str | None, str, str]] = []  # (app, usuario, autor, texto, ts)
        vecs = []
        for app, usuario, autor, texto, ts, emb in self.db.execute(
                "SELECT app, usuario, autor, texto, ts, emb FROM memoria ORDER BY id"):
            self.filas.append((app, usuario, autor, texto, ts))
            vecs.append(np.frombuffer(emb, dtype="float32"))
        if vecs:
            self.idx.add(np.vstack(vecs))

    def total(self) -> int:
        return len(self.filas)

    async def add_session_to_memory(self, session) -> None:
        nuevos = []
        for e in session.events:
            texto = texto_evento(e)
            if not texto:
                continue
            existe = self.db.execute(
                "SELECT 1 FROM memoria WHERE app=? AND usuario=? AND sesion=? AND autor IS ? AND texto=?",
                (session.app_name, session.user_id, session.id, e.author, texto)).fetchone()
            if not existe:
                nuevos.append((e.author, texto))
        if not nuevos:
            return
        vecs = _Embedder.vec([t for _, t in nuevos])
        ts = _ahora()
        for (autor, texto), v in zip(nuevos, vecs):
            self.db.execute("INSERT INTO memoria(app, usuario, sesion, autor, texto, ts, emb) VALUES (?,?,?,?,?,?,?)",
                            (session.app_name, session.user_id, session.id, autor, texto, ts, v.tobytes()))
            self.filas.append((session.app_name, session.user_id, autor, texto, ts))
        self.db.commit()
        self.idx.add(vecs)

    async def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        ok = np.array([i for i, f in enumerate(self.filas) if (f[0], f[1]) == (app_name, user_id)], dtype="int64")
        if not len(ok):
            return SearchMemoryResponse(memories=[])  # aislamiento por usuario: otro user_id no ve nada
        scores, ids = self.idx.search(_Embedder.vec([query]), min(self.top_k, len(ok)),
                                      params=faiss.SearchParameters(sel=faiss.IDSelectorBatch(ok)))
        return SearchMemoryResponse(memories=[
            _entrada(self.filas[i][3], self.filas[i][2], self.filas[i][4], score=round(float(s), 4))
            for s, i in zip(scores[0], ids[0]) if i >= 0])


# ═════════════════════════════════════════════════════════════════════════════════════════════
class _Hecho(BaseModel):
    hecho: str = Field(description="Una oración autocontenida en tercera persona")


class _Hechos(BaseModel):
    hechos: list[_Hecho] = Field(default_factory=list)


class _Decision(BaseModel):
    accion: str = Field(description="actualizar | agregar | ignorar")


PROMPT_EXTRACCION = """Sos el extractor de memoria de un asistente para oficiales de una entidad financiera.
Leé la conversación y devolvé los HECHOS DURADEROS sobre el usuario y los casos que maneja: cliente, producto,
plazos, montos, decisiones y preferencias. Reglas:
- Cada hecho es UNA oración autocontenida, en tercera persona, que nombra a la entidad o cliente
  (ejemplo: "Textil Norte S.A. evalúa una línea de capital de trabajo a 24 meses.").
- Si el usuario corrige un dato anterior, devolvé el dato corregido como hecho vigente.
- NO incluyas saludos, preguntas, ni lo que dijo el asistente salvo que confirme un dato del usuario.
- Máximo 6 hechos. Si no hay nada duradero, devolvé una lista vacía.

CONVERSACIÓN:
{conversacion}"""

PROMPT_CONSOLIDACION = """Una memoria ya guarda este HECHO EXISTENTE sobre un usuario:
  "{existente}"
Acaba de extraerse este HECHO NUEVO:
  "{nuevo}"
Decidí qué hacer:
- "actualizar": trata del MISMO asunto y el valor cambió o se corrigió (el nuevo reemplaza al existente).
- "agregar": es un dato distinto e independiente (conviven los dos).
- "ignorar": no aporta nada que el existente no diga.
Respondé solo con el JSON."""


class LocalMemoryBankService(BaseMemoryService):
    """Réplica local del patrón de Memory Bank: extracción de hechos con un LLM + consolidación + alcance por
    usuario. La extracción y la decisión de consolidar las hace el modelo; la persistencia, el alcance por
    `user_id`, los umbrales, la validación de la salida y el borrado las hace el código."""

    SIM_DUPLICADO = 0.985   # casi idéntico: no se le pregunta al modelo
    SIM_MISMO_TEMA = 0.55   # a partir de acá se considera candidato a corrección y decide el modelo
    MIN_SCORE = 0.30        # en la búsqueda: por debajo de esto no se devuelve nada (evita relleno)

    def __init__(self, ruta_db: str, chat_json, top_k: int = 3):
        """`chat_json(mensajes, modelo_pydantic, num_predict=...)` devuelve `(objeto validado | None, meta)`: es el LLM
        que extrae y consolida los hechos (ver `gemini_backend.py`)."""
        self.chat_json = chat_json
        self.top_k = top_k
        self.traza: list[dict] = []
        self.db = sqlite3.connect(ruta_db, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS hechos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, app TEXT, usuario TEXT, hecho TEXT, emb BLOB, sesion TEXT,
            creado TEXT, version INTEGER DEFAULT 1, vigente INTEGER DEFAULT 1, reemplaza INTEGER)""")
        self.db.commit()

    # ── lectura ─────────────────────────────────────────────────────────────────────────────
    def _vigentes(self, app: str, usuario: str):
        filas = self.db.execute("SELECT id, hecho, emb, creado, version FROM hechos "
                                "WHERE app=? AND usuario=? AND vigente=1 ORDER BY id", (app, usuario)).fetchall()
        embs = np.vstack([np.frombuffer(f[2], dtype="float32") for f in filas]) if filas else np.zeros((0, DIM), "float32")
        return filas, embs

    def listar(self, app: str, usuario: str, historial: bool = False) -> list[dict]:
        cond = "" if historial else "AND vigente=1"
        return [dict(id=i, hecho=h, version=v, vigente=bool(vg), reemplaza=r) for i, h, v, vg, r in self.db.execute(
            f"SELECT id, hecho, version, vigente, reemplaza FROM hechos WHERE app=? AND usuario=? {cond} ORDER BY id",
            (app, usuario))]

    async def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        filas, embs = self._vigentes(app_name, user_id)
        if not len(filas):
            return SearchMemoryResponse(memories=[])
        scores = embs @ _Embedder.vec([query])[0]
        orden = [i for i in np.argsort(-scores)[: self.top_k] if scores[i] >= self.MIN_SCORE]
        return SearchMemoryResponse(memories=[
            _entrada(filas[i][1], "memoria", filas[i][3], score=round(float(scores[i]), 4), version=filas[i][4])
            for i in orden])

    # ── escritura ───────────────────────────────────────────────────────────────────────────
    async def add_session_to_memory(self, session) -> None:
        transcripcion = "\n".join(
            f"{'Usuario' if e.author == 'user' else 'Asistente'}: {t}"
            for e in session.events if (t := texto_evento(e)))
        if not transcripcion:
            return
        extraccion, meta = await asyncio.to_thread(
            self.chat_json, [{"role": "user", "content": PROMPT_EXTRACCION.format(conversacion=transcripcion)}],
            _Hechos, num_predict=350)
        if extraccion is None:  # el modelo no devolvió un JSON válido: no se inventa nada
            self.traza.append({"sesion": session.id, "hecho": None, "accion": "extracción inválida (no se guardó nada)"})
            return
        for h in extraccion.hechos:
            await self._consolidar(session, re.sub(r"\s+", " ", h.hecho).strip())

    async def _consolidar(self, session, nuevo: str) -> None:
        if not nuevo:
            return
        app, usuario = session.app_name, session.user_id
        vec = _Embedder.vec([nuevo])[0]
        filas, embs = self._vigentes(app, usuario)
        accion, reemplaza, sim = "agregar", None, 0.0
        if len(filas):
            sims = embs @ vec
            k = int(np.argmax(sims))
            sim = float(sims[k])
            existente_id, existente = filas[k][0], filas[k][1]
            if existente.lower() == nuevo.lower() or sim >= self.SIM_DUPLICADO:
                accion = "ignorar"
            elif sim >= self.SIM_MISMO_TEMA:
                dec, _ = await asyncio.to_thread(
                    self.chat_json,
                    [{"role": "user", "content": PROMPT_CONSOLIDACION.format(existente=existente, nuevo=nuevo)}],
                    _Decision, num_predict=40)
                pedida = (dec.accion.strip().lower() if dec else "")
                accion = pedida if pedida in ("actualizar", "agregar", "ignorar") else "agregar"  # el código valida
                if accion == "actualizar":
                    reemplaza = existente_id
        self.traza.append({"sesion": session.id, "hecho": nuevo, "accion": accion, "similitud": round(sim, 3)})
        if accion == "ignorar":
            return
        version = 1
        if reemplaza is not None:
            self.db.execute("UPDATE hechos SET vigente=0 WHERE id=?", (reemplaza,))
            version = self.db.execute("SELECT version FROM hechos WHERE id=?", (reemplaza,)).fetchone()[0] + 1
        self.db.execute("INSERT INTO hechos(app, usuario, hecho, emb, sesion, creado, version, reemplaza) VALUES (?,?,?,?,?,?,?,?)",
                        (app, usuario, nuevo, vec.tobytes(), session.id, _ahora(), version, reemplaza))
        self.db.commit()

    def borrar_usuario(self, app: str, usuario: str) -> int:
        """Derecho al olvido: borra TODOS los hechos del usuario, vigentes e historial. Devuelve cuántos."""
        n = self.db.execute("DELETE FROM hechos WHERE app=? AND usuario=?", (app, usuario)).rowcount
        self.db.commit()
        return n
