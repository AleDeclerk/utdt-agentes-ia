"""Ejercicio 2 · Parte D — el agente escribe en `session.state` con una tool.

Qué muestra: en `memoria_adk.py` el estado terminaba con `producto_consultado: None` después de
cinco turnos hablando de la operación. Acá el agente tiene una tool (`registrar_dato_operacion`) que escribe
con `tool_context.state[...]`, y al final el estado queda poblado. "El agente dijo que lo registró" y "el
sistema lo registró" no son lo mismo.

Necesita `GOOGLE_API_KEY`. No es determinista: el valor que queda guardado es el que el modelo le pasa a la tool
(no el texto literal del usuario) y puede llamarla de más o de menos. El control real es la validación
dentro de la tool.

Uso:  python ejercicio_2d_estado_registrar_dato.py
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from google.adk import Agent, Runner
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool, ToolContext
from google.genai.types import Content, Part

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · CONFIGURACIÓN
#   El modelo (Gemini) y los servicios de sesión y de memoria, que viven en
#   RAM.
# ══════════════════════════════════════════════════════════════════════════════
MODEL = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")

session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · LA HERRAMIENTA QUE ESCRIBE EN EL ESTADO
#   Valida el campo y lo guarda con tool_context.state[campo] = valor. Es lo
#   que diferencia «lo dijo» de «lo registró».
# ══════════════════════════════════════════════════════════════════════════════
def registrar_dato_operacion(campo: str, valor: str, tool_context: ToolContext) -> dict:
    """Registra en el estado de la sesión un dato confirmado de la operación en análisis.

    Llamar esta tool únicamente cuando el oficial CONFIRME explícitamente el dato
    (no cuando esté evaluando alternativas).

    Args:
        campo: "producto_consultado" o "dictamen_riesgos".
        valor: el valor confirmado, tal como lo expresó el oficial.

    Returns:
        Un dict con el resultado del registro.
    """
    if campo not in ("producto_consultado", "dictamen_riesgos"):
        return {"status": "error", "message": f"Campo no reconocido: {campo}"}
    tool_context.state[campo] = valor
    return {"status": "ok", "campo": campo, "valor": valor}


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · EL AGENTE CON LA HERRAMIENTA
#   Gemini con la herramienta y una instrucción: llamarla solo cuando el
#   oficial CONFIRMA un dato, no cuando evalúa alternativas.
# ══════════════════════════════════════════════════════════════════════════════
# Agente específico para esta demo: además de conversar, tiene la tool que
# le permite escribir en session.state cuando el oficial confirma un dato.
stateful_agent = Agent(
    name="asistente_de_normativa_stateful",
    model=MODEL,
    instruction="""Sos un asistente de normativa interna para oficiales de cuentas
de una entidad financiera. Cuando el oficial confirme explícitamente el producto
consultado o el dictamen de la Gerencia de Riesgos, llamá a la tool
`registrar_dato_operacion` para dejarlo registrado en el estado de la sesión
(campo "producto_consultado" o "dictamen_riesgos"). No la llames si el oficial
todavía está evaluando alternativas, solo cuando confirme una decisión tomada.""",
    tools=[FunctionTool(registrar_dato_operacion)],
)

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · EL RUNNER
#   Une el agente con los servicios de sesión y de memoria para poder
#   ejecutarlo.
# ══════════════════════════════════════════════════════════════════════════════
stateful_runner = Runner(
    agent=stateful_agent,
    app_name="asistente_normativa",
    session_service=session_service,
    memory_service=memory_service,
)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 5 · ENVIAR UN MENSAJE Y LEER LA RESPUESTA FINAL
#   Recorre los eventos del agente sin cortar el bucle (cortarlo rompe el
#   contexto de OpenTelemetry).
# ══════════════════════════════════════════════════════════════════════════════
async def get_response(user_id: str, session_id: str, message: str, runner: Runner) -> str:
    """Envía un mensaje al runner y devuelve el texto de la respuesta final.
    No se corta el `async for` con `break`: cortarlo dispara un error de contexto de OpenTelemetry."""
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
# PARTE 6 · LA DEMO
#   Crea la sesión con los dos campos en None, manda tres mensajes y al final
#   lee el estado para comprobar qué se registró.
# ══════════════════════════════════════════════════════════════════════════════
async def stateful_session_demo():
    """Demuestra cómo el agente actualiza `session.state` durante la sesión."""
    # ── 6a · Crear la sesión con el estado inicial: producto_consultado y dictamen_riesgos en None ──
    await session_service.create_session(
        app_name="asistente_normativa",
        user_id="oficial_cuentas_44",
        session_id="session_003",
        state={
            "cliente": "Textil Norte S.A.",
            "segmento": "Empresas — Banca Corporativa",
            "exposicion_vigente_usd": 3_400_000,
            "producto_consultado": None,
            "dictamen_riesgos": None,
        },
    )

    # ── 6b · Tres mensajes: confirmar el producto, confirmar el dictamen y pedir un resumen ──
    turns = [
        "Queda confirmado: el producto es línea de capital de trabajo a 18 meses.",
        "El dictamen de la Gerencia de Riesgos se emitió el 10 de julio.",
        "¿Podés confirmarme los datos que registré en esta sesión?",
    ]
    for turn in turns:
        answer = await get_response("oficial_cuentas_44", "session_003", turn, runner=stateful_runner)
        print(f"\nUsuario: {turn}")
        print(f"Agente: {answer}")

    # ── 6c · Leer el estado al final: ¿quedaron registrados los dos campos? ──
    final_session = await session_service.get_session(
        app_name="asistente_normativa", user_id="oficial_cuentas_44", session_id="session_003"
    )
    print("\nEstado final de la sesión de la operación:")
    print(f"  {final_session.state}")
    pendientes = [c for c in ("producto_consultado", "dictamen_riesgos") if final_session.state.get(c) is None]
    print(f"  Campos que siguen en None: {pendientes or 'ninguno'}")


if __name__ == "__main__":
    asyncio.run(stateful_session_demo())
