"""Infraestructura de la demo de talento (GraphRAG con ADK 2 + Neo4j + Gemini de Google AI Studio).

Neo4j corre en un contenedor propio de esta demo (puerto 7688 por defecto; ver docker-compose.yml).
Reglas de seguridad:
  - El modelo NUNCA escribe Cypher. Toda consulta es una plantilla fija con parámetros.
  - Las lecturas usan sesión de solo lectura (`READ_ACCESS`).
  - Nada que venga del usuario o del modelo se interpola en un Cypher.
"""
import hashlib
import json
import os
import pathlib
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from neo4j import READ_ACCESS, GraphDatabase

RAIZ = pathlib.Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")  # GOOGLE_API_KEY y el resto de la configuración

# Variables TALENT_*: así no chocan con un NEO4J_URI que ya tengas definido para otros proyectos.
NEO4J_URI = f"bolt://127.0.0.1:{os.getenv('TALENT_BOLT_PORT', '7688')}"
NEO4J_AUTH = ("neo4j", os.getenv("TALENT_NEO4J_PASSWORD", "demo-talent-local"))
DEMO_MODEL = os.getenv("DEMO_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
DIM = 768  # gemini-embedding-001 devuelve 3072 por defecto; se pide 768 y el índice vectorial se crea con la misma dimensión
INDICE_SKILLS = "skill_emb"
DATOS = RAIZ / "datos"

# Tipo de tarea de los embeddings. Todo lo que se compara acá son textos cortos contra textos cortos (una skill contra otra,
# o lo que escribe el usuario contra la descripción de una skill), así que se usa SEMANTIC_SIMILARITY en ambos lados.
# Con RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY, `Security` quedaba casi tan cerca de `Testing` y de `Linux` como `AWS` de `Azure`.
TAREA_EMBEDDING = "SEMANTIC_SIMILARITY"

# Umbrales de similitud semántica. El score de Neo4j es (1 + coseno) / 2, no el coseno, y este modelo concentra los scores
# de skill contra skill entre 0.86 y 0.96. Elegidos A OJO con `./run.sh calibrar` mirando qué pares quedan como «parecidos»
# (se probaron sobre unos 25 pares sensatos y dudosos). No hay una métrica ni un conjunto de evaluación: si cambiás el
# modelo o el tipo de tarea de los embeddings, hay que repetir la calibración.
UMBRAL_SKILL_SKILL = 0.94    # arista SIMILAR_SEMANTIC entre dos skills del grafo
UMBRAL_CONSULTA = 0.895      # texto libre del usuario contra las skills

AVISOS_429: list[str] = []
_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH, notifications_min_severity="OFF")
    return _driver


def esperar_neo4j(timeout_s: int = 120) -> None:
    fin = time.time() + timeout_s
    while True:
        try:
            driver().verify_connectivity()
            return
        except Exception as e:  # noqa: BLE001
            if time.time() > fin:
                raise SystemExit(
                    f"Neo4j no responde en {NEO4J_URI} ({type(e).__name__}).\n"
                    "Levantalo con:  ./run.sh up")
            time.sleep(2)


def leer(query: str, **params) -> list[dict]:
    """Lectura parametrizada, en sesión de solo lectura."""
    with driver().session(default_access_mode=READ_ACCESS) as s:
        return s.execute_read(lambda tx: [r.data() for r in tx.run(query, params)])


def escribir(query: str, **params) -> list[dict]:
    with driver().session() as s:
        return s.execute_write(lambda tx: [r.data() for r in tx.run(query, params)])


def ddl(query: str) -> None:
    with driver().session() as s:
        s.run(query).consume()


def es_429(e: Exception) -> bool:
    t = f"{type(e).__name__} {e}"
    return "429" in t or "RESOURCE_EXHAUSTED" in t or "ResourceExhausted" in t


def explicar_error(e: Exception) -> str | None:
    """Traduce los errores de configuración más comunes a una indicación concreta (None si no es uno de ellos)."""
    t = f"{type(e).__name__} {e}"
    if "Missing key inputs" in t:
        return ("Falta la API key de Gemini: copiá .env.example a .env y pegá tu GOOGLE_API_KEY "
                "(se genera gratis en https://aistudio.google.com/apikey).")
    if "API_KEY_INVALID" in t or "API key not valid" in t or "API key expired" in t:
        return ("La API key no es válida. Revisá GOOGLE_API_KEY en el archivo .env "
                "(se genera gratis en https://aistudio.google.com/apikey).")
    if "NOT_FOUND" in t or "PERMISSION_DENIED" in t:
        return (f"Tu clave no pudo usar el modelo ({t[:160]}). Modelos en uso: DEMO_MODEL={DEMO_MODEL}, EMBED_MODEL={EMBED_MODEL}. "
                "Probá con otro modelo de Gemini poniendo DEMO_MODEL=... en .env (ver .env.example).")
    return None


def con_reintentos(fn, etiqueta: str, intentos: int = 5):
    """Reintenta ante 429 (límite de pedidos por minuto, frecuente en la capa gratuita) con espera creciente."""
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if es_429(e) and i < intentos - 1:
                espera = min(60, 10 * (2 ** i))
                AVISOS_429.append(f"{etiqueta}: 429 (intento {i + 1}), espero {espera}s")
                print(f"  [429] {etiqueta}: reintento en {espera}s")
                time.sleep(espera)
                continue
            msg = explicar_error(e)
            if msg:
                raise SystemExit(msg) from e
            raise


def cliente_gemini() -> genai.Client:
    """Cliente del SDK de Gemini: toma GOOGLE_API_KEY del entorno (.env). Falla con un mensaje claro si falta."""
    try:
        return genai.Client()
    except Exception as e:  # noqa: BLE001
        raise SystemExit("Falta la API key de Gemini: copiá .env.example a .env y pegá tu GOOGLE_API_KEY "
                         "(se genera gratis en https://aistudio.google.com/apikey).") from e


# ── Embeddings, con caché en disco (cada texto se calcula una sola vez) ──────────────────────
_CACHE = RAIZ / ".cache" / "embeddings.json"
LOTE_EMBEDDINGS = 20


def embed(textos: list[str]) -> list[list[float]]:
    """Vectores de DIM dimensiones, uno por texto. Solo llama a la API por lo que falta en caché."""
    cache = json.loads(_CACHE.read_text()) if _CACHE.exists() else {}
    claves = [hashlib.sha256(f"{EMBED_MODEL}|{DIM}|{TAREA_EMBEDDING}|{t}".encode()).hexdigest() for t in textos]
    faltan = [i for i, c in enumerate(claves) if c not in cache]
    if faltan:
        cliente = cliente_gemini()
        for ini in range(0, len(faltan), LOTE_EMBEDDINGS):
            lote = faltan[ini:ini + LOTE_EMBEDDINGS]
            r = con_reintentos(
                lambda: cliente.models.embed_content(
                    model=EMBED_MODEL, contents=[textos[i] for i in lote],
                    config=types.EmbedContentConfig(task_type=TAREA_EMBEDDING, output_dimensionality=DIM)),
                "embeddings")
            for i, emb in zip(lote, r.embeddings):
                cache[claves[i]] = list(emb.values)
        _CACHE.parent.mkdir(exist_ok=True)
        _CACHE.write_text(json.dumps(cache))
    return [cache[c] for c in claves]
