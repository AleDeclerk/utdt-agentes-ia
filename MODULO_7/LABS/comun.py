"""
Piezas comunes de la demo ADK2 del Módulo 7 (few-shot dinámico, Reflexion, ExpeL).

Un solo grafo (`crear_workflow`) sirve para todas las condiciones del experimento:

    START ─► [recuperar] ─► resolver ─► evaluar ──ok / sin intentos──► fin
                               ▲           │ fallo
                               │           ▼
                               └─ guardar ◄─ reflexionar

  `recuperar` es un nodo opcional que escribe en el estado lo que el agente "recuerda":
    - few-shot dinámico : `ejemplos`  (casos resueltos parecidos)
    - Reflexion         : `lecciones` (reflexiones guardadas de casos parecidos)

Qué es Reflexion en esta demo (la versión del paper):

  - Corto plazo: dentro de UNA tarea, cada reflexión se agrega a un buffer acotado de
    `session.state` (`reflexiones`) y se antepone al siguiente intento.
  - Largo plazo: las reflexiones de las tareas terminadas se guardan en una memoria
    PERSISTENTE (`MemoriaReflexiones`, un archivo JSON) y se RECUPERAN POR PARECIDO
    cuando el agente enfrenta la misma tarea u otra similar (`lecciones`).
  - Lo que Reflexion NO hace por diseño: generalizar. Guarda lecciones sueltas, atadas a
    casos concretos ("en esta comisión de $90.300 debí redondear a 994"), sin destilarlas
    en reglas ni votarlas. Eso es lo que agrega ExpeL (ver expel_adk2.py).

Claves de `session.state` que usa el grafo:

  tarea, problema        entrada: el dict de la tarea y su enunciado
  respuesta              salida del agente `resolver` (output_key)
  intento, feedback      los escribe `evaluar` (feedback revela el número correcto)
  reflexion              salida del agente `reflexionar` (output_key)
  buffer, reflexiones    los escribe `_guardar`: buffer acotado de ESTA tarea y su texto
  trayectoria            lista de intentos [{intento, numero, ok, respuesta, reflexion}]
  lecciones, lecciones_ids   las escribe `recuperar_lecciones` (memoria persistente)
  reglas, ejemplos       opcionales; los inyecta quien llama (ExpeL) o `recuperar` (few-shot)

Dos reglas de ADK 2 que este módulo respeta:
  1. El modelo NO lee el estado: llega al prompt solo vía plantillas `{clave}` en la
     instrucción (`{clave?}` si puede faltar).
  2. El estado se escribe por ASIGNACIÓN (`ctx.state["k"] = lista_nueva`); un
     `.append` sobre la lista que ya está en el estado se pierde.

Variables de entorno (ver .env.example): GOOGLE_API_KEY (API key de Google AI Studio),
GOOGLE_GENAI_USE_VERTEXAI=FALSE, DEMO_MODEL, DEMO_CONCURRENCIA y DEMO_TOPE_USD.
Escrito para google-adk 2.11.0 (API usada: Workflow, Event(route=...), LlmAgent con
output_key / include_contents="none").
"""
import asyncio
import json
import logging
import os
import textwrap
import time
import uuid
import warnings
from typing import Awaitable, Callable, Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()

# Salida limpia para la clase: se silencian avisos de dependencias y los logs internos de
# ADK/genai (el 429 «Root node … failed» se reintenta solo: `con_reintentos` avisa con una
# línea propia). Una falla real igual termina el script con su excepción.
warnings.filterwarnings("ignore")
try:   # authlib se pone un filtro «always» propio al importarse: hay que pisarlo después
    from authlib.deprecate import AuthlibDeprecationWarning
    warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)
except ImportError:
    pass
for _nombre in ("google_genai", "google_adk", "google.adk", "httpx", "authlib"):
    logging.getLogger(_nombre).setLevel(logging.CRITICAL)

from google import genai
from google.adk import Event, Runner, Workflow
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import START
from google.genai import types

from tareas import es_correcta, extraer_numero

MODEL = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
# Llamadas simultáneas al modelo. La API limita las solicitudes por minuto y por proyecto
# (en el nivel gratuito, bastante): con 2 hay menos 429. Subilo si tu cuota lo permite.
CONCURRENCIA = int(os.environ.get("DEMO_CONCURRENCIA", "2"))

# ─── Costo medido ───────────────────────────────────────────────────────────────────
# Precios de lista de gemini-2.5-flash en el nivel de pago de la Gemini API (página de
# precios, verificada el 2026-10-19): entrada $0.30 y salida $2.50 por millón de tokens; el
# razonamiento («thinking») se cobra como salida. En el nivel gratuito no se cobra: el
# número es la referencia de lo que costaría. Los embeddings no se cuentan (despreciables).
# Los precios son los de gemini-2.5-flash; con otro DEMO_MODEL el costo es solo aproximado.
PRECIO_ENTRADA_USD = 0.30
PRECIO_SALIDA_USD = 2.50
TOPE_USD = float(os.environ.get("DEMO_TOPE_USD", "0.60"))     # corta la corrida si lo supera
ARCHIVO_COSTOS = "costo_acumulado.json"
USO = {"llamadas": 0, "entrada": 0, "salida": 0}


class TopeDeCostoExcedido(RuntimeError):
    """La corrida superó DEMO_TOPE_USD: se corta para no gastar de más."""


def costo_usd() -> float:
    return USO["entrada"] / 1e6 * PRECIO_ENTRADA_USD + USO["salida"] / 1e6 * PRECIO_SALIDA_USD


def contar_uso(ctx, llm_response):
    """`after_model_callback` de cada LlmAgent: suma tokens reales (`usage_metadata`).
    Tolera respuestas sin metadata (modelo falso en las pruebas)."""
    um = getattr(llm_response, "usage_metadata", None)
    if um is None or getattr(llm_response, "partial", False):
        return None
    USO["llamadas"] += 1
    USO["entrada"] += um.prompt_token_count or 0
    USO["salida"] += (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
    if costo_usd() > TOPE_USD:
        raise TopeDeCostoExcedido(f"costo medido ${costo_usd():.2f} > tope ${TOPE_USD:.2f}")
    return None


def registrar_costo(nombre: str) -> None:
    """Imprime el costo medido de la corrida y lo agrega al registro `costo_acumulado.json`."""
    c = costo_usd()
    print(f"\nCOSTO MEDIDO · {USO['llamadas']} llamadas al modelo, {USO['entrada']:,} tokens de entrada, "
          f"{USO['salida']:,} de salida (con razonamiento) → equivale a ${c:.3f} USD a precio de lista")
    try:
        hist = json.load(open(ARCHIVO_COSTOS, encoding="utf-8")) if os.path.exists(ARCHIVO_COSTOS) else []
    except (OSError, ValueError):
        hist = []
    hist.append({"demo": nombre, "fecha": time.strftime("%Y-%m-%d %H:%M"), "modelo": str(MODEL), **USO,
                 "usd": round(c, 4), "acumulado_usd": round(sum(h.get("usd", 0) for h in hist) + c, 4)})
    with open(ARCHIVO_COSTOS, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)
    print(f"  (acumulado en {ARCHIVO_COSTOS}: ${hist[-1]['acumulado_usd']:.3f} USD)")


def narrar(texto: str, titulo: str = "Qué pasó") -> None:
    """Explicación breve, en prosa, de lo que acaba de verse. El texto lo arma cada demo
    A PARTIR DE LOS RESULTADOS (nunca fijo): si la corrida sale mal, dice que salió mal."""
    cuerpo = textwrap.fill(texto, width=96, initial_indent="  ▸ ", subsequent_indent="    ")
    print(f"\n  {titulo}:" if titulo else "")
    print(cuerpo)
EMBEDDING_MODEL = "gemini-embedding-001"
MAX_BUFFER = 5       # Reflexion, corto plazo: ventana deslizante. Un buffer sin límite es el anti-patrón.
K_LECCIONES = 2      # Reflexion, largo plazo: cuántas lecciones parecidas se recuperan.
#                      Con pocas lecciones guardadas, un k grande recupera TODO y la
#                      selección "por parecido" no se ve; por eso k es chico.
ARCHIVO_MEMORIA = "memoria_reflexiones.json"
APP = "modulo7"

INSTRUCCION_RESOLVER = (
    "Sos un analista financiero de un banco. Resolvé el problema con precisión.\n"
    "{reglas?}\n{ejemplos?}\n{lecciones?}\n{reflexiones?}\n"
    "PROBLEMA: {problema}"
)
INSTRUCCION_REFLEXION = (
    "Acabás de fallar un cálculo financiero.\n"
    "PROBLEMA: {problema}\nTU RESPUESTA: {respuesta}\nRESULTADO DEL VERIFICADOR: {feedback}\n"
    "Analizá qué convención o supuesto te faltó (no solo el error aritmético) y "
    "qué vas a hacer distinto. Terminá con: Plan: <estrategia corregida en una frase>."
)


def verificar_credenciales() -> None:
    """Corta con un mensaje claro si falta la API key, en vez de dejar que falle la librería
    en medio de la corrida. Se llama antes de la primera llamada al modelo o a embeddings."""
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        raise SystemExit("Falta GOOGLE_API_KEY. Copiá .env.example a .env y pegá tu API key de "
                         "Google AI Studio (https://aistudio.google.com/apikey).")


# ─── Embeddings (compartidos por few-shot dinámico y memoria de Reflexion) ──────────
_cliente: Optional[genai.Client] = None


def embeber(textos: list[str]) -> np.ndarray:
    """Embeddings normalizados (norma 1) de una lista de textos: con vectores
    normalizados, el producto interno equivale a la similitud coseno.
    El cliente se crea la primera vez y toma la API key de AI Studio de `.env`."""
    global _cliente
    verificar_credenciales()
    if _cliente is None:
        _cliente = genai.Client()
    r = _cliente.models.embed_content(model=EMBEDDING_MODEL, contents=textos)
    v = np.array([e.values for e in r.embeddings], dtype=float)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# ─── Memoria persistente de Reflexion ───────────────────────────────────────────────
class MemoriaReflexiones:
    """Memoria de largo plazo de Reflexion: lecciones sueltas, ligadas a casos concretos.

    Cada entrada es {id_tarea, categoria, problema, reflexion}. Se guarda en un archivo
    JSON (legible y versionable) y se recupera POR PARECIDO del enunciado: se embebe el
    `problema` de cada entrada y se buscan las `k` más cercanas a la tarea actual.

    No generaliza ni vota: dos tareas parecidas dejan dos lecciones, no una regla.
    Esa es la diferencia con ExpeL."""

    def __init__(self, archivo: Optional[str] = None, cargar: bool = True):
        """`archivo`: dónde se persiste. `cargar=False` parte de una memoria VACÍA aunque
        el archivo exista (lo usa la pasada de aprendizaje: se sobrescribe al guardar)."""
        self.archivo = archivo
        self.entradas: list[dict] = []
        self._vectores: Optional[np.ndarray] = None   # caché; se invalida al agregar
        if cargar and archivo and os.path.exists(archivo):
            with open(archivo, encoding="utf-8") as f:
                self.entradas = json.load(f)

    def __len__(self) -> int:
        return len(self.entradas)

    def retener(self, tarea: dict, resultado: dict) -> int:
        """Paso 'Retain': guarda las reflexiones de una tarea TERMINADA. Se llama afuera
        del grafo y una sola vez por tarea (así un reintento por red no duplica lecciones).
        Devuelve cuántas lecciones agregó."""
        nuevas = resultado.get("reflexiones", [])
        for r in nuevas:
            self.entradas.append({"id_tarea": tarea["id"], "categoria": tarea["categoria"],
                                  "problema": tarea["prompt"], "reflexion": r})
        if nuevas:
            self._vectores = None
        return len(nuevas)

    def buscar(self, problema: str, k: int = K_LECCIONES) -> list[dict]:
        """Las `k` lecciones cuyo problema es más parecido a `problema` (coseno)."""
        if not self.entradas:
            return []
        if self._vectores is None:
            self._vectores = embeber([e["problema"] for e in self.entradas])
        q = embeber([problema])[0]
        top = np.argsort(-(self._vectores @ q))[:k]
        return [self.entradas[i] for i in top]

    def copia_solo_lectura(self) -> "MemoriaReflexiones":
        """Instantánea sin archivo asociado. Para evaluar sobre tareas NUEVAS sin que
        el experimento contamine la memoria ni las condiciones se contaminen entre sí."""
        c = MemoriaReflexiones()
        c.entradas = [dict(e) for e in self.entradas]
        c._vectores = self._vectores
        return c

    def guardar(self, archivo: Optional[str] = None) -> None:
        destino = archivo or self.archivo or ARCHIVO_MEMORIA
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(self.entradas, f, indent=2, ensure_ascii=False)


def crear_recuperador_lecciones(memoria: MemoriaReflexiones, k: int = K_LECCIONES) -> Callable:
    """Nodo-función del grafo (para el parámetro `recuperar`): busca en la memoria las
    lecciones de casos parecidos y las deja en `state['lecciones']`, que la instrucción
    del agente incorpora con `{lecciones?}`. Es la 'recuperación' del bucle de mejora."""
    async def recuperar_lecciones(node_input, ctx) -> Event:
        top = await asyncio.to_thread(memoria.buscar, ctx.state["problema"], k)
        ctx.state["lecciones_ids"] = [e["id_tarea"] for e in top]
        ctx.state["lecciones"] = (
            "Lecciones de casos parecidos anteriores (usalas):\n"
            + "\n".join(f"- ({e['id_tarea']}) {e['reflexion']}" for e in top)
        ) if top else ""
        return Event(output="lecciones recuperadas")
    return recuperar_lecciones


# ─── Grafo ──────────────────────────────────────────────────────────────────────────
def _nodo_evaluar(max_intentos: int):
    """Fábrica del nodo `evaluar` (la señal de calidad del bucle).

    Compara la respuesta con la esperada, registra el intento en `trayectoria` y elige
    la ruta: "fin" si acertó o se agotaron `max_intentos`, "fallo" si hay que reflexionar.
    El feedback revela el número correcto: es una señal MUY rica (ver README)."""
    def evaluar(node_input, ctx) -> Event:
        t = ctx.state["tarea"]
        n = extraer_numero(str(ctx.state["respuesta"]))
        ok = es_correcta(n, t)
        intento = ctx.state.get("intento", 0) + 1
        ctx.state["intento"] = intento
        ctx.state["feedback"] = (
            f"tu número fue {n}; el número correcto era {t['correct_answer']}."
        )
        ctx.state["trayectoria"] = (ctx.state.get("trayectoria") or []) + [
            {"intento": intento, "numero": n, "ok": ok, "respuesta": str(ctx.state["respuesta"])[:300]}
        ]
        return Event(output={"n": n, "ok": ok},
                     route="fin" if (ok or intento >= max_intentos) else "fallo")
    return evaluar


def _guardar(node_input, ctx) -> Event:
    """Agrega la reflexión al buffer de ESTA tarea, lo recorta a las últimas MAX_BUFFER y
    arma el texto que la instrucción de `resolver` recibe como `{reflexiones?}`."""
    buf = ((ctx.state.get("buffer") or []) + [str(ctx.state["reflexion"])])[-MAX_BUFFER:]
    ctx.state["buffer"] = buf
    ctx.state["reflexiones"] = (
        "Reflexiones de intentos anteriores de ESTA tarea (usalas):\n" + "\n".join(f"- {r}" for r in buf)
    )
    tr = list(ctx.state["trayectoria"])
    tr[-1] = {**tr[-1], "reflexion": str(ctx.state["reflexion"])}
    ctx.state["trayectoria"] = tr
    return Event(output="reflexion guardada")


def _fin(node_input, ctx) -> Event:
    """Nodo terminal: no hace nada; existe para que la ruta "fin" tenga destino."""
    return Event(output="fin")


def crear_workflow(max_intentos: int = 1, recuperar: Optional[Callable] = None) -> Workflow:
    """Arma el grafo resolver → evaluar → (reflexionar → guardar → resolver)*.

    `max_intentos=1` es la condición SIN memoria (no hay reflexión posible).
    `max_intentos=3` permite Reflexion: buffer de la tarea + (opcional) memoria persistente.
    ExpeL es el mismo grafo con `reglas` en el estado.
    `recuperar` es un nodo-función opcional que escribe lo que el agente recuerda
    (`ejemplos` del few-shot o `lecciones` de Reflexion) y se conecta entre START y `resolver`."""
    verificar_credenciales()
    resolver = LlmAgent(name="resolver", model=MODEL, output_key="respuesta",
                        include_contents="none", instruction=INSTRUCCION_RESOLVER,
                        after_model_callback=contar_uso)
    reflexionar = LlmAgent(name="reflexionar", model=MODEL, output_key="reflexion",
                           include_contents="none", instruction=INSTRUCCION_REFLEXION,
                           after_model_callback=contar_uso)
    evaluar = _nodo_evaluar(max_intentos)
    entrada = [(START, recuperar), (recuperar, resolver)] if recuperar else [(START, resolver)]
    return Workflow(name=f"wf_{max_intentos}", edges=entrada + [
        (resolver, evaluar),
        (evaluar, {"fin": _fin, "fallo": reflexionar}),
        (reflexionar, _guardar),
        (_guardar, resolver),
    ])


async def resolver_tarea(wf: Workflow, tarea: dict, estado_extra: Optional[dict] = None) -> dict:
    """Corre una tarea en una sesión NUEVA. Todo lo que el agente 'recuerda' entra por
    `estado_extra` (reglas, ejemplos) o por el nodo `recuperar` (lecciones, ejemplos); el
    buffer de la tarea nace vacío en cada sesión.

    Devuelve {id, categoria, resuelta, primer_intento, intentos, trayectoria,
    reflexiones, lecciones}; `lecciones` son los id de las tareas cuyas lecciones se
    recuperaron. NO escribe en la memoria persistente: eso lo hace quien llama con
    `MemoriaReflexiones.retener` cuando la tarea terminó."""
    svc = InMemorySessionService()
    sid = uuid.uuid4().hex[:8]
    estado = {"tarea": tarea, "problema": tarea["prompt"], **(estado_extra or {})}
    await svc.create_session(app_name=APP, user_id="u", session_id=sid, state=estado)
    runner = Runner(agent=wf, app_name=APP, session_service=svc)
    msg = types.Content(role="user", parts=[types.Part(text="Resolvé el problema.")])
    async for _ in runner.run_async(user_id="u", session_id=sid, new_message=msg):
        pass
    s = (await svc.get_session(app_name=APP, user_id="u", session_id=sid)).state
    tr = s["trayectoria"]
    return {"id": tarea["id"], "categoria": tarea["categoria"], "resuelta": tr[-1]["ok"],
            "primer_intento": tr[0]["ok"], "intentos": len(tr), "trayectoria": tr,
            "reflexiones": [a["reflexion"] for a in tr if a.get("reflexion")],
            "lecciones": s.get("lecciones_ids", [])}


# ─── Concurrencia y reintentos ──────────────────────────────────────────────────────
_SEMAFORO: Optional[asyncio.Semaphore] = None

# Errores transitorios que vale la pena reintentar: cuota de la API (429) y cortes de
# red o de servicio. Una demo con WiFi de aula falla más por esto que por el modelo.
_TRANSITORIOS = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "name resolution",
                 "NameResolutionError", "Max retries exceeded", "TransportError",
                 "ConnectionError", "timed out", "DEADLINE_EXCEEDED")


async def con_reintentos(f: Callable[[], Awaitable[dict]]) -> dict:
    """Ejecuta `f()` y la reintenta ante errores transitorios (`_TRANSITORIOS`) con
    esperas de 10, 30, 60 y 60 s (la cuota por minuto se renueva sola); cualquier otro error
    se propaga. Se usa directamente en
    las pasadas secuenciales (aprendizaje) y desde `correr_en_paralelo`."""
    for espera in (10, 30, 60, 60, None):
        try:
            return await f()
        except Exception as e:
            if espera is None or not any(k in str(e) for k in _TRANSITORIOS):
                raise
            print(f"  … cuota de la API agotada o corte de red; reintento en {espera} s", flush=True)
            await asyncio.sleep(espera)


async def correr_en_paralelo(trabajos: list[Callable[[], Awaitable[dict]]],
                             concurrencia: Optional[int] = None):
    """Concurrencia GLOBAL (un solo semáforo para todas las llamadas) y reintentos con
    espera ante errores transitorios: la API limita las solicitudes por minuto y por proyecto.
    `concurrencia` toma por defecto `DEMO_CONCURRENCIA` (2).

    `trabajos` es una lista de funciones sin argumentos que devuelven una corrutina."""
    global _SEMAFORO
    if _SEMAFORO is None:
        _SEMAFORO = asyncio.Semaphore(concurrencia or CONCURRENCIA)

    async def uno(f):
        async with _SEMAFORO:
            return await con_reintentos(f)
    return await asyncio.gather(*[uno(f) for f in trabajos])


def resumen(nombre: str, res: list[dict]) -> dict:
    """Agrega los resultados de una condición, los imprime en una línea y devuelve
    {condicion, n, primer_intento, resueltas, intentos_prom} (fracciones 0-1)."""
    n = len(res)
    r = {"condicion": nombre, "n": n,
         "primer_intento": sum(x["primer_intento"] for x in res) / n,
         "resueltas": sum(x["resuelta"] for x in res) / n,
         "intentos_prom": sum(x["intentos"] for x in res) / n}
    print(f"  {nombre:<30} 1er intento {r['primer_intento']:5.0%} | resueltas {r['resueltas']:5.0%} "
          f"| intentos prom {r['intentos_prom']:.2f}  (n={n})")
    return r


def baseline_vs_tecnica(tecnica: str, baseline: list[dict], con_tecnica: list[dict],
                        etiqueta_baseline: str = "sin memoria") -> dict:
    """Bloque común a las tres demos: baseline contra UNA técnica, misma métrica.

    La métrica es el acierto al PRIMER intento en tareas nuevas (sin reintentos ni
    reflexión en la prueba), de modo que lo que se ve es lo que la técnica le dio al
    agente antes de actuar. No compara técnicas entre sí. Devuelve un dict para el JSON."""
    nb, nt = len(baseline), len(con_tecnica)
    ab = sum(r["primer_intento"] for r in baseline)
    at = sum(r["primer_intento"] for r in con_tecnica)
    pb, pt = ab / nb, at / nt
    print(f"\nRESUMEN · {tecnica} — acierto al primer intento, tareas nuevas")
    print(f"  {'baseline (' + etiqueta_baseline + ')':<36}{ab:>3}/{nb:<3} {pb:5.0%}")
    print(f"  {'con ' + tecnica:<36}{at:>3}/{nt:<3} {pt:5.0%}")
    print(f"  {'mejora':<36}{(pt - pb) * 100:+.0f} puntos")
    return {"tecnica": tecnica, "baseline": {"aciertos": ab, "n": nb, "tasa": pb},
            "con_tecnica": {"aciertos": at, "n": nt, "tasa": pt}, "mejora_puntos": (pt - pb) * 100}
