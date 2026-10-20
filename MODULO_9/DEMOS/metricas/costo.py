# costo.py — cuánto cuesta evaluar. Estimador previo + contador de tokens reales.
#
# Precios de Gemini 2.5 Flash en la API de Gemini (texto, nivel de pago): $0.30 por millón
# de tokens de entrada y $2.50 por millón de salida (la salida incluye los tokens de
# razonamiento). Fuente: https://ai.google.dev/gemini-api/docs/pricing, consultada el
# 2026-10-19. Con la capa gratuita no se paga, pero la estimación sigue diciendo cuánto
# equivale lo que se consume. Si cambia el precio, o si usás otro modelo (MODEL_NAME),
# cambian estas dos constantes.
#
# Tokens por llamada del juez de ADK (hallucinations_v1 y rúbricas, Gemini 2.5 Flash):
#   2026-10-18, ADK 2.12.0: 10 llamadas medidas → ~2.6k de entrada y ~2.4k de salida
#                           (casi toda la salida es razonamiento del modelo).
#   2026-10-10, ADK 2.10.0: 34 llamadas medidas → ~3.7k de entrada y ~1.0k de salida.
# La proporción de razonamiento varía mucho entre corridas y versiones: por eso el
# escenario «alto» es generoso y el costo real se mide siempre, no se da por estimado.
# El prompt del juez reenvía la instrucción del agente, la declaración de herramientas y
# la traza completa; por eso juzgar cuesta bastante más que ejecutar al agente.
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

# ── Precios y tokens por llamada ────────────────────────────────────────────

PRECIO_ENTRADA_USD_POR_M = 0.30
PRECIO_SALIDA_USD_POR_M = 2.50

# (tokens de entrada, tokens de salida) por llamada del juez, en tres escenarios.
# «esperado» sigue lo medido con ADK 2.12; «bajo» y «alto» acotan el rango, y «alto» es
# generoso a propósito: es el que se usa para el tope de gasto.
JUEZ_POR_LLAMADA = {"bajo": (2300, 1000), "esperado": (2700, 2400), "alto": (3700, 3600)}


# ── Estimación previa ───────────────────────────────────────────────────────

@dataclass
class Tokens:
    """Tokens consumidos (o estimados) y su costo en dólares."""
    entrada: float = 0.0
    salida: float = 0.0        # incluye los tokens de razonamiento

    @property
    def usd(self) -> float:
        return (self.entrada * PRECIO_ENTRADA_USD_POR_M + self.salida * PRECIO_SALIDA_USD_POR_M) / 1_000_000


def estimar_juez(llamadas: int) -> dict[str, Tokens]:
    """Costo estimado de `llamadas` llamadas al juez, en cada escenario. Se imprime
    ANTES de gastar, para poder abortar si el peor escenario supera el tope."""
    return {esc: Tokens(llamadas * e, llamadas * s) for esc, (e, s) in JUEZ_POR_LLAMADA.items()}


# ── Contador de tokens reales de TODAS las llamadas al modelo ───────────────

USO: dict[str, float] = defaultdict(float)   # llamadas / entrada / salida acumuladas


def instalar_contador() -> None:
    """Envuelve la llamada al modelo para sumar el usage_metadata de cada respuesta.
    Las métricas de eficiencia de ADK miden solo al agente evaluado; el juez no se reporta."""
    from google.adk.models.google_llm import Gemini

    original = Gemini.generate_content_async

    async def contado(self, llm_request, stream=False):
        async for resp in original(self, llm_request, stream=stream):
            um = getattr(resp, "usage_metadata", None)
            # Las respuestas parciales (streaming) no se cuentan: el uso se toma de la final.
            if um is not None and not getattr(resp, "partial", False):
                USO["llamadas"] += 1
                USO["entrada"] += um.prompt_token_count or 0
                USO["salida"] += (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
            yield resp

    Gemini.generate_content_async = contado


def uso_real() -> Tokens:
    """Lo acumulado hasta ahora por el contador, como Tokens (y por lo tanto en USD)."""
    return Tokens(USO["entrada"], USO["salida"])
