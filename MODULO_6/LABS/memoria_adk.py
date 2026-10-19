"""Memoria de sesión y de largo plazo con ADK 2 (Ejercicio 2, Partes A, B y C).

Escenario: `asistente_de_normativa`, un asistente para oficiales de cuentas de una entidad financiera
(cliente Textil Norte S.A.). Una sesión de cinco turnos, el estado de la sesión (`session.state`), el pasaje
de esa sesión a la memoria de largo plazo (`InMemoryMemoryService`) y una sesión 2 nueva y vacía en la que
`PreloadMemoryTool` le antepone al agente lo recordado. Necesita `GOOGLE_API_KEY` (ver `.env.example`).

Ojo: este agente tiene memoria pero ningún retriever de normativa conectado, así que puede citar una norma
que no existe. Es parte de lo que hay que mirar.
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai.types import Content, Part


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · AYUDA PARA EJECUTAR CÓDIGO ASÍNCRONO
#   Funciona tanto en un script como en un notebook, donde ya hay un event
#   loop corriendo.
# ══════════════════════════════════════════════════════════════════════════════
def run_demo(coro):
    """Ejecuta una coroutine tanto en notebook (Colab/Jupyter) como en script.

    En un notebook ya hay un event loop corriendo y `asyncio.run()` falla con
    `RuntimeError: asyncio.run() cannot be called from a running event loop`.
    En un script no hay loop y hay que crearlo. Este helper cubre los dos casos.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)              # script: no hay loop activo
    import nest_asyncio                       # notebook: ya hay loop activo
    nest_asyncio.apply()
    return asyncio.get_event_loop().run_until_complete(coro)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · EL AGENTE CON MEMORIA
#   Gemini con una instrucción de asistente de normativa y, la línea clave,
#   tools=[PreloadMemoryTool()]: sin ella el agente no ve la memoria.
# ══════════════════════════════════════════════════════════════════════════════
MODEL = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")

# Definición del agente de normativa
normativa_agent = Agent(
    name="asistente_de_normativa",
    model=MODEL,
    instruction="""Sos un asistente de normativa interna para oficiales de cuentas
y suscriptores de una entidad financiera. Tu rol es:
1. Responder consultas sobre políticas de crédito, suscripción y circulares internas
2. Mantener el contexto del caso que se está analizando en esta conversación
3. Adecuar la respuesta al segmento y a la exposición vigente del cliente

IMPORTANTE: Mencioná siempre de qué documento surge cada afirmación, y decí
explícitamente cuando estás usando información de mensajes anteriores. Si la
normativa no cubre el caso, decilo: NO infieras la regla que faltaría.""",
    # Sin esta tool, `search_memory()` recupera memorias para el CÓDIGO pero no
    # para el MODELO: el agente respondería que no recuerda nada de session_001.
    # PreloadMemoryTool se ejecuta sola en cada llamada al LLM (el modelo no la
    # invoca) y agrega las memorias recuperadas a la petición (en ADK 2.10, como contenido
    # de usuario transitorio).
    tools=[PreloadMemoryTool()],
)

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · LOS SERVICIOS DE SESIÓN Y DE MEMORIA
#   La sesión guarda una conversación; la memoria de largo plazo guarda lo que
#   se quiere recordar entre sesiones. Ambas viven en RAM.
# ══════════════════════════════════════════════════════════════════════════════
# Configurar servicios de memoria
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · EL RUNNER
#   Une el agente con los dos servicios para poder ejecutarlo.
# ══════════════════════════════════════════════════════════════════════════════
# Crear runner
runner = Runner(
    agent=normativa_agent,
    app_name="asistente_normativa",
    session_service=session_service,
    memory_service=memory_service,
)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 5 · ENVIAR UN MENSAJE Y LEER LA RESPUESTA FINAL
#   Recorre los eventos del agente sin cortar el bucle.
# ══════════════════════════════════════════════════════════════════════════════
async def get_response(user_id: str, session_id: str, message: str,
                        runner: Runner = runner) -> str:
    """Envía un mensaje al runner y devuelve el texto de la respuesta final."""
    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=Content(parts=[Part(text=message)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text
    return final_text


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 6 · LA SESIÓN 1: CINCO TURNOS
#   Crea la sesión con el estado inicial (producto_consultado en None), manda
#   los mensajes y los imprime.
# ══════════════════════════════════════════════════════════════════════════════
async def multi_turn_session(user_id: str, session_id: str,
                              messages: list[str]) -> list[str]:
    """Ejecuta una sesión de múltiples turnos y retorna las respuestas."""
    session = await session_service.create_session(
        app_name="asistente_normativa",
        user_id=user_id,
        session_id=session_id,
        state={
            "cliente": "Textil Norte S.A.",
            "segmento": "Empresas — Banca Corporativa",
            "exposicion_vigente_usd": 3_400_000,
            "producto_consultado": None,
            "dictamen_riesgos": None,
        }
    )

    responses = []
    for i, message in enumerate(messages):
        print(f"\n[Turno {i+1}] Usuario: {message}")
        answer = await get_response(user_id, session_id, message)
        responses.append(answer)
        print(f"[Turno {i+1}] Agente: {answer[:200]}...")

    return responses


# ── 6b · Los cinco mensajes de la sesión 1 ──
conversation = [
    "Hola, consulto por Textil Norte S.A., banca corporativa. Hoy tienen 3.4 millones "
    "de dólares de exposición con nosotros.",
    "¿Cuánto más le puedo prestar sin salirme del límite normativo?",
    "Estoy evaluando una línea de capital de trabajo a 24 meses. ¿Entra en la política?",
    "¿Qué necesito para elevarlo al Comité de Créditos?",
    "Resumime lo que hablamos hasta ahora sobre esta operación.",
]


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 7 · GUARDAR LA SESIÓN Y RECORDARLA EN OTRA
#   Muestra el estado, guarda la sesión 1 en la memoria de largo plazo, abre
#   una sesión 2 vacía y le pregunta al agente qué se evaluaba.
# ══════════════════════════════════════════════════════════════════════════════
async def persist_and_recall():
    """Persiste la sesión anterior y verifica la recuperación."""
    session = await session_service.get_session(
        app_name="asistente_normativa",
        user_id="oficial_cuentas_44",
        session_id="session_001"
    )

    # ── 7a · Mostrar el estado de la sesión 1: producto_consultado sigue en None ──
    print(f"Estado final de la sesión:")
    print(f"  Estado: {session.state}")
    print(f"  Mensajes en historial: {len(session.events)}")

    # ── 7b · Guardar la sesión 1 en la memoria de largo plazo ──
    await memory_service.add_session_to_memory(session)
    print("\nSesión persistida en memoria de largo plazo.")

    # ── 7c · Abrir una sesión 2 NUEVA y vacía, y buscar en la memoria lo dicho en la 1 ──
    session2 = await session_service.create_session(
        app_name="asistente_normativa",
        user_id="oficial_cuentas_44",
        session_id="session_002"
    )

    memories = await memory_service.search_memory(
        app_name="asistente_normativa",
        user_id="oficial_cuentas_44",
        query="Textil Norte límite asistencia crediticia capital de trabajo"
    )

    print(f"\nMemorías recuperadas para nueva sesión:")
    for mem in memories.memories[:3]:
        print(f"  - {str(mem)[:150]}...")

    # ── 7d · Preguntar en la sesión 2: PreloadMemoryTool le antepone al agente lo recordado ──
    answer = await get_response(
        "oficial_cuentas_44", "session_002",
        "Hola de nuevo. La semana pasada analizamos un cliente corporativo. "
        "¿Te acordás qué producto estábamos evaluando y por qué no entraba?"
    )

    print(f"\nRespuesta en sesión nueva:")
    print(answer)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 8 · ARRANQUE
#   Corre la sesión 1 y después la recuperación en la sesión 2.
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("SESIÓN CON MÚLTIPLES TURNOS")
    print("=" * 60)
    run_demo(multi_turn_session(
        user_id="oficial_cuentas_44",
        session_id="session_001",
        messages=conversation,
    ))
    print()
    run_demo(persist_and_recall())
