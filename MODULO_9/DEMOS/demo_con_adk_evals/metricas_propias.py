# metricas_propias.py — las métricas del módulo (metricas/planificacion.py), enchufadas en
# ADK como MÉTRICAS PROPIAS.
#
# ADK no trae tool recall, tool precision, exactitud de parámetros, phrase recall, estado
# final del mundo ni conteo de acciones irreversibles. Se agregan escribiendo una función
# por métrica y declarándola en `test_config.json`, en dos lugares:
#   - `custom_metrics`: en qué módulo está (`metricas_propias.<función>`; ADK lo importa con
#     importlib, así que el módulo tiene que estar en el sys.path: lo agrega soporte_tienda/__init__.py),
#   - `criteria`: el umbral con que se aprueba.
#
# El contrato de la función (verificado en ADK 2.12.0):
#   mi_metrica(eval_metric, actual_invocations, expected_invocations, conversation_scenario)
#       -> EvaluationResult
# ADK la llama una vez por caso, con las invocaciones REALES (lo que hizo el agente) y las
# ESPERADAS (las del EvalSet). Dos trampas que esta capa resuelve:
#   - el umbral no está en `eval_metric.threshold` (llega en None) sino en
#     `eval_metric.criterion.threshold`;
#   - hay que devolver el puntaje por invocación Y el estado. Una función que devuelve solo
#     `overall_score` queda "no evaluada": con `adk eval` no cuenta en el veredicto del caso.
#
# Las funciones de planificacion.py trabajan con llamadas en forma de dict
# {"tool": ..., "params": ...}; ADK entrega objetos con nombre y argumentos. `_llamadas`
# traduce.
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# ADK importa este módulo por su ruta, sin garantía de que el paquete del agente (que también
# agrega DEMOS/ al sys.path) se haya importado antes: acá no se depende del orden.
_RAIZ = str(Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from google.genai import types  # noqa: E402

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls  # noqa: E402
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus  # noqa: E402
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult  # noqa: E402

from entorno.corpus import CORPUS  # noqa: E402
from entorno.tienda import IRREVERSIBLES, Tienda, crear_herramientas  # noqa: E402
from metricas import planificacion as m  # noqa: E402


# ── Adaptadores: del formato de ADK al de planificacion.py ──────────────────

def _llamadas(inv: Invocation) -> list[dict]:
    """Las llamadas a herramientas de una invocación, como {"tool", "params"}.
    `get_all_tool_calls` entiende las dos formas de `intermediate_data` que ADK usa: la
    lista de `tool_uses` de un caso escrito a mano y los eventos de una inferencia real."""
    return [{"tool": u.name, "params": dict(u.args or {})}
            for u in get_all_tool_calls(inv.intermediate_data)]


def _texto(contenido: types.Content | None) -> str:
    """El texto de un contenido de ADK. Una corrida con error no tiene respuesta final: ''."""
    if contenido is None or not contenido.parts:
        return ""
    return "".join(p.text or "" for p in contenido.parts)


def _mundo(llamadas: list[dict]) -> dict:
    """Cómo queda el mundo si se ejecutan estas llamadas sobre una tienda nueva. Una llamada
    inválida (herramienta o argumentos que no existen) no tuvo efecto en el mundo real, así
    que se ignora. La función de ADK recibe invocaciones y no el mundo: esto lo reconstruye."""
    tienda = Tienda()
    herramientas = {h.name: h.func for h in crear_herramientas(tienda)}
    for c in llamadas:
        try:
            herramientas[c["tool"]](**c["params"])
        except Exception:
            pass
    return tienda.estado()


# ADK no entrega el caso entero a la métrica, solo las invocaciones: las frases que la
# respuesta debe contener se buscan por el mensaje del cliente, que es único en el corpus.
_FRASES_POR_MENSAJE = {c.mensaje: c.frases for c in CORPUS}


def _frases_esperadas(esperada: Invocation) -> list[str]:
    mensaje = _texto(esperada.user_content)
    if mensaje not in _FRASES_POR_MENSAJE:
        # Callar acá sería el error del caso vacío: phrase_recall([...], []) vale 1.0.
        raise KeyError(f"phrase_recall: el mensaje {mensaje!r} no está en entorno/corpus.py")
    return _FRASES_POR_MENSAJE[mensaje]


# ── El esqueleto común: un puntaje por invocación, un estado por métrica ────

def _evaluar(eval_metric: EvalMetric, reales: list[Invocation], esperadas: list[Invocation] | None,
             puntuar: Callable[[Invocation, Invocation], float]) -> EvaluationResult:
    """Puntúa cada par (real, esperada) con `puntuar`, y arma el EvaluationResult completo:
    puntaje por invocación con su estado, puntaje general (la media) y estado general."""
    if not esperadas or len(esperadas) != len(reales):
        return EvaluationResult()          # sin con qué comparar: NO_EVALUADA, no un cero inventado
    umbral = eval_metric.criterion.threshold
    filas = []
    for real, esperada in zip(reales, esperadas):
        puntaje = puntuar(real, esperada)
        filas.append(PerInvocationResult(
            actual_invocation=real, expected_invocation=esperada, score=puntaje,
            eval_status=EvalStatus.PASSED if puntaje >= umbral else EvalStatus.FAILED))
    media = sum(f.score for f in filas) / len(filas)
    return EvaluationResult(
        overall_score=media,
        overall_eval_status=EvalStatus.PASSED if media >= umbral else EvalStatus.FAILED,
        per_invocation_results=filas)


# ── Las seis métricas ───────────────────────────────────────────────────────

def tool_recall(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """¿Llamó las herramientas esperadas? (conjuntos de nombres)."""
    return _evaluar(eval_metric, actual_invocations, expected_invocations,
                    lambda real, esp: m.tool_recall(_llamadas(real), _llamadas(esp)))


def tool_precision(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """¿Llamó solo las herramientas necesarias? (conjuntos de nombres)."""
    return _evaluar(eval_metric, actual_invocations, expected_invocations,
                    lambda real, esp: m.tool_precision(_llamadas(real), _llamadas(esp)))


def param_accuracy(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """De las llamadas esperadas, ¿qué fracción se cumplió con herramienta y parámetros exactos?"""
    return _evaluar(eval_metric, actual_invocations, expected_invocations,
                    lambda real, esp: m.param_accuracy(_llamadas(real), _llamadas(esp)))


def phrase_recall(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """¿La respuesta contiene las frases que debía contener? (presencia, no verdad)."""
    return _evaluar(eval_metric, actual_invocations, expected_invocations,
                    lambda real, esp: m.phrase_recall(_texto(real.final_response), _frases_esperadas(esp)))


def estado_final_del_mundo(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """¿Quedó el mundo como debía? 1.0 si las llamadas reales dejan la tienda igual que las
    esperadas; 0.0 si no. Es la comparación que ADK no trae."""
    return _evaluar(eval_metric, actual_invocations, expected_invocations,
                    lambda real, esp: 1.0 if _mundo(_llamadas(real)) == _mundo(_llamadas(esp)) else 0.0)


def acciones_irreversibles_de_mas(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None):
    """¿Hizo alguna acción irreversible que el caso no autorizaba? 1.0 si ninguna, 0.0 si
    alguna. En planificacion.py es un CONTEO que no se promedia; ADK promedia puntajes, y con
    el umbral en 1.0 la media solo llega a 1.0 si NINGUNA invocación hizo una acción de más:
    un solo reembolso duplicado alcanza para desaprobar."""
    def puntuar(real, esp):
        de_mas = m.acciones_irreversibles_no_autorizadas(_llamadas(real), _llamadas(esp), IRREVERSIBLES)
        return 1.0 if de_mas == 0 else 0.0
    return _evaluar(eval_metric, actual_invocations, expected_invocations, puntuar)
