# adk_nativo.py — llama a los evaluadores NATIVOS de ADK 2.12 sobre trazas armadas
# a mano. Sirve para comparar, con la misma traza, las métricas del módulo
# (planificacion.py) contra las que ya trae ADK, sin pagar un solo token de modelo.
#
#   tool_trajectory_avg_score   TrajectoryEvaluator   local, determinista, 1.0 o 0.0
#                               por invocación: EXACT / IN_ORDER / ANY_ORDER
#   response_match_score        RougeEvaluator        local, determinista, ROUGE-1 (F1)
#
# Ambos reciben listas de `Invocation` (la unidad que ADK usa para evaluar un
# turno del usuario) y devuelven un EvaluationResult; acá se reduce a un float.
from __future__ import annotations

from google.genai import types

from google.adk.evaluation.eval_case import IntermediateData, Invocation
from google.adk.evaluation.eval_metrics import EvalMetric, ToolTrajectoryCriterion
from google.adk.evaluation.final_response_match_v1 import RougeEvaluator
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator

from .planificacion import Llamada

# Los tres modos de comparar trayectorias que trae ADK (ToolTrajectoryCriterion.MatchType):
#   EXACT      misma secuencia: mismas llamadas, mismo orden, sin llamadas de más
#   IN_ORDER   las esperadas aparecen en ese orden, admitiendo llamadas intercaladas
#   ANY_ORDER  las esperadas aparecen, en cualquier orden y con llamadas de más
MODOS = ("EXACT", "IN_ORDER", "ANY_ORDER")


# ── Armar la traza en el formato de ADK ─────────────────────────────────────

def a_invocacion(llamadas: list[Llamada], respuesta: str = "", pregunta: str = "") -> Invocation:
    """Arma la Invocation que ADK espera a partir de lo que hizo el agente."""
    return Invocation(
        invocation_id="m9",
        user_content=types.Content(role="user", parts=[types.Part(text=pregunta)]),
        final_response=types.Content(role="model", parts=[types.Part(text=respuesta)]),
        intermediate_data=IntermediateData(tool_uses=[
            types.FunctionCall(name=c["tool"], args=dict(c.get("params") or {}))
            for c in llamadas
        ]),
    )


# ── Las dos métricas nativas, sin modelo ────────────────────────────────────

def trayectoria(predichas: list[Llamada], esperadas: list[Llamada],
                modo: str = "EXACT", ignorar_args: bool = False) -> float:
    """tool_trajectory_avg_score de ADK para UNA invocación: 1.0 o 0.0.
    `modo`: ver MODOS. `ignorar_args=True` compara solo los nombres de herramienta."""
    if modo not in MODOS:
        raise ValueError(f"modo debe ser uno de {MODOS}")
    criterio = ToolTrajectoryCriterion(
        threshold=1.0,
        match_type=getattr(ToolTrajectoryCriterion.MatchType, modo),
        ignore_args=ignorar_args,
    )
    evaluador = TrajectoryEvaluator(eval_metric=EvalMetric(
        metric_name="tool_trajectory_avg_score", threshold=1.0, criterion=criterio))
    # Primero lo que hizo el agente, después lo esperado (es el orden que pide ADK).
    r = evaluador.evaluate_invocations([a_invocacion(predichas)], [a_invocacion(esperadas)])
    return float(r.overall_score)


def rouge1(respuesta: str, referencia: str) -> float:
    """response_match_score de ADK: ROUGE-1 (F1 de unigramas).
    OJO con el español: el tokenizador de rouge_score reemplaza todo lo que no
    sea [a-z0-9] por un espacio, así que 'días' se parte en 'd' + 'as'."""
    evaluador = RougeEvaluator(EvalMetric(metric_name="response_match_score", threshold=0.8))
    r = evaluador.evaluate_invocations(
        [a_invocacion([], respuesta)], [a_invocacion([], referencia)])
    return float(r.overall_score)
