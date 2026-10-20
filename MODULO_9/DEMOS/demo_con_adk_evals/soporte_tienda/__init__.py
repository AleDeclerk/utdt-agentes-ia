# __init__.py — hace de `soporte_tienda` un agente que ADK sabe cargar.
#
# `adk eval`, `adk web` y `AgentEvaluator` importan este paquete y buscan en él un módulo
# `agent` que exponga `root_agent`. Antes de importarlo se agregan dos carpetas al sys.path:
#   - DEMOS/, para que el agente y las métricas propias reutilicen `entorno/` y `metricas/`
#     sin copiarlos;
#   - demo_con_adk_evals/, donde vive `metricas_propias.py`. ADK importa las métricas propias
#     por su ruta (`metricas_propias.tool_recall`, con importlib) y `adk eval` no pone esa
#     carpeta en el sys.path: carga este paquete bajo el nombre `agent`, así que el nombre
#     `soporte_tienda` no existe en ese proceso.
#
# También se instala acá el parser tolerante del juez de rúbricas (metricas/juez_tolerante.py).
# El parser de ADK descarta SIN AVISO las muestras en que el juez escribe el razonamiento en
# varias líneas (algo que Gemini 2.5 Flash hace seguido), y el puntaje se calcula con menos
# muestras de las pedidas. Se instala al cargar el agente porque eso ocurre antes de cualquier
# evaluación, con cualquiera de los ejecutores; y al terminar el proceso se imprime cuántas
# muestras hubo, cuántas se rescataron y cuántas se perdieron.
import atexit
import sys
from pathlib import Path

for _ruta in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

from metricas import juez_tolerante  # noqa: E402

juez_tolerante.instalar()
atexit.register(lambda: print(f"[juez] {juez_tolerante.resumen()}") if juez_tolerante.STATS["muestras"] else None)

from . import agent  # noqa: E402,F401
