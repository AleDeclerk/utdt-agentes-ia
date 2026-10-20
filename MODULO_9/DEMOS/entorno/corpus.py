# corpus.py — el corpus de evaluación: siete casos con su especificación completa.
#
# Cada caso define tres cosas:
#   1. la entrada (mensaje del cliente),
#   2. la trayectoria esperada (llamadas con parámetros) y las frases que debe
#      contener la respuesta,
#   3. el estado final esperado del mundo (reembolsos y cancelaciones).
# Las dos primeras describen lo que el agente HACE y DICE; la tercera, cómo queda el mundo.
# El estado final se compara contra el estado real de la tienda (Tienda.estado en
# tienda.py), no contra lo que el agente cuenta haber hecho: es el criterio de τ-bench
# (Yao et al., 2024), que evalúa comparando el estado final.
#
# Los casos 4, 6 y 7 son los "difíciles": intención mezclada (cancelar_entregado),
# typo en el ID (id_con_typo) y pregunta sin acción (consulta_politica).
from __future__ import annotations

from dataclasses import dataclass, field


# ── Constructores de llamadas esperadas ─────────────────────────────────────
# Una llamada es un dict {"tool", "params"}; estos cuatro atajos evitan repetir esa forma.

def lookup(o): return {"tool": "lookup_order", "params": {"order_id": o}}
def estado(o): return {"tool": "get_shipment_status", "params": {"order_id": o}}
def cancelar(o): return {"tool": "cancel_order", "params": {"order_id": o}}
def reembolso(o, sku, monto): return {"tool": "issue_refund", "params": {"order_id": o, "sku": sku, "amount": monto}}


# ── La especificación de un caso ────────────────────────────────────────────

@dataclass(frozen=True)
class Caso:
    id: str
    mensaje: str
    esperadas: list = field(default_factory=list)        # trayectoria esperada
    frases: list = field(default_factory=list)           # lo que debe decir la respuesta
    estado_esperado: dict = field(default_factory=lambda: {"reembolsos": [], "cancelados": []})
    nota: str = ""                                       # qué ejercita el caso (documentación)


# ── Los siete casos ─────────────────────────────────────────────────────────
# Las frases se buscan como subcadena de la respuesta tras normalizar ambos lados
# (minúsculas, sin tildes, coma decimal → punto; ver normalizar_texto en
# metricas/planificacion.py): por eso "19.99" alcanza para «$19,99».

CORPUS: list[Caso] = [
    # 1 · El caso central: reembolso PARCIAL de un pedido de dos ítems.
    Caso("taza_rota",
         "Hola, me llegó rota la taza del pedido A89268. Quiero que me devuelvan la plata.",
         [lookup("A89268"), reembolso("A89268", "MUG-001", 19.99)],
         ["A89268", "19.99", "dias habiles"],
         {"reembolsos": [("A89268", "MUG-001", 19.99)], "cancelados": []},
         "Pedido de dos ítems: se reembolsa SOLO la taza (19,99), no el total (39,99)."),
    # 2 · Fuera de plazo: lo correcto es NO reembolsar.
    Caso("fuera_de_plazo",
         "Quiero devolver los auriculares del pedido B70415, los recibí hace un mes y medio.",
         [lookup("B70415")], ["B70415", "30 dias"],
         nota="Entregado hace 45 días: fuera de la política de 30. No se reembolsa."),
    # 3 · La cancelación legítima.
    Caso("cancelar_en_proceso",
         "Cancelame por favor el pedido C55120, me equivoqué de talle.",
         [lookup("C55120"), cancelar("C55120")], ["C55120", "cancel"],
         {"reembolsos": [], "cancelados": ["C55120"]},
         "Único caso donde cancelar es lo correcto: el pedido está en 'processing'."),
    # 4 · DIFÍCIL: la intención mezcla dos acciones irreversibles sobre un pedido entregado.
    Caso("cancelar_entregado",
         "Quiero cancelar el pedido A89268 y que me devuelvan todo.",
         [lookup("A89268")], ["A89268", "entreg"],
         nota="Intención mezclada sobre un pedido entregado: aclarar o derivar, sin "
              "cancelar ni reembolsar."),
    # 5 · Consulta pura, sin efectos.
    Caso("consulta_estado",
         "¿Dónde está mi pedido D31877?",
         [lookup("D31877"), estado("D31877")], ["D31877"],
         nota="Consulta pura: no debe cambiar el estado del mundo."),
    # 6 · DIFÍCIL: el ID no existe; lo correcto es preguntar, no adivinar.
    Caso("id_con_typo",
         "Quiero el reembolso del pedido A89286.",
         [lookup("A89286")], ["A89286", "confirm"],
         nota="El ID tiene un typo (A89286 no existe). Pedir confirmación; no adivinar."),
    # 7 · DIFÍCIL: no hay ninguna herramienta esperada (el caso vacío de recall / precisión).
    Caso("consulta_politica",
         "¿Cuál es la política de devoluciones?",
         [], ["30 dias"],
         nota="Caso SIN herramientas esperadas: ejercita el caso borde de recall/precisión vacíos."),
]

POR_ID = {c.id: c for c in CORPUS}
