"""Punto de entrada para `adk web agentes` (desde la raíz de la demo, con ./run.sh web). Requiere el Neo4j de la demo levantado."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # raíz de la demo: comun, herramientas, agente

from agente import construir_agente  # noqa: E402

root_agent = construir_agente()
