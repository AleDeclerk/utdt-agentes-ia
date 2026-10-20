# evaluar_con_pytest.py — la misma evaluación que `adk eval`, corrida desde pytest con
# `AgentEvaluator.evaluate`. Es la manera natural cuando la evaluación forma parte del
# conjunto de pruebas del proyecto.
#
# Qué agrega respecto de `adk eval`:
#   - `num_runs`: repite cada caso N veces (por defecto 2). Para cada métrica junta TODOS los
#     puntajes de todas las invocaciones y de todas las corridas, calcula la media y la
#     compara con el umbral. No calcula pass^k ni intervalos de confianza.
#   - Si una métrica no llega al umbral, la prueba FALLA con la lista de lo que falló; ese
#     mensaje es el resultado, no un error del script. Se usa el test_config.json que está
#     junto al conjunto de casos (el veredicto). El diagnóstico estricto
#     (test_config_diagnostico.json) solo se puede correr con `adk eval --config_file_path`.
#
# NO se llama test_*.py a propósito: `pytest` desde DEMOS/ recorre todas las carpetas, y una
# prueba que llama al modelo se colaría en la suite de pruebas que cuestan $0. Se corre
# a mano, nombrando el archivo (pytest recoge un archivo pasado explícitamente):
#
#   python -m pytest demo_con_adk_evals/evaluar_con_pytest.py -s -q
#   NUM_RUNS=1 python -m pytest demo_con_adk_evals/evaluar_con_pytest.py -s -q    # la mitad
#
# CUESTA DINERO: 7 casos × NUM_RUNS corridas contra el modelo, más los jueces (del orden de
# $0.25 por cada corrida de los 7 casos; con el valor por defecto, NUM_RUNS=2, unos $0.5).
import asyncio
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))       # para que ADK pueda importar `soporte_tienda`

from google.adk.evaluation.agent_evaluator import AgentEvaluator  # noqa: E402


def test_soporte_tienda_con_agent_evaluator():
    # La configuración (test_config.json) se busca en la misma carpeta que el conjunto de casos.
    asyncio.run(AgentEvaluator.evaluate(
        agent_module="soporte_tienda",
        eval_dataset_file_path_or_dir=str(AQUI / "soporte_tienda" / "soporte_tienda.evalset.json"),
        num_runs=int(os.environ.get("NUM_RUNS", "2")),
        print_detailed_results=True,
    ))
