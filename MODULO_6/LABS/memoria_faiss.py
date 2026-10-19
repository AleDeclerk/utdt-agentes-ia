"""Memoria de largo plazo local: FAISS + SQLite, con Gemini como LLM del agente.

Muestra lo que hace un servicio de memoria de largo plazo sin depender de un servicio administrado:
`DatabaseSessionService` (SQLite) guarda las sesiones y `SqliteFaissMemoryService` (FAISS + SQLite, en
`servicios_memoria.py`, sin LLM) guarda los turnos con su vector. El agente (Gemini) usa `PreloadMemoryTool`, que
antes de cada llamada busca en la memoria con el mensaje del usuario.

Necesita `GOOGLE_API_KEY`. Las bases viven en `datos_memoria_faiss/` (no se versionan).
Códigos de salida: 0 = OK, 1 = una verificación falló, 2 = error de ejecución.

Subcomandos (cada uno es un proceso distinto: eso es lo que prueba la persistencia):
    python memoria_faiss.py reset      borra las bases de datos de esta demo
    python memoria_faiss.py guardar    "Día 1": conversa, cierra la sesión y la manda a memoria
    python memoria_faiss.py recordar   "Día 2": proceso NUEVO; verifica y pregunta en una sesión vacía
    python memoria_faiss.py todo       reset + guardar + recordar, cada uno en su propio proceso

Verificaciones sin modelo (deterministas): un proceso nuevo recupera lo guardado, otro `user_id` recibe una lista vacía,
`PreloadMemoryTool` inyecta <PAST_CONVERSATIONS> y, si la búsqueda falla, no da error. Con Gemini: la respuesta de la sesión
nueva usa lo que solo se dijo en la anterior, contra un control (usuario sin memoria).
"""
import asyncio
import os
import pathlib
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

from google.adk import Agent, Runner
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService, Session
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.models.llm_request import LlmRequest
from google.genai.types import Content, GenerateContentConfig, Part

from adk_util import con_reintentos_async
from servicios_memoria import SqliteFaissMemoryService

DATOS = pathlib.Path(__file__).resolve().parent / "datos_memoria_faiss"
MODELO = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
DB_SESIONES, DB_MEMORIA = DATOS / "sesiones.db", DATOS / "memoria_faiss.db"
APP = "asistente_normativa"
OFICIAL_44, OFICIAL_51, OFICIAL_99 = "oficial_cuentas_44", "oficial_cuentas_51", "oficial_cuentas_99"

DIA_1 = [
    "Hola, consulto por Textil Norte S.A., banca corporativa. Hoy tienen 3.4 millones de dólares de exposición.",
    "Estoy evaluando una línea de capital de trabajo a 24 meses para ese cliente.",
    "El dictamen de la Gerencia de Riesgos se emitió el 10 de julio.",
]
PREGUNTA_DIA_2 = "¿Qué cliente estábamos analizando y qué producto y plazo evaluábamos?"

INSTRUCCION = ("Sos un asistente de normativa interna para oficiales de cuentas de una entidad financiera. "
               "Respondé en UNA o DOS oraciones. Si no tenés información de conversaciones anteriores, decilo "
               "en vez de inventar.")


# Cuántos turnos devuelve `search_memory` (y por tanto cuántos recibe el modelo). Con el valor por defecto (3), las respuestas del agente
# del Día 1 —que cambian en cada corrida— a veces desplazaban del top 3 al turno donde el usuario nombra al cliente, y Gemini contestaba
# «no sé qué cliente». Con 6 entran los 6 turnos del usuario 44 (3 del usuario + 3 del agente).
TOP_K = 6


def agente() -> Agent:
    return Agent(name="asistente_de_normativa", model=MODELO,
                 instruction=INSTRUCCION, tools=[PreloadMemoryTool()],
                 generate_content_config=GenerateContentConfig(temperature=0.0))  # respuestas lo más estables posible entre corridas


def servicios():
    ses = DatabaseSessionService(f"sqlite+aiosqlite:///{DB_SESIONES}")
    mem = SqliteFaissMemoryService(str(DB_MEMORIA), top_k=TOP_K)
    return ses, mem, Runner(agent=agente(), app_name=APP, session_service=ses, memory_service=mem)


async def turno(runner: Runner, user_id: str, session_id: str, mensaje: str) -> str:
    async def una_vez() -> str:
        final = ""
        async for ev in runner.run_async(user_id=user_id, session_id=session_id,
                                         new_message=Content(role="user", parts=[Part(text=mensaje)])):
            if ev.is_final_response() and ev.content and ev.content.parts:
                final = ev.content.parts[0].text  # sin `break`: cortar el generador rompe el contexto de OpenTelemetry
        return final
    # Reintenta solo errores transitorios (cuota, red, 503). Si el fallo ocurre después de guardar el mensaje del usuario,
    # el reintento lo deja repetido en la sesión: no cambia ninguna verificación.
    return await con_reintentos_async(una_vez, "agente (memoria_faiss)")


def sesion_a_mano(user_id: str, session_id: str, dialogo: list[tuple[str, str]]) -> Session:
    """Una sesión ya cerrada armada a mano (sin LLM), para probar el aislamiento entre usuarios."""
    return Session(id=session_id, app_name=APP, user_id=user_id, events=[
        Event(author=a, content=Content(role="user" if a == "user" else "model", parts=[Part(text=t)]))
        for a, t in dialogo])


# ── Día 1 ────────────────────────────────────────────────────────────────────────────────────
async def guardar() -> None:
    DATOS.mkdir(exist_ok=True)
    ses, mem, runner = servicios()
    await ses.create_session(app_name=APP, user_id=OFICIAL_44, session_id="dia1_s1")
    print("== DÍA 1 · sesión dia1_s1 (oficial_cuentas_44) con Gemini ==")
    for m in DIA_1:
        print(f"Usuario: {m}\nAgente:  {await turno(runner, OFICIAL_44, 'dia1_s1', m)}\n")
    cerrada = await ses.get_session(app_name=APP, user_id=OFICIAL_44, session_id="dia1_s1")
    await mem.add_session_to_memory(cerrada)
    # Otro usuario, otra conversación (sin LLM): sirve para verificar el aislamiento en el Día 2.
    await mem.add_session_to_memory(sesion_a_mano(OFICIAL_51, "dia1_s2", [
        ("user", "Consulto por Frigorífico Pampa S.R.L.: quiero un leasing sobre maquinaria a 84 meses."),
        ("asistente", "Anotado: leasing sobre maquinaria a 84 meses para Frigorífico Pampa S.R.L.")]))
    print(f"Sesión persistida en SQLite y {mem.total()} turnos en la memoria (de 2 usuarios).")
    print(f"Modelo: {MODELO}.")


# ── Día 2 (proceso nuevo) ────────────────────────────────────────────────────────────────────
class _ToolContextFalso:
    """Lo mínimo que usa PreloadMemoryTool.process_llm_request, para probarlo sin invocar al modelo."""
    def __init__(self, mem, user_id, texto):
        self.user_content = Content(role="user", parts=[Part(text=texto)])
        self._mem, self._user = mem, user_id

    async def search_memory(self, query):
        return await self._mem.search_memory(app_name=APP, user_id=self._user, query=query)


class _MemoriaRota:
    async def search_memory(self, *a, **k):
        raise RuntimeError("la base de memoria no responde")


def _instrucciones(req: LlmRequest) -> str:
    """Todo el texto que recibiría el modelo: la system instruction y los contenidos. PreloadMemoryTool inyecta el bloque
    como contenido de usuario transitorio (ADK 2.10) o en la system instruction (versiones anteriores): se miran los dos lugares."""
    si = req.config.system_instruction
    sistema = si if isinstance(si, str) else "" if si is None else "\n".join(p.text for p in si.parts if p.text)
    contenidos = "\n".join(p.text for c in (req.contents or []) for p in (c.parts or []) if p.text)
    return sistema + "\n" + contenidos


async def recordar() -> None:
    ses, mem, runner = servicios()
    print(f"== DÍA 2 · proceso NUEVO: la memoria cargó {mem.total()} turnos desde SQLite ==\n")
    ok = True

    print("[1] search_memory como oficial_cuentas_44 — «producto y plazo de la línea»:")
    r = await mem.search_memory(app_name=APP, user_id=OFICIAL_44, query="¿qué producto y plazo se evaluaba?")
    for m in r.memories:
        print(f"    score={m.custom_metadata['score']:.4f}  {m.author}: {m.content.parts[0].text[:95]}")
    ok &= any("24 meses" in m.content.parts[0].text for m in r.memories)

    print("[2] la MISMA consulta como oficial_cuentas_51 (otro usuario):")
    r51 = await mem.search_memory(app_name=APP, user_id=OFICIAL_51, query="¿qué producto y plazo se evaluaba?")
    textos51 = " ".join(m.content.parts[0].text for m in r51.memories)
    for m in r51.memories:
        print(f"    score={m.custom_metadata['score']:.4f}  {m.author}: {m.content.parts[0].text[:95]}")
    ok &= "Textil Norte" not in textos51 and len(r51.memories) > 0
    print(f"    ¿aparece algo de Textil Norte? {'SÍ (FUGA)' if 'Textil Norte' in textos51 else 'no: aislado'}")

    r99 = await mem.search_memory(app_name=APP, user_id=OFICIAL_99, query="Textil Norte")
    print(f"[3] usuario sin memoria (oficial_cuentas_99): {len(r99.memories)} resultados")
    ok &= len(r99.memories) == 0

    print("[4] ¿PreloadMemoryTool inyecta la memoria? (sin invocar al modelo)")
    req = LlmRequest()
    await PreloadMemoryTool().process_llm_request(tool_context=_ToolContextFalso(mem, OFICIAL_44, PREGUNTA_DIA_2), llm_request=req)
    inyectado = "<PAST_CONVERSATIONS>" in _instrucciones(req)
    print(f"    bloque <PAST_CONVERSATIONS> en la petición al modelo: {'SÍ' if inyectado else 'NO'}")
    ok &= inyectado

    print("[5] fallo silencioso: si search_memory lanza una excepción, PreloadMemoryTool…")
    print("    (el «WARNING:root:Failed to preload memory» que sigue es lo ESPERADO: esta verificación rompe search_memory a propósito)", flush=True)
    req2 = LlmRequest()
    try:
        await PreloadMemoryTool().process_llm_request(tool_context=_ToolContextFalso(_MemoriaRota(), OFICIAL_44, PREGUNTA_DIA_2), llm_request=req2)
        print(f"    …NO da error y sigue sin memoria (inyectó algo: {'<PAST_CONVERSATIONS>' in _instrucciones(req2)}). Solo deja un logging.warning.")
    except Exception as e:  # noqa: BLE001
        print(f"    …propagó la excepción: {e}")
        ok = False

    print(f"\n[6] CON Gemini, sesión NUEVA y vacía, pregunta: «{PREGUNTA_DIA_2}»")
    await ses.create_session(app_name=APP, user_id=OFICIAL_44, session_id="dia2_s1")
    con_memoria = await turno(runner, OFICIAL_44, "dia2_s1", PREGUNTA_DIA_2)
    print(f"    oficial_cuentas_44 (con memoria): {con_memoria}")
    await ses.create_session(app_name=APP, user_id=OFICIAL_99, session_id="dia2_s1")
    control = await turno(runner, OFICIAL_99, "dia2_s1", PREGUNTA_DIA_2)
    print(f"    oficial_cuentas_99 (CONTROL, sin memoria): {control}")
    recuerda = "Textil Norte" in con_memoria and "24" in con_memoria
    no_sabe = "Textil Norte" not in control
    print(f"    recuerda cliente y plazo: {recuerda} | el control NO los conoce: {no_sabe}")
    ok &= recuerda and no_sabe

    print(f"\nModelo: {MODELO}.")
    print("RESULTADO:", "TODAS LAS VERIFICACIONES OK" if ok else "HAY VERIFICACIONES QUE FALLARON")
    sys.exit(0 if ok else 1)


def reset() -> None:
    for f in (DB_SESIONES, DB_MEMORIA):
        f.unlink(missing_ok=True)
    print("Bases de datos de la demo borradas.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    # Códigos de salida: 0 = verificaciones OK · 1 = alguna verificación falló · 2 = error de ejecución (se imprime el traceback).
    try:
        if cmd == "reset":
            reset()
        elif cmd == "guardar":
            asyncio.run(guardar())
        elif cmd == "recordar":
            asyncio.run(recordar())
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("\nERROR DE EJECUCIÓN (no es una verificación fallida): ver el traceback de arriba.")
        sys.exit(2)
    if cmd in ("reset", "guardar", "recordar"):
        pass
    elif cmd == "todo":
        reset()
        for sub in ("guardar", "recordar"):  # procesos separados a propósito
            print(f"\n######## {sub} (proceso nuevo) ########", flush=True)
            rc = subprocess.run([sys.executable, "-u", __file__, sub]).returncode
            if rc:
                sys.exit(rc)
    else:
        sys.exit(__doc__)
