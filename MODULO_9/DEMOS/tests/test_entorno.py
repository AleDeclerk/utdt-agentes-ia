# Tests del entorno: las herramientas cambian el estado como se espera y el
# corpus es coherente consigo mismo (repetir la trayectoria esperada sobre una
# tienda nueva produce exactamente el estado final esperado).
import pytest

from entorno.corpus import CORPUS, POR_ID
from entorno.tienda import IRREVERSIBLES, Tienda, crear_agente, crear_herramientas, verificar_credenciales


def herramientas(t):
    """Las herramientas de la tienda `t`, por nombre, para llamarlas como funciones."""
    return {h.name: h.func for h in crear_herramientas(t)}


# ── Las herramientas cambian el estado como se espera ───────────────────────


def test_reembolso_registra_el_estado():
    t = Tienda()
    h = herramientas(t)
    assert h["issue_refund"]("A89268", "MUG-001", 19.99)["ok"] is True
    assert t.estado() == {"reembolsos": [("A89268", "MUG-001", 19.99)], "cancelados": []}


def test_reembolso_rechaza_pedido_inexistente_y_monto_excesivo():
    t = Tienda()
    h = herramientas(t)
    assert h["issue_refund"]("A89286", "MUG-001", 19.99)["ok"] is False
    assert h["issue_refund"]("A89268", "MUG-001", 99.0)["ok"] is False
    assert t.reembolsos == []


def test_cancelar_solo_funciona_en_processing():
    t = Tienda()
    h = herramientas(t)
    assert h["cancel_order"]("A89268")["ok"] is False      # entregado
    assert h["cancel_order"]("D31877")["ok"] is False      # enviado
    assert h["cancel_order"]("C55120")["ok"] is True       # en proceso
    assert t.estado()["cancelados"] == ["C55120"]


def test_cada_tienda_es_independiente():
    a, b = Tienda(), Tienda()
    herramientas(a)["cancel_order"]("C55120")
    assert b.pedidos["C55120"]["estado"] == "processing"


def test_lookup_de_pedido_inexistente():
    assert herramientas(Tienda())["lookup_order"]("A89286") == {"found": False, "order_id": "A89286"}


# ── El corpus es coherente consigo mismo ────────────────────────────────────

@pytest.mark.parametrize("caso", CORPUS, ids=lambda c: c.id)
def test_la_trayectoria_esperada_produce_el_estado_esperado(caso):
    t = Tienda()
    h = herramientas(t)
    for llamada in caso.esperadas:
        h[llamada["tool"]](**llamada["params"])
    esperado = {"reembolsos": sorted(caso.estado_esperado["reembolsos"]),
                "cancelados": sorted(caso.estado_esperado["cancelados"])}
    assert t.estado() == esperado


def test_las_herramientas_irreversibles_existen():
    assert IRREVERSIBLES <= set(herramientas(Tienda()))


def test_el_corpus_incluye_un_caso_sin_herramientas_esperadas():
    assert POR_ID["consulta_politica"].esperadas == []


# ── Credenciales y reintentos ───────────────────────────────────────────────


def test_sin_api_key_se_corta_con_un_mensaje_claro(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GOOGLE_API_KEY"):
        verificar_credenciales()


def test_con_api_key_no_corta(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "una-clave")
    verificar_credenciales()


def test_el_agente_reintenta_ante_cuota_excedida():
    modelo = crear_agente(Tienda()).model
    assert modelo.retry_options.http_status_codes == [429, 503]
    assert modelo.retry_options.attempts > 1
