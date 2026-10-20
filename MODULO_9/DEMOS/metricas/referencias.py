# referencias.py — dos implementaciones «anteriores» de recall / precisión, tal como
# estaban escritas, para compararlas con la definición de planificacion.py.
#
#   tool_metrics_simple   la convención simple: si no se esperaba ninguna herramienta
#                         devuelve 1.0 / 1.0 de inmediato, sin mirar qué hizo el agente.
#   tool_metrics_v1       el código de la primera versión del módulo: recall 1.0 si no se
#                         esperaba nada, pero precisión 0.0 si el agente no llamó nada
#                         (castiga al agente que acertó al no hacer nada).
#
# No se usan en las demos con agente: existen para mostrar, con los mismos tres casos
# vacíos, dónde cada versión se comporta distinto (sección 6 de la demo 1 y tests de
# tests/test_zoologico.py). Reciben NOMBRES de herramienta, no llamadas completas.
from __future__ import annotations


# ── La convención simple: lista vacía ⇒ todo en 1.0 ─────────────────────────

def tool_metrics_simple(pred_tools: list[str], expected_calls: list[dict]) -> dict:
    """Si no se esperaba nada, devuelve 1.0 / 1.0 aunque el agente haya actuado:
    premia el exceso porque nunca llega a mirar qué hizo."""
    expected_names = [c.get("tool") for c in expected_calls]
    if not expected_names:
        return {"tool_recall": 1.0, "tool_precision": 1.0}
    pred_set = set(pred_tools)
    exp_set = set(expected_names)
    tp = len(exp_set & pred_set)
    recall = tp / len(exp_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    return {"tool_recall": recall, "tool_precision": precision}


# ── La primera versión del módulo ───────────────────────────────────────────

def tool_metrics_v1(pred_tools: list[str], expected_calls: list[dict]) -> dict:
    """Recall 1.0 si no se esperaba nada (bien), pero precisión 0.0 cuando el agente
    no llamó nada: también castiga a quien correctamente no hizo nada."""
    exp_set = set(c.get("tool") for c in expected_calls)
    pred_set = set(pred_tools)
    tp = len(exp_set & pred_set)
    return {
        "tool_recall": tp / len(exp_set) if exp_set else 1.0,
        "tool_precision": tp / len(pred_set) if pred_set else 0.0,
    }
