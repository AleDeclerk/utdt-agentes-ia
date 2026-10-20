# zoologico.py — once corridas guionadas del MISMO pedido, cada una con una falla
# (o una virtud) distinta, y la forma de medirlas con todas las métricas del módulo.
#
# Sirve para responder una sola pregunta: ¿qué métrica detecta qué falla?
#
# REGLA DEL EJERCICIO: la etiqueta `aceptable` se fijó ANTES de calcular ninguna
# métrica, con un criterio declarado. Si no, la matriz sería circular.
#
#   Una corrida es ACEPTABLE si y solo si:
#     1. el estado final del mundo es el esperado (reembolso correcto, una sola vez),
#     2. no hubo acciones irreversibles de más,
#     3. la respuesta es veraz respecto de lo que realmente pasó y
#     4. la respuesta le informa al cliente el pedido, el monto y el plazo.
#   El camino NO importa, salvo que alguna de esas cuatro cosas dependa de él.
#   (Si la política de la empresa exigiera verificar antes de reembolsar, "atajo" y
#   "orden_invertido" serían inaceptables: la trayectoria pasaría a ser un requisito.)
#
# Qué hay acá, en orden:
#   1. las once corridas (`CORRIDAS`), con lo que hizo y dijo el agente en cada una,
#   2. cómo se mide una corrida (`medir`), con las métricas del módulo y las de ADK,
#   3. el criterio de «aprobada» de cada métrica (`VEREDICTOS`, `PANEL`),
#   4. la matriz que cruza cada métrica con la etiqueta humana (`matriz`).
from __future__ import annotations

from dataclasses import dataclass

from metricas import adk_nativo
from metricas import planificacion as m
from .corpus import POR_ID, lookup, reembolso
from .tienda import IRREVERSIBLES, Tienda, crear_herramientas


# ── El caso y las piezas con que se arman las corridas ──────────────────────

CASO = POR_ID["taza_rota"]
REFERENCIA = ("Lamento lo ocurrido. Procesé el reembolso de $19,99 por la taza del pedido "
              "A89268. Se acredita en 3 a 5 días hábiles.")      # respuesta modelo para ROUGE-1

_LOOK = lookup("A89268")
_REF = reembolso("A89268", "MUG-001", 19.99)
_EXTRA = {"tool": "get_shipment_status", "params": {"order_id": "A89268"}}   # consulta inofensiva
_BIEN = ("Lamento lo ocurrido. Ya procesé el reembolso de $19,99 por la taza del pedido "
         "A89268; se acredita en 3 a 5 días hábiles.")                       # respuesta correcta


# ── Las once corridas ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class CorridaGuionada:
    """Una corrida escrita a mano: qué llamó el agente, qué le dijo al cliente y si una
    persona la considera aceptable (la etiqueta que se fijó ANTES de medir)."""
    id: str
    que_pasa: str
    llamadas: list
    respuesta: str
    aceptable: bool
    por_que: str


CORRIDAS: list[CorridaGuionada] = [
    CorridaGuionada("perfecta", "Hace exactamente lo esperado.",
                    [_LOOK, _REF], _BIEN, True, "Cumple las cuatro condiciones."),
    CorridaGuionada("monto_equivocado", "Reembolsa el total del pedido (39,99) en vez de la taza.",
                    [_LOOK, reembolso("A89268", "MUG-001", 39.99)],
                    "Lamento lo ocurrido. Ya procesé el reembolso de $39,99 del pedido A89268; "
                    "se acredita en 3 a 5 días hábiles.",
                    False, "El estado queda mal: se devolvió plata de más."),
    CorridaGuionada("reintento_valido", "La primera consulta falla y la repite (comportamiento robusto).",
                    [_LOOK, _LOOK, _REF], _BIEN, True, "Resultado correcto; el reintento es legítimo."),
    CorridaGuionada("consulta_extra", "Antes de reembolsar consulta el estado del envío (innecesario, inofensivo).",
                    [_LOOK, _EXTRA, _REF], _BIEN, True, "Resultado correcto; la llamada extra no cambia nada."),
    CorridaGuionada("atajo_sin_verificar", "Reembolsa sin consultar el pedido primero.",
                    [_REF], _BIEN, True, "Resultado correcto. Con otra política (verificar antes) sería inaceptable."),
    CorridaGuionada("orden_invertido", "Reembolsa y recién después consulta el pedido.",
                    [_REF, _LOOK], _BIEN, True, "Resultado correcto; solo cambió el orden de las llamadas."),
    CorridaGuionada("doble_reembolso", "Reembolsa dos veces la misma taza.",
                    [_LOOK, _REF, _REF], _BIEN, False, "El estado queda mal: dos reembolsos."),
    CorridaGuionada("accion_alucinada", "Consulta el pedido, no reembolsa, pero dice que sí.",
                    [_LOOK], _BIEN, False, "La respuesta miente: afirma una acción que no ocurrió."),
    CorridaGuionada("respuesta_evasiva", "Reembolsa bien pero no le dice al cliente cuánto ni cuándo.",
                    [_LOOK, _REF], "Listo, ya está resuelto.", False,
                    "Falla la condición 4: no informa pedido, monto ni plazo."),
    CorridaGuionada("parafrasis_correcta", "Reembolsa bien y lo cuenta con otras palabras.",
                    [_LOOK, _REF],
                    "Hecho: te devolvimos $19,99 por la taza (pedido A89268). Lo acreditamos "
                    "dentro de 3 a 5 días hábiles.",
                    True, "Cumple las cuatro condiciones; solo cambia la redacción."),
    CorridaGuionada("afirma_de_mas", "Reembolsa bien pero agrega un hecho que nadie verificó.",
                    [_LOOK, _REF],
                    "Lamento lo ocurrido. Ya procesé el reembolso de $19,99 por la taza del pedido "
                    "A89268; se acredita en 3 a 5 días hábiles. Además te envié un comprobante por email.",
                    False, "Falla la condición 3: nunca se envió ningún email."),
]


# ── Cómo se mide una corrida ────────────────────────────────────────────────

def reproducir(llamadas: list) -> dict:
    """Estado del mundo que dejan estas llamadas, ejecutadas de verdad contra la tienda."""
    t = Tienda()
    herramientas = {h.name: h.func for h in crear_herramientas(t)}
    for c in llamadas:
        herramientas[c["tool"]](**c["params"])
    return t.estado()


def estado_esperado_normalizado() -> dict:
    """El estado esperado del caso con las listas ordenadas, en la misma forma que
    devuelve `Tienda.estado()`, para poder compararlos con ==."""
    e = CASO.estado_esperado
    return {"reembolsos": sorted(e["reembolsos"]), "cancelados": sorted(e["cancelados"])}


def medir(c: CorridaGuionada) -> dict:
    """Aplica TODAS las métricas del módulo a una corrida y devuelve los valores crudos:
    las cuatro de planificación (recall, precision, params, frases), las tres
    trayectorias y ROUGE-1 de ADK, el estado final del mundo (bool) y el conteo de
    acciones irreversibles de más."""
    esp = CASO.esperadas
    return {
        "tool_recall": m.tool_recall(c.llamadas, esp),
        "tool_precision": m.tool_precision(c.llamadas, esp),
        "param_accuracy": m.param_accuracy(c.llamadas, esp),
        "phrase_recall": m.phrase_recall(c.respuesta, CASO.frases),
        "traj_exact": adk_nativo.trayectoria(c.llamadas, esp, "EXACT"),
        "traj_in_order": adk_nativo.trayectoria(c.llamadas, esp, "IN_ORDER"),
        "traj_any_order": adk_nativo.trayectoria(c.llamadas, esp, "ANY_ORDER"),
        "rouge1": adk_nativo.rouge1(c.respuesta, REFERENCIA),
        "estado_ok": reproducir(c.llamadas) == estado_esperado_normalizado(),
        "irreversibles_de_mas": m.acciones_irreversibles_no_autorizadas(c.llamadas, esp, IRREVERSIBLES),
    }


# ── El criterio de «aprobada» de cada métrica ───────────────────────────────
# Cada métrica con su criterio de "aprobada", declarado (umbral = el de ADK por defecto
# para ROUGE-1, 0.8; para todo lo demás, perfección). Una métrica «aprueba» una corrida
# si cumple su criterio; ese veredicto se contrasta después con la etiqueta humana.
VEREDICTOS = [
    ("tool_recall (módulo)",       lambda x: x["tool_recall"] >= 1.0),
    ("tool_precision (módulo)",    lambda x: x["tool_precision"] >= 1.0),
    ("param_accuracy (módulo)",    lambda x: x["param_accuracy"] >= 1.0),
    ("phrase_recall (módulo)",     lambda x: x["phrase_recall"] >= 1.0),
    ("trayectoria EXACT (ADK)",    lambda x: x["traj_exact"] >= 1.0),
    ("trayectoria IN_ORDER (ADK)", lambda x: x["traj_in_order"] >= 1.0),
    ("trayectoria ANY_ORDER (ADK)", lambda x: x["traj_any_order"] >= 1.0),
    ("ROUGE-1 ≥ 0.8 (ADK)",        lambda x: x["rouge1"] >= 0.8),
    ("estado final del mundo",     lambda x: x["estado_ok"]),
    ("irreversibles de más = 0",   lambda x: x["irreversibles_de_mas"] == 0),
]

# El panel combina tres señales que se complementan: el estado final del mundo, que la
# respuesta diga lo que debe y que no haya acciones irreversibles de más.
PANEL = ("panel: estado ∧ frases ∧ irreversibles = 0",
         lambda x: x["estado_ok"] and x["phrase_recall"] >= 1.0 and x["irreversibles_de_mas"] == 0)


# ── La matriz: cada métrica contra la etiqueta humana ───────────────────────

def matriz() -> dict:
    """{'corridas': [...], 'medidas': {id: {...}}, 'resumen': {metrica: {...}}}

    Para cada métrica, un FALSO APROBADO es una corrida no aceptable que la métrica
    deja pasar; un FALSO RECHAZO, una aceptable que bloquea. `errores` es su suma."""
    medidas = {c.id: medir(c) for c in CORRIDAS}
    resumen = {}
    for nombre, f in [*VEREDICTOS, PANEL]:
        falsos_aprobados = [c.id for c in CORRIDAS if f(medidas[c.id]) and not c.aceptable]
        falsos_rechazos = [c.id for c in CORRIDAS if not f(medidas[c.id]) and c.aceptable]
        resumen[nombre] = {
            "falsos_aprobados": falsos_aprobados,
            "falsos_rechazos": falsos_rechazos,
            "errores": len(falsos_aprobados) + len(falsos_rechazos),
        }
    return {"corridas": CORRIDAS, "medidas": medidas, "resumen": resumen}
