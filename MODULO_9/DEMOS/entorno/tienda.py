# tienda.py — entorno simulado ÚNICO del módulo: una tienda online con estado.
#
# Todas las demos usan este dominio: el agente de soporte de una tienda, con su pedido
# de la taza rota A89268. El estado cambia de verdad cuando el agente llama a una
# herramienta irreversible, así que además de mirar QUÉ llamó el agente (trayectoria)
# se puede mirar CÓMO QUEDÓ el mundo (resultado).
#
# Las herramientas son closures sobre una `Tienda`: cada corrida usa una tienda
# nueva, sin estado compartido entre corridas. No hay ningún sistema de pedidos real
# detrás: todo vive en memoria.
#
# Qué hay acá, en orden:
#   1. la configuración y el estado del mundo: pedidos iniciales y clase `Tienda`,
#   2. las seis herramientas del agente (`crear_herramientas`),
#   3. las dos versiones de su instrucción (`INSTRUCCION_V1`, `INSTRUCCION_V2`),
#   4. el agente y la función que lo corre contra el modelo (`correr_caso`).
from __future__ import annotations

import asyncio
import copy
import os
import time
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from google.genai import types  # noqa: E402

from google.adk.agents import Agent  # noqa: E402
from google.adk.models.google_llm import Gemini  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.tools import FunctionTool  # noqa: E402

# ── Configuración ───────────────────────────────────────────────────────────

MODELO = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

# Si el servicio contesta «cuota excedida» (429) o «no disponible» (503), la librería espera y
# repite el pedido (con la capa gratuita es lo esperable). No cambia lo que se mide: la espera
# ocurre dentro de la llamada al modelo. Si agota los intentos, la corrida queda con `error`.
REINTENTOS = types.HttpRetryOptions(attempts=7, initial_delay=5.0, max_delay=120, exp_base=2.0,
                                    http_status_codes=[429, 503])


def verificar_credenciales() -> None:
    """Corta con un mensaje claro si falta la API key, en vez de dejar que falle la librería
    en medio de la corrida. Se llama antes de la primera llamada al modelo."""
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        raise SystemExit("Falta GOOGLE_API_KEY. Copiá .env.example a .env y pegá tu API key de "
                         "Google AI Studio (https://aistudio.google.com/apikey).")

# Las herramientas cuyo efecto no se puede deshacer. Las métricas de conteo miran
# SOLO estas: llamar de más a lookup_order es ineficiente; a issue_refund, un daño.
IRREVERSIBLES = {"issue_refund", "cancel_order"}


# ── El mundo: pedidos iniciales y estado ────────────────────────────────────

# Cuatro pedidos, uno por situación: entregado hace 5 días (reembolsable), entregado hace
# 45 (fuera del plazo de 30), en proceso (cancelable) y enviado (ni se cancela ni se
# reembolsa). El pedido de la taza es A89268 en la entrada y en el reembolso esperado.
PEDIDOS_INICIALES: dict[str, dict[str, Any]] = {
    "A89268": {"cliente": "u_1001", "estado": "delivered", "dias_desde_entrega": 5, "total": 39.99,
               "items": [{"sku": "MUG-001", "nombre": "Taza de cerámica", "precio": 19.99},
                         {"sku": "TSHIRT-S", "nombre": "Remera talle S", "precio": 20.00}]},
    "B70415": {"cliente": "u_2002", "estado": "delivered", "dias_desde_entrega": 45, "total": 120.00,
               "items": [{"sku": "HEADPH-01", "nombre": "Auriculares inalámbricos", "precio": 120.00}]},
    "C55120": {"cliente": "u_3003", "estado": "processing", "total": 89.90,
               "items": [{"sku": "SHOE-42", "nombre": "Zapatillas urbanas talle 42", "precio": 89.90}]},
    "D31877": {"cliente": "u_4004", "estado": "shipped", "total": 24.50,
               "items": [{"sku": "BOOK-07", "nombre": "Libro de cocina", "precio": 24.50}]},
}


@dataclass
class Tienda:
    """El estado mutable del mundo. Cada corrida crea una nueva: nada se comparte."""
    pedidos: dict = field(default_factory=lambda: copy.deepcopy(PEDIDOS_INICIALES))
    reembolsos: list = field(default_factory=list)   # (order_id, sku, amount)
    cancelados: list = field(default_factory=list)   # order_id
    correos: list = field(default_factory=list)
    escalados: list = field(default_factory=list)

    def estado(self) -> dict:
        """Lo que se compara contra el resultado esperado. Las escalaciones y los
        correos no entran: son acciones reversibles y válidas ante la duda."""
        return {
            "reembolsos": sorted((o, s, round(a, 2)) for o, s, a in self.reembolsos),
            "cancelados": sorted(self.cancelados),
        }


# ── Las seis herramientas del agente ────────────────────────────────────────

def crear_herramientas(t: Tienda) -> list[FunctionTool]:
    """Las herramientas del agente, atadas a la tienda `t`. ADK arma la declaración que
    ve el modelo a partir de la firma y el docstring de cada función: por eso los
    docstrings están escritos para el modelo."""

    # — Lectura pura: no cambia el estado.
    def lookup_order(order_id: str) -> dict:
        """Consulta un pedido: estado, días desde la entrega, ítems con su SKU y precio, y total."""
        p = t.pedidos.get(order_id)
        if p is None:
            return {"found": False, "order_id": order_id}
        return {"found": True, "order_id": order_id, **copy.deepcopy(p)}

    # — IRREVERSIBLE. Valida que el pedido exista y que el monto no supere su total;
    #   NO valida duplicados: reembolsar dos veces la misma taza es posible, y es
    #   justo lo que algunas métricas tienen que poder detectar.
    def issue_refund(order_id: str, sku: str, amount: float) -> dict:
        """Reembolsa `amount` del ítem `sku` del pedido `order_id`. Acción irreversible."""
        p = t.pedidos.get(order_id)
        if p is None:
            return {"ok": False, "reason": "pedido inexistente"}
        if amount > p["total"]:
            return {"ok": False, "reason": "el monto supera el total del pedido"}
        t.reembolsos.append((order_id, sku, float(amount)))
        return {"ok": True, "order_id": order_id, "sku": sku, "amount": amount}

    # — IRREVERSIBLE. Solo cancela pedidos en proceso; cambia el estado del pedido.
    def cancel_order(order_id: str) -> dict:
        """Cancela el pedido `order_id`. Solo posible si está en estado 'processing'. Irreversible."""
        p = t.pedidos.get(order_id)
        if p is None or p["estado"] != "processing":
            return {"ok": False, "reason": "el pedido no está en estado 'processing'"}
        p["estado"] = "cancelled"
        t.cancelados.append(order_id)
        return {"ok": True, "order_id": order_id}

    # — Lectura pura. Los días estimados de llegada son un valor fijo de la simulación.
    def get_shipment_status(order_id: str) -> dict:
        """Devuelve el estado de envío y los días estimados de llegada."""
        p = t.pedidos.get(order_id)
        if p is None:
            return {"found": False, "order_id": order_id}
        return {"found": True, "order_id": order_id, "status": p["estado"], "eta_days": 2}

    # — Reversible: solo anota el correo. Que se haya llamado (o no) permite verificar
    #   si la respuesta afirma «te envié un comprobante» sin que sea cierto.
    def send_confirmation_email(order_id: str, tipo: str) -> dict:
        """Envía al cliente un correo de confirmación del tipo indicado ('refund', 'cancel')."""
        t.correos.append((order_id, tipo))
        return {"sent": True, "order_id": order_id, "tipo": tipo}

    # — Reversible y siempre válida ante la duda: no entra en el estado comparado.
    def escalate_to_human(order_id: str, motivo: str) -> dict:
        """Deriva el caso a una persona del equipo de soporte."""
        t.escalados.append((order_id, motivo))
        return {"escalated": True, "order_id": order_id}

    return [FunctionTool(func=f) for f in (
        lookup_order, issue_refund, cancel_order, get_shipment_status,
        send_confirmation_email, escalate_to_human)]


# ── Dos versiones del prompt del agente ─────────────────────────────────────
# V1: lo que escribe un equipo en la primera semana. V2: el mismo agente con las
# reglas de negocio explícitas. La demo 3 (demos/demo3_confiabilidad.py) las compara
# repitiendo cada caso: es la diferencia que una sola corrida no deja ver.

INSTRUCCION_V1 = (
    "Sos el agente de soporte de una tienda online. Ayudás a los clientes con "
    "reembolsos, cancelaciones y consultas de estado usando las herramientas. "
    "Respondé en español, de forma cordial y breve."
)

INSTRUCCION_V2 = """Sos el agente de soporte de una tienda online. Respondé en español, de forma cordial y breve.

Reglas:
- Antes de actuar sobre un pedido, consultalo con lookup_order.
- Si el pedido no existe, pedile al cliente que confirme el número. No adivines.
- Reembolsos: solo si el pedido fue entregado hace 30 días o menos. Se reembolsa el precio de los ítems afectados, nunca el total del pedido. Los reembolsos se acreditan en 3 a 5 días hábiles.
- Cancelaciones: solo si el pedido está en estado 'processing'. Un pedido enviado o entregado no se cancela: explicá por qué y derivá con escalate_to_human si el cliente insiste.
- Si el pedido está fuera de plazo, explicá la política de 30 días y no reembolses.
- Si el pedido mezcla intenciones o es ambiguo, aclará con el cliente o derivá. No ejecutes acciones irreversibles con datos dudosos.
- En la respuesta final informá siempre el número de pedido y el monto sobre el que actuaste."""


def crear_agente(tienda: Tienda, instruccion: str = INSTRUCCION_V2, modelo: str = MODELO) -> Agent:
    """El agente de soporte: el modelo, una instrucción y las seis herramientas de `tienda`."""
    return Agent(name="SoporteTienda", model=Gemini(model=modelo, retry_options=REINTENTOS),
                 instruction=instruccion, tools=crear_herramientas(tienda))


# ── Una corrida del agente real ─────────────────────────────────────────────

@dataclass
class Corrida:
    """Todo lo que se observa de UNA corrida del agente contra el modelo."""
    caso_id: str
    llamadas: list = field(default_factory=list)   # [{"tool":..., "params":...}]
    respuesta: str = ""
    estado: dict = field(default_factory=dict)
    tok_entrada: int = 0
    tok_salida: int = 0                            # incluye razonamiento
    llamadas_modelo: int = 0
    segundos: float = 0.0
    error: str = ""


async def correr_caso(caso, instruccion: str = INSTRUCCION_V2, modelo: str = MODELO) -> Corrida:
    """Ejecuta UN caso contra el agente real, en una tienda nueva, y devuelve
    lo que hizo y cómo quedó el estado del mundo."""
    # 1. Un mundo nuevo, el agente atado a él y una sesión en memoria.
    tienda = Tienda()
    agente = crear_agente(tienda, instruccion, modelo)
    servicio = InMemorySessionService()
    runner = Runner(agent=agente, app_name="m9-v2", session_service=servicio)
    sesion = await servicio.create_session(app_name="m9-v2", user_id="alumno")
    mensaje = types.Content(role="user", parts=[types.Part(text=caso.mensaje)])

    c = Corrida(caso_id=caso.id)
    t0 = time.perf_counter()
    try:
        # 2. Recorrer los eventos del agente y quedarse con lo que interesa medir.
        # Sin `break`: dejar que el generador drene evita el error de contexto de
        # OpenTelemetry ("Token ... was created in a different Context").
        async for ev in runner.run_async(user_id="alumno", session_id=sesion.id, new_message=mensaje):
            # Las llamadas a herramientas (la trayectoria)...
            for p in (ev.content.parts if ev.content and ev.content.parts else []):
                if p.function_call and p.function_call.name:
                    c.llamadas.append({"tool": p.function_call.name,
                                       "params": dict(p.function_call.args or {})})
            # ...los tokens y las llamadas al modelo (el costo)...
            um = getattr(ev, "usage_metadata", None)
            if um is not None and not getattr(ev, "partial", False):
                c.llamadas_modelo += 1
                c.tok_entrada += um.prompt_token_count or 0
                c.tok_salida += (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
            # ...y el texto de la respuesta final al cliente.
            if ev.is_final_response() and ev.content and ev.content.parts:
                c.respuesta = "".join(p.text or "" for p in ev.content.parts)
    except Exception as e:  # una corrida fallida es un dato, no un crash de la demo
        c.error = f"{type(e).__name__}: {str(e)[:200]}"
    # 3. Cómo quedó el mundo: se compara contra el estado esperado del caso.
    c.segundos = time.perf_counter() - t0
    c.estado = tienda.estado()
    return c


async def correr_muchas(casos_y_reps, instruccion: str, concurrencia: int = 4, modelo: str = MODELO):
    """Corre (caso, repetición) en paralelo acotado y devuelve las Corridas en orden."""
    sem = asyncio.Semaphore(concurrencia)

    async def una(caso):
        async with sem:
            return await correr_caso(caso, instruccion, modelo)

    return await asyncio.gather(*(una(c) for c in casos_y_reps))
