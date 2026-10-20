# Los ítems del juez: etiquetas coherentes y, sobre todo, una traza BIEN armada.
# Si una llamada y su respuesta no quedan emparejadas por id, el juez evalúa una traza
# distinta de la que se cree (pasó en la primera corrida de la demo 2).
from google.adk.evaluation.eval_case import get_all_tool_calls_with_responses

from entorno.juez_items import ITEMS, TRAZAS, invocacion


# ── La traza está bien armada ───────────────────────────────────────────────

def test_cada_llamada_queda_emparejada_con_su_propia_respuesta():
    inv = invocacion(next(i for i in ITEMS if i.traza == "taza"))
    pares = get_all_tool_calls_with_responses(inv.intermediate_data)
    assert [(c.name, r.name) for c, r in pares] == [("lookup_order", "lookup_order"),
                                                    ("issue_refund", "issue_refund")]
    assert pares[0][1].response["found"] is True          # la consulta devuelve el pedido, no el reembolso


def test_todas_las_trazas_se_emparejan():
    for item in ITEMS:
        pares = get_all_tool_calls_with_responses(invocacion(item).intermediate_data)
        assert len(pares) == len(TRAZAS[item.traza])
        assert all(c.name == r.name for c, r in pares), item.id


# ── Las etiquetas humanas ───────────────────────────────────────────────────

def test_las_etiquetas_estan_balanceadas_y_son_catorce():
    assert len(ITEMS) == 14
    assert sum(i.alucina for i in ITEMS) == 7
    assert [i.id for i in ITEMS if not i.cita_pedido] == ["sin_numero_de_pedido"]


def test_la_traza_sin_reembolso_no_contiene_issue_refund():
    inv = invocacion(next(i for i in ITEMS if i.id == "accion_inventada"))
    assert [c.name for c, _ in get_all_tool_calls_with_responses(inv.intermediate_data)] == ["lookup_order"]
