# Tests de la biblioteca de métricas. Cada test fija una decisión de definición:
# si cambia una fórmula, el test dice cuál era la intención.
import math

import pytest

from metricas import adk_nativo
from metricas import agregacion as ag
from metricas import planificacion as m

# Las dos llamadas del caso central (la taza rota) y las herramientas irreversibles.
LOOKUP = {"tool": "lookup_order", "params": {"order_id": "A89268"}}
REEMBOLSO = {"tool": "issue_refund",
             "params": {"order_id": "A89268", "sku": "MUG-001", "amount": 19.99}}
IRREVERSIBLES = {"issue_refund", "cancel_order"}


# ── Los tres casos vacíos ───────────────────────────────────────────────────

def test_nada_esperado_y_nada_hecho_es_perfecto():
    assert m.tool_recall([], []) == 1.0
    assert m.tool_precision([], []) == 1.0


def test_nada_esperado_pero_el_agente_actuo_es_precision_cero():
    # La convención simple devuelve 1.0/1.0 acá; esta versión no premia el exceso.
    assert m.tool_recall([REEMBOLSO], []) == 1.0
    assert m.tool_precision([REEMBOLSO], []) == 0.0


def test_algo_esperado_y_el_agente_no_hizo_nada():
    assert m.tool_recall([], [LOOKUP]) == 0.0
    assert m.tool_precision([], [LOOKUP]) == 0.0


# ── recall / precisión: ven nombres, no repeticiones ni parámetros ──────────

def test_recall_y_precision_son_ciegos_al_doble_reembolso():
    esperadas = [LOOKUP, REEMBOLSO]
    doble = [LOOKUP, REEMBOLSO, REEMBOLSO]
    assert m.tool_recall(doble, esperadas) == 1.0
    assert m.tool_precision(doble, esperadas) == 1.0


def test_recall_y_precision_son_ciegos_al_monto_equivocado():
    esperadas = [LOOKUP, REEMBOLSO]
    mal = [LOOKUP, {**REEMBOLSO, "params": {**REEMBOLSO["params"], "amount": 39.99}}]
    assert m.tool_recall(mal, esperadas) == 1.0
    assert m.tool_precision(mal, esperadas) == 1.0
    assert m.param_accuracy(mal, esperadas) == 0.5  # solo lookup_order acierta


def test_precision_baja_con_una_herramienta_de_mas():
    extra = {"tool": "get_shipment_status", "params": {"order_id": "A89268"}}
    assert m.tool_precision([LOOKUP, extra, REEMBOLSO], [LOOKUP, REEMBOLSO]) == pytest.approx(2 / 3)


# ── param_accuracy ──────────────────────────────────────────────────────────

def test_param_accuracy_compara_numeros_a_dos_decimales():
    a = {"tool": "issue_refund", "params": {"amount": 19.99}}
    b = {"tool": "issue_refund", "params": {"amount": 19.990}}
    assert m.param_accuracy([a], [b]) == 1.0


def test_param_accuracy_empareja_uno_a_uno():
    # Dos llamadas esperadas idénticas no se cumplen con una sola predicha.
    assert m.param_accuracy([REEMBOLSO], [REEMBOLSO, REEMBOLSO]) == 0.5
    assert m.param_accuracy([REEMBOLSO, REEMBOLSO], [REEMBOLSO, REEMBOLSO]) == 1.0


def test_param_accuracy_sin_llamadas_esperadas_es_uno():
    assert m.param_accuracy([REEMBOLSO], []) == 1.0


# ── phrase_recall ───────────────────────────────────────────────────────────

def test_phrase_recall_normaliza_tildes_moneda_y_coma_decimal():
    resp = "Procesé el reembolso de $19,99. Llega en 3 a 5 días hábiles."
    assert m.phrase_recall(resp, ["19.99", "dias habiles"]) == 1.0


def test_phrase_recall_parcial_y_vacio():
    assert m.phrase_recall("Listo, ya está resuelto.", ["19.99", "A89268"]) == 0.0
    assert m.phrase_recall("lo que sea", []) == 1.0


# ── task_success y conteo ───────────────────────────────────────────────────

def test_task_success_exige_las_cuatro():
    assert m.task_success(1, 1, 1, 1) is True
    assert m.task_success(1, 1, 1, 0.5) is False
    assert m.task_success(0.9, 1, 1, 1, umbral=0.9) is True


def test_acciones_irreversibles_cuenta_repetidas_y_con_otro_monto():
    esperadas = [LOOKUP, REEMBOLSO]
    assert m.acciones_irreversibles_no_autorizadas([LOOKUP, REEMBOLSO], esperadas, IRREVERSIBLES) == 0
    assert m.acciones_irreversibles_no_autorizadas([LOOKUP, REEMBOLSO, REEMBOLSO], esperadas, IRREVERSIBLES) == 1
    otro_monto = {**REEMBOLSO, "params": {**REEMBOLSO["params"], "amount": 39.99}}
    assert m.acciones_irreversibles_no_autorizadas([LOOKUP, otro_monto], esperadas, IRREVERSIBLES) == 1
    # lookup_order no es irreversible: llamarlo de más no cuenta.
    assert m.acciones_irreversibles_no_autorizadas([LOOKUP, LOOKUP, REEMBOLSO], esperadas, IRREVERSIBLES) == 0


# ── Agregación y confiabilidad ──────────────────────────────────────────────

def test_pass_k_con_valores_calculados_a_mano():
    # n=5, c=3, k=2 → pass^2 = C(3,2)/C(5,2) = 3/10; pass@2 = 1 − C(2,2)/C(5,2) = 9/10
    assert ag.pass_hat_k(5, 3, 2) == pytest.approx(0.3)
    assert ag.pass_at_k(5, 3, 2) == pytest.approx(0.9)


def test_pass_k_k1_es_la_tasa_de_exito():
    assert ag.pass_hat_k(8, 6, 1) == pytest.approx(6 / 8)
    assert ag.pass_at_k(8, 6, 1) == pytest.approx(6 / 8)


def test_pass_k_extremos():
    assert ag.pass_hat_k(6, 6, 6) == 1.0
    assert ag.pass_hat_k(6, 5, 6) == 0.0
    assert ag.pass_at_k(6, 0, 3) == 0.0


def test_pass_hat_k_nunca_supera_pass_at_k():
    for c in range(0, 9):
        assert ag.pass_hat_k(8, c, 4) <= ag.pass_at_k(8, c, 4) + 1e-12


def test_pass_k_valida_argumentos():
    with pytest.raises(ValueError):
        ag.pass_hat_k(4, 2, 5)
    with pytest.raises(ValueError):
        ag.pass_at_k(4, 5, 2)


def test_promedio_por_tarea_pesa_cada_tarea_igual():
    # tarea A: 6/6; tarea B: 0/2 → promedio por tarea (1.0 + 0.0)/2, no 6/8
    assert ag.promedio_por_tarea(ag.pass_hat_k, {"A": (6, 6), "B": (2, 0)}, 1) == pytest.approx(0.5)


def test_wilson_valores_conocidos():
    lo, hi = ag.wilson(8, 10)
    assert lo == pytest.approx(0.490, abs=2e-3) and hi == pytest.approx(0.943, abs=2e-3)
    assert ag.wilson(0, 0) == (0.0, 1.0)
    lo, hi = ag.wilson(10, 10)
    assert hi == 1.0 and lo < 1.0  # con 10/10 el límite inferior NO es 1.0


def test_cohen_kappa_ejemplo_calculado_a_mano():
    juez = [True, True, False, False]
    humano = [True, False, False, False]
    assert ag.cohen_kappa(juez, humano) == pytest.approx(0.5)
    assert ag.acuerdo(juez, humano) == pytest.approx(0.75)
    assert ag.matriz_confusion(juez, humano) == {"vp": 1, "fp": 1, "fn": 0, "vn": 2}


def test_cohen_kappa_indefinido_si_todo_es_igual():
    assert math.isnan(ag.cohen_kappa([True, True], [True, True]))


# ── Evaluadores nativos de ADK 2.12 (locales, sin modelo) ───────────────────

ESPERADAS = [LOOKUP, REEMBOLSO]


@pytest.mark.parametrize("nombre,predichas,exact,in_order,any_order", [
    ("perfecta",      [LOOKUP, REEMBOLSO],            1, 1, 1),
    ("doble",         [LOOKUP, REEMBOLSO, REEMBOLSO], 0, 1, 1),   # IN_ORDER/ANY_ORDER no lo ven
    ("reintento",     [LOOKUP, LOOKUP, REEMBOLSO],    0, 1, 1),
    ("invertida",     [REEMBOLSO, LOOKUP],            0, 0, 1),
    ("atajo",         [REEMBOLSO],                    0, 0, 0),
])
def test_trayectoria_nativa_de_adk(nombre, predichas, exact, in_order, any_order):
    assert adk_nativo.trayectoria(predichas, ESPERADAS, "EXACT") == exact
    assert adk_nativo.trayectoria(predichas, ESPERADAS, "IN_ORDER") == in_order
    assert adk_nativo.trayectoria(predichas, ESPERADAS, "ANY_ORDER") == any_order


def test_trayectoria_con_esperado_vacio_IN_ORDER_y_ANY_ORDER_aprueban_por_vacuidad():
    assert adk_nativo.trayectoria([REEMBOLSO], [], "EXACT") == 0.0
    assert adk_nativo.trayectoria([REEMBOLSO], [], "IN_ORDER") == 1.0
    assert adk_nativo.trayectoria([REEMBOLSO], [], "ANY_ORDER") == 1.0


def test_trayectoria_ignorar_args():
    mal = [LOOKUP, {**REEMBOLSO, "params": {**REEMBOLSO["params"], "amount": 39.99}}]
    assert adk_nativo.trayectoria(mal, ESPERADAS, "EXACT") == 0.0
    assert adk_nativo.trayectoria(mal, ESPERADAS, "EXACT", ignorar_args=True) == 1.0


def test_trayectoria_rechaza_modo_desconocido():
    with pytest.raises(ValueError):
        adk_nativo.trayectoria([], [], "ALGUNO")


def test_rouge1_identico_y_el_tokenizador_rompe_las_tildes():
    assert adk_nativo.rouge1("el reembolso fue procesado", "el reembolso fue procesado") == 1.0
    # El tokenizador de rouge_score solo conoce [a-z0-9]: con tilde ≠ sin tilde.
    assert adk_nativo.rouge1("días hábiles", "dias habiles") == 0.0
