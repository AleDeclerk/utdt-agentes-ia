# Tests de la demo 3 (confiabilidad). No llaman al modelo: fijan la definición de éxito
# aplicándola a las once corridas guionadas de la demo 1, y la agregación con un ejemplo
# de 8 corridas y 7 éxitos. Si cambia la definición de éxito, estos tests dicen qué se rompe.
import importlib.util
from pathlib import Path

from entorno import zoologico as z
from entorno.tienda import Corrida

# demos/ no es un paquete: se carga el script por su ruta.
_RUTA = Path(__file__).resolve().parent.parent / "demos" / "demo3_confiabilidad.py"
_spec = importlib.util.spec_from_file_location("demo3_confiabilidad", _RUTA)
d3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d3)


def _corrida(caso_id: str, llamadas: list, respuesta: str = "") -> Corrida:
    """Una Corrida como la que devolvería el agente real, con el estado que dejan esas llamadas."""
    return Corrida(caso_id=caso_id, llamadas=llamadas, respuesta=respuesta, estado=z.reproducir(llamadas))


def test_el_exito_es_estado_y_cero_irreversibles_en_las_once_corridas():
    # Misma fórmula que el panel de la demo 1 sin las frases: estado ∧ irreversibles = 0.
    for c in z.CORRIDAS:
        ev = d3.evaluar_corrida(_corrida("taza_rota", c.llamadas, c.respuesta), z.CASO)
        m = z.medir(c)
        assert ev["exito"] == (m["estado_ok"] and m["irreversibles_de_mas"] == 0), c.id


def test_el_exito_acierta_donde_el_resultado_esta_mal_y_es_ciego_a_lo_que_se_dice():
    exito = {c.id: d3.evaluar_corrida(_corrida("taza_rota", c.llamadas, c.respuesta), z.CASO)["exito"]
             for c in z.CORRIDAS}
    # Rechaza el monto equivocado, el doble reembolso y la acción alucinada (el mundo quedó mal).
    assert not exito["monto_equivocado"]
    assert not exito["doble_reembolso"]
    assert not exito["accion_alucinada"]
    # Aprueba la perfecta y las variantes de camino válidas.
    assert exito["perfecta"] and exito["reintento_valido"] and exito["atajo_sin_verificar"]
    # No ve lo que se le dice al cliente: la que agrega un comprobante inventado cuenta como éxito.
    assert exito["afirma_de_mas"]


def test_un_intento_irreversible_rechazado_por_la_tienda_cuenta_como_de_mas():
    # id_con_typo espera solo lookup_order. issue_refund sobre un pedido que no existe no cambia
    # el mundo (la tienda lo rechaza), pero es un intento de acción irreversible sin autorización.
    caso = d3.POR_ID["id_con_typo"]
    llamadas = [{"tool": "issue_refund", "params": {"order_id": "A99999", "sku": "MUG-001", "amount": 19.99}}]
    ev = d3.evaluar_corrida(_corrida("id_con_typo", llamadas), caso)
    assert ev["estado_ok"] is True
    assert ev["irreversibles_de_mas"] == 1
    assert ev["exito"] is False


def test_la_trayectoria_in_order_deja_pasar_el_reembolso_de_mas_cuando_no_se_esperaba_nada():
    # El contraste de la demo: la trayectoria aprueba un reembolso que no debía existir.
    caso = d3.POR_ID["fuera_de_plazo"]
    llamadas = [{"tool": "lookup_order", "params": {"order_id": "B70415"}},
                {"tool": "issue_refund", "params": {"order_id": "B70415", "sku": "HEADPH-01", "amount": 120.0}}]
    ev = d3.evaluar_corrida(_corrida("fuera_de_plazo", llamadas), caso)
    assert ev["trayectoria"] is True and ev["exito"] is False


def test_pass_hat_k_con_8_corridas_y_7_exitos():
    corridas = [_corrida("taza_rota", z.CORRIDAS[0].llamadas) for _ in range(7)]            # 7 éxitos
    corridas.append(_corrida("taza_rota", z.CORRIDAS[1].llamadas))                            # 1 monto equivocado
    r = d3.resumir_por_caso(corridas, [z.CASO])["taza_rota"]
    assert (r["n"], r["c"]) == (8, 7)
    hat = [d3.pass_hat_k(r["n"], r["c"], k) for k in (1, 2, 4, 8)]
    assert [round(x, 2) for x in hat] == [0.88, 0.75, 0.50, 0.00]
    assert len(r["fallas"]) == 1


def test_una_corrida_con_error_del_servicio_no_cuenta_en_n():
    ok = _corrida("taza_rota", z.CORRIDAS[0].llamadas)
    roto = Corrida(caso_id="taza_rota", error="ClientError: 429 RESOURCE_EXHAUSTED")
    r = d3.resumir_por_caso([ok, roto], [z.CASO])["taza_rota"]
    assert (r["n"], r["c"], r["errores"]) == (1, 1, 1)
