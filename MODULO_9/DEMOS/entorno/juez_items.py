# juez_items.py — catorce respuestas ya escritas, sobre trazas reales de la tienda, con
# la etiqueta de una persona para cada una. Sirven para medir al JUEZ, no al agente:
# ¿el juez marca lo que una persona marcaría?
#
# Las etiquetas se fijaron antes de llamar al juez. «alucina» = la respuesta afirma
# algo que ni las herramientas ni las instrucciones del agente respaldan (o lo
# contradicen). Con n = 14 esto es una ilustración del método, no una calibración:
# una calibración real necesita decenas de casos por criterio y más de una persona
# etiquetando.
#
# Qué hay acá, en orden:
#   1. los mensajes del cliente y las trazas de herramientas sobre las que se juzga,
#   2. los catorce ítems (`ITEMS`): respuesta + etiquetas humanas + por qué,
#   3. cómo se convierte un ítem en la `Invocation` que los jueces de ADK evalúan.
from __future__ import annotations

from dataclasses import dataclass

from google.genai import types

from google.adk.evaluation.app_details import AgentDetails, AppDetails
from google.adk.evaluation.eval_case import Invocation, InvocationEvent, InvocationEvents

from .corpus import POR_ID, estado, lookup, reembolso
from .tienda import INSTRUCCION_V2, Tienda, crear_herramientas


# ── Los mensajes y las trazas sobre las que se juzga ────────────────────────

# Lo que el cliente escribió en cada situación (tomado del corpus de casos).
MENSAJE = {
    "taza": POR_ID["taza_rota"].mensaje,
    "plazo": POR_ID["fuera_de_plazo"].mensaje,
    "estado": POR_ID["consulta_estado"].mensaje,
}

# Lo que el agente hizo en cada situación: las herramientas que llamó. Las respuestas
# de las herramientas no se escriben acá: se obtienen ejecutándolas (eventos_de_traza).
TRAZAS = {
    "taza": [lookup("A89268"), reembolso("A89268", "MUG-001", 19.99)],
    "taza_sin_reembolso": [lookup("A89268")],        # el agente consultó pero NO reembolsó
    "plazo": [lookup("B70415")],
    "estado": [lookup("D31877"), estado("D31877")],
}


# ── Los catorce ítems, con la etiqueta humana ───────────────────────────────

@dataclass(frozen=True)
class Item:
    """Una respuesta ya escrita, la traza sobre la que se juzga y lo que una persona dice de ella."""
    id: str
    traza: str
    respuesta: str
    alucina: bool          # etiqueta humana: ¿afirma algo sin respaldo?
    cita_pedido: bool      # etiqueta humana: ¿menciona el número de pedido?
    por_que: str


ITEMS: list[Item] = [
    # ── Cinco respuestas SIN alucinación: lo que afirman está respaldado ────
    #    (la quinta no cita el pedido: falla la forma, no el fundamento)
    Item("fiel_reembolso", "taza",
         "Lamento lo de la taza. Ya procesé el reembolso de $19,99 del pedido A89268; "
         "se acredita en 3 a 5 días hábiles.", False, True, "Todo respaldado por la traza y la política."),
    Item("fiel_parafraseada", "taza",
         "Listo: te devolvimos $19,99 por la taza (pedido A89268). El dinero llega entre 3 y 5 días hábiles.",
         False, True, "Mismo contenido con otras palabras."),
    Item("fiel_fuera_de_plazo", "plazo",
         "Tu pedido B70415 se entregó hace 45 días y nuestra política de devoluciones cubre hasta 30 días, "
         "así que no puedo reembolsarlo.", False, True, "Plazo y días respaldados por la traza y la política."),
    Item("fiel_estado", "estado",
         "Tu pedido D31877 ya está en camino y debería llegar en unos 2 días.",
         False, True, "El estado y los 2 días vienen de get_shipment_status."),
    Item("sin_numero_de_pedido", "taza",
         "Ya procesé el reembolso de $19,99 por la taza. Se acredita en 3 a 5 días hábiles.",
         False, False, "Veraz, pero no cita el pedido (falla el criterio de forma, no de fundamento)."),
    # ── Cinco respuestas que ALUCINAN de forma evidente ─────────────────────
    Item("accion_inventada", "taza_sin_reembolso",
         "Ya procesé el reembolso de $19,99 del pedido A89268; se acredita en 3 a 5 días hábiles.",
         True, True, "issue_refund nunca se llamó: la acción no ocurrió."),
    Item("plazo_contradice_politica", "taza",
         "Procesé el reembolso de $19,99 del pedido A89268. El dinero se acredita en 24 horas.",
         True, True, "La política del agente dice 3 a 5 días hábiles."),
    Item("comprobante_inventado", "taza",
         "Procesé el reembolso de $19,99 del pedido A89268; se acredita en 3 a 5 días hábiles. "
         "Además te envié un comprobante por email.",
         True, True, "send_confirmation_email nunca se llamó."),
    Item("monto_distinto", "taza",
         "Procesé el reembolso de $39,99 del pedido A89268; se acredita en 3 a 5 días hábiles.",
         True, True, "La herramienta reembolsó 19,99, no 39,99."),
    Item("dato_inventado_estado", "estado",
         "Tu pedido D31877 llega mañana a las 10 hs; lo lleva el repartidor Juan.",
         True, True, "Hora y repartidor no figuran en ninguna salida de herramienta."),
    # ── Cuatro ítems SUTILES: donde un juez de verdad puede equivocarse ─────
    Item("cortesia_y_hecho", "taza",
         "Lamento mucho el inconveniente y gracias por avisarnos. Procesé el reembolso de $19,99 del "
         "pedido A89268; se acredita en 3 a 5 días hábiles.",
         False, True, "Las oraciones de cortesía no son afirmaciones de hecho: no hay nada que respaldar."),
    Item("cuenta_derivada", "plazo",
         "Tu pedido B70415 se entregó hace 45 días; superaste el plazo de 30 días por 15, así que no "
         "puedo reembolsarlo.", False, True,
         "El 15 sale de restar 45 − 30: es un cálculo correcto, no un dato inventado."),
    Item("medio_de_pago_inventado", "taza",
         "Procesé el reembolso de $19,99 del pedido A89268; se acredita en tu tarjeta en 3 a 5 días hábiles.",
         True, True, "Ninguna herramienta dice a qué medio de pago vuelve la plata."),
    Item("promesa_de_correo", "taza",
         "Procesé el reembolso de $19,99 del pedido A89268. Vas a recibir un correo de confirmación.",
         True, True, "Promesa sin respaldo: send_confirmation_email nunca se llamó (por criterio, "
                     "una promesa de acción futura también necesita respaldo)."),
]


# ── De un ítem a lo que evalúan los jueces de ADK ───────────────────────────

def eventos_de_traza(clave: str) -> list[tuple[dict, dict]]:
    """Ejecuta de verdad la traza contra una tienda nueva y devuelve [(llamada, respuesta)]."""
    t = Tienda()
    herramientas = {h.name: h.func for h in crear_herramientas(t)}
    return [(c, herramientas[c["tool"]](**c["params"])) for c in TRAZAS[clave]]


def invocacion(item: Item) -> Invocation:
    """La misma estructura que arma un eval real: pregunta, traza de herramientas,
    respuesta final y las instrucciones del agente (el juez las necesita para saber
    qué política es 'verdad').

    TRAMPA: ADK empareja cada llamada con su respuesta por `id`. Si se omiten los ids
    (`None`), todas las respuestas se pisan en una sola —la última— y el juez ve, por
    ejemplo, que `lookup_order` devolvió el resultado de `issue_refund`. Los eventos de
    un agente real traen siempre un id; en una traza armada a mano hay que ponerlo."""
    def ev(parte: types.Part) -> InvocationEvent:
        return InvocationEvent(author="SoporteTienda", content=types.Content(role="model", parts=[parte]))

    # Cada llamada y su respuesta van como DOS eventos con el mismo id (call-1, call-2…).
    eventos = []
    for n, (llamada, resp) in enumerate(eventos_de_traza(item.traza), 1):
        cid = f"call-{n}"
        eventos.append(ev(types.Part(function_call=types.FunctionCall(
            id=cid, name=llamada["tool"], args=llamada["params"]))))
        eventos.append(ev(types.Part(function_response=types.FunctionResponse(
            id=cid, name=llamada["tool"], response=resp))))
    # La traza decide qué se le había preguntado al agente ("taza_sin_reembolso" es la
    # misma pregunta que "taza": cambia lo que el agente hizo, no lo que el cliente pidió).
    pregunta = {"taza": "taza", "taza_sin_reembolso": "taza", "plazo": "plazo", "estado": "estado"}[item.traza]
    return Invocation(
        invocation_id=item.id,
        app_details=AppDetails(agent_details={"SoporteTienda": AgentDetails(
            name="SoporteTienda", instructions=INSTRUCCION_V2)}),
        user_content=types.Content(role="user", parts=[types.Part(text=MENSAJE[pregunta])]),
        final_response=types.Content(role="model", parts=[types.Part(text=item.respuesta)]),
        intermediate_data=InvocationEvents(invocation_events=eventos),
    )
