# agent.py — el agente de soporte de la tienda, en el formato que ADK espera: un módulo
# `agent` que expone `root_agent`.
#
# Es el MISMO agente de las demostraciones (entorno/tienda.py): mismo modelo, misma
# instrucción (INSTRUCCION_V2) y las mismas seis herramientas. Lo único que cambia es cómo
# se ata al mundo, por una razón que solo aparece al evaluar con ADK:
#
#   `adk eval` y `AgentEvaluator` cargan el agente UNA vez y lo corren sobre muchos casos
#   (y, con num_runs, varias veces cada uno), en paralelo. Si todos compartieran una única
#   `Tienda`, un reembolso o una cancelación de un caso cambiaría el mundo del siguiente:
#   `cancel_order` deja el pedido C55120 en 'cancelled', y la segunda corrida de
#   `cancelar_en_proceso` ya no podría cancelarlo. Cada caso tiene que empezar con el mundo
#   intacto, y cada sesión de ADK corresponde a una corrida.
from __future__ import annotations

from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools import BaseTool, ToolContext

from entorno.tienda import INSTRUCCION_V2, MODELO, Tienda, crear_herramientas


# ── Un mundo por sesión ─────────────────────────────────────────────────────

# session.id → {nombre de herramienta: función}, atadas a la Tienda de ESA sesión.
# Crece una entrada por corrida y no se limpia: alcanza para una evaluación.
_MUNDOS: dict[str, dict[str, Any]] = {}


def _ejecutar_en_el_mundo_de_la_sesion(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict[str, Any]]:
    """`before_tool_callback`: ADK lo llama antes de ejecutar cada herramienta (con estos
    nombres de parámetro, por palabra clave). Si devuelve un dict, ADK lo usa como
    resultado de la herramienta y NO la ejecuta: acá se ejecuta la misma herramienta, pero
    contra la tienda de la sesión actual."""
    sesion = tool_context.session.id
    if sesion not in _MUNDOS:
        _MUNDOS[sesion] = {h.name: h.func for h in crear_herramientas(Tienda())}
    try:
        return _MUNDOS[sesion][tool.name](**args)
    except Exception as e:   # argumentos de más o de menos: se le informa al modelo, como haría ADK
        return {"error": f"{type(e).__name__}: {e}"}


# ── El agente ───────────────────────────────────────────────────────────────

root_agent = Agent(
    name="SoporteTienda",
    model=MODELO,
    instruction=INSTRUCCION_V2,
    # Estas herramientas, atadas a una tienda descartable, solo aportan lo que ve el modelo
    # (nombre, descripción y parámetros). Quien las ejecuta de verdad es el callback.
    tools=crear_herramientas(Tienda()),
    before_tool_callback=_ejecutar_en_el_mundo_de_la_sesion,
)
