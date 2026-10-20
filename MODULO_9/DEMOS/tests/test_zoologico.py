# Estos tests fijan lo que la guía afirma sobre la demo 1. Si alguien cambia una métrica
# o una corrida y una afirmación deja de ser cierta, falla acá.
import pytest

from entorno import zoologico as z
from metricas.referencias import tool_metrics_simple, tool_metrics_v1
from metricas import planificacion as m
from metricas import adk_nativo

# La matriz se calcula una sola vez: medidas por corrida y resumen por métrica.
R = z.matriz()
MED = R["medidas"]
RES = R["resumen"]


# ── Las once corridas y qué métrica ve qué falla ────────────────────────────

def test_las_etiquetas_estan_declaradas_de_antemano():
    aceptables = [c.id for c in z.CORRIDAS if c.aceptable]
    assert len(z.CORRIDAS) == 11 and len(aceptables) == 6
    assert set(aceptables) == {"perfecta", "reintento_valido", "consulta_extra",
                               "atajo_sin_verificar", "orden_invertido", "parafrasis_correcta"}


def test_ninguna_metrica_sola_acierta_las_once():
    individuales = {k: v for k, v in RES.items() if not k.startswith("panel")}
    assert min(v["errores"] for v in individuales.values()) >= 2
    assert RES["estado final del mundo"]["errores"] == 2   # la mejor métrica individual


def test_el_panel_de_tres_falla_solo_en_afirma_de_mas():
    p = RES[z.PANEL[0]]
    assert p["errores"] == 1 and p["falsos_aprobados"] == ["afirma_de_mas"] and p["falsos_rechazos"] == []


def test_recall_y_precision_son_ciegos_al_monto_y_al_doble_reembolso():
    for corrida in ("monto_equivocado", "doble_reembolso"):
        assert MED[corrida]["tool_recall"] == 1.0 and MED[corrida]["tool_precision"] == 1.0
    assert MED["monto_equivocado"]["param_accuracy"] == 0.5


def test_solo_EXACT_ve_el_doble_reembolso_entre_las_trayectorias_de_ADK():
    assert MED["doble_reembolso"]["traj_exact"] == 0.0
    assert MED["doble_reembolso"]["traj_in_order"] == 1.0
    assert MED["doble_reembolso"]["traj_any_order"] == 1.0


def test_EXACT_rechaza_cuatro_caminos_validos():
    rechazadas = set(RES["trayectoria EXACT (ADK)"]["falsos_rechazos"])
    assert rechazadas == {"reintento_valido", "consulta_extra", "atajo_sin_verificar", "orden_invertido"}


def test_ROUGE_aprueba_el_monto_equivocado_y_reprueba_la_parafrasis_correcta():
    assert MED["monto_equivocado"]["rouge1"] >= 0.8
    assert MED["accion_alucinada"]["rouge1"] >= 0.8
    assert MED["parafrasis_correcta"]["rouge1"] < 0.8


def test_phrase_recall_no_ve_la_accion_alucinada():
    assert MED["accion_alucinada"]["phrase_recall"] == 1.0
    assert MED["accion_alucinada"]["tool_recall"] == 0.5     # el recall de herramientas sí


def test_el_estado_final_es_ciego_a_la_respuesta_evasiva_y_a_la_mentira_chica():
    assert MED["respuesta_evasiva"]["estado_ok"] is True
    assert MED["afirma_de_mas"]["estado_ok"] is True


# ── Los tres casos vacíos: convención simple, v1 y V2 ───────────────────────

LOOKUP = {"tool": "lookup_order", "params": {"order_id": "A89268"}}
REEMBOLSO = {"tool": "issue_refund", "params": {"order_id": "A89268", "sku": "MUG-001", "amount": 19.99}}


def test_casos_vacios_la_convencion_simple_premia_el_exceso():
    assert tool_metrics_simple(["issue_refund"], []) == {"tool_recall": 1.0, "tool_precision": 1.0}


def test_casos_vacios_la_v1_castiga_al_agente_que_no_hace_nada_cuando_no_habia_nada_que_hacer():
    assert tool_metrics_v1([], []) == {"tool_recall": 1.0, "tool_precision": 0.0}


def test_casos_vacios_la_v2_resuelve_los_tres():
    assert (m.tool_recall([], []), m.tool_precision([], [])) == (1.0, 1.0)
    assert (m.tool_recall([REEMBOLSO], []), m.tool_precision([REEMBOLSO], [])) == (1.0, 0.0)
    assert (m.tool_recall([], [LOOKUP]), m.tool_precision([], [LOOKUP])) == (0.0, 0.0)


@pytest.mark.parametrize("modo,esperado", [("EXACT", 0.0), ("IN_ORDER", 1.0), ("ANY_ORDER", 1.0)])
def test_casos_vacios_en_ADK_IN_ORDER_y_ANY_ORDER_aprueban_aunque_el_agente_actue(modo, esperado):
    assert adk_nativo.trayectoria([REEMBOLSO], [], modo) == esperado
