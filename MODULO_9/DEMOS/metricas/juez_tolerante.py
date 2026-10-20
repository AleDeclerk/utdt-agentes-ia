# juez_tolerante.py — parser tolerante + contadores para el juez de rúbricas.
#
# Problema (ADK 2.10 y 2.12 — el archivo rubric_based_evaluator.py es idéntico entre
# ambas versiones; rubric_based_evaluator.DefaultAutoRaterResponseParser):
# el parser exige que haya la MISMA cantidad de líneas `Property:`,
# `Rationale: <texto>` y `Verdict:`. Si el juez escribe `Rationale:` y salta
# de línea con una lista (algo que 2.5 Flash hace seguido cuando razona sobre
# una rúbrica), el regex `(?<=Rationale: )(.*)` no matchea, las cuentas no
# cierran y la muestra ENTERA se descarta, aunque los veredictos estén bien.
# Solo queda un WARNING en el log y el score se calcula con menos muestras.
#
# Qué hace este módulo:
#   1. Si el parser original no pudo, reintenta con un parser por bloques
#      (un bloque = desde un `Property:` hasta el siguiente), que tolera
#      rationales multilínea. Conserva la regla conservadora del original:
#      si a algún bloque le falta el veredicto, devuelve [] (no se infla el
#      score con un parseo parcial).
#   2. Cuenta muestras parseadas por el original, rescatadas por este parser
#      y descartadas, para que el reporte las muestre en vez de esconderlas.
#
# Es un monkeypatch de UNA función de la librería: se aplica explícitamente
# con instalar() y no toca nada en disco.
from __future__ import annotations

import logging
import re
from collections import Counter

from google.adk.evaluation import rubric_based_evaluator as rbe

# ── Contadores y patrones ───────────────────────────────────────────────────

STATS: Counter = Counter()  # muestras / originales / rescatadas / descartadas / vacias

# Un bloque de la respuesta del juez es: ID, Property, Rationale y Verdict, en ese orden.
_PROPERTY = re.compile(r"(?m)^\s*Property:[ \t]*(.*)$")
_ID = re.compile(r"(?m)^\s*ID:[ \t]*(.*)$")
_VERDICT = re.compile(r"(?mi)^\s*Verdict:[ \t]*(.*)$")
_RATIONALE = re.compile(r"(?s)Rationale:[ \t]*(.*?)(?=^\s*Verdict:|\Z)", re.M)


# ── El parser por bloques ───────────────────────────────────────────────────

def _score(verdict: str) -> float | None:
    """«Yes» / «Sí» → 1.0; «No» → 0.0; cualquier otra cosa → None (sin veredicto)."""
    v = re.sub(r"[^a-záéíóú ]", "", verdict.lower()).strip()
    if v.startswith(("yes", "sí", "si")):
        return 1.0
    if v.startswith("no"):
        return 0.0
    return None


def parse_tolerante(texto: str) -> list[rbe.RubricResponse]:
    """Parsea la respuesta del juez bloque por bloque (de un `Property:` al siguiente).
    Devuelve [] si no hay ningún bloque o si a alguno le falta el veredicto."""
    props = list(_PROPERTY.finditer(texto))
    if not props:
        return []
    ids = list(_ID.finditer(texto))
    out: list[rbe.RubricResponse] = []
    for i, p in enumerate(props):
        fin = props[i + 1].start() if i + 1 < len(props) else len(texto)
        bloque = texto[p.end():fin]
        v = _VERDICT.search(bloque)
        if v is None:
            return []  # parseo parcial: mejor descartar que inflar el score
        r = _RATIONALE.search(bloque)
        # El `ID:` de una rúbrica va ANTES de su `Property:`, entre el bloque anterior y este.
        previo = props[i - 1].start() if i > 0 else -1
        rid = None
        for m in ids:
            if previo < m.start() < p.start():
                rid = m.group(1).strip() or None
        out.append(rbe.RubricResponse(
            rubric_id=rid,
            property_text=p.group(1).strip(),
            rationale=(r.group(1).strip() if r else ""),
            score=_score(v.group(1)),
        ))
    return out


# ── Instalación del parche y recuento de muestras ───────────────────────────

class _ContadorVacias(logging.Handler):
    """Cuenta las veces que ADK avisa (por log) que el juez devolvió una respuesta vacía."""

    def emit(self, record: logging.LogRecord) -> None:
        if "returned an empty response" in record.getMessage():
            STATS["vacias"] += 1


_instalado = False


def instalar() -> None:
    """Reemplaza `parse` del parser de ADK por uno que prueba primero el original y,
    si este devuelve [], el parser por bloques. Es idempotente: llamarla dos veces no
    envuelve el parche dos veces."""
    global _instalado
    if _instalado:
        return
    original = rbe.DefaultAutoRaterResponseParser.parse

    def parse(self, auto_rater_response: str):
        STATS["muestras"] += 1
        r = original(self, auto_rater_response)
        if r:
            STATS["originales"] += 1
            return r
        r = parse_tolerante(auto_rater_response)
        if r:
            STATS["rescatadas"] += 1
            return r
        STATS["descartadas"] += 1
        return []

    rbe.DefaultAutoRaterResponseParser.parse = parse
    logging.getLogger("google_adk." + rbe.__name__).addHandler(_ContadorVacias())
    _instalado = True


def resumen() -> str:
    """Una línea con cuántas muestras del juez se parsearon, se rescataron o se perdieron."""
    m = STATS["muestras"]
    return (f"muestras del juez de rúbricas={m}  parseadas={STATS['originales']}  "
            f"rescatadas={STATS['rescatadas']}  descartadas={STATS['descartadas']}  "
            f"vacías={STATS['vacias']}")
