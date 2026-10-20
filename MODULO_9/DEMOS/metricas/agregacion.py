# agregacion.py — cómo se combinan los resultados: promedio, conteo, confiabilidad
# entre corridas (pass@k / pass^k), intervalos de confianza (Wilson) y acuerdo entre
# evaluadores (Cohen κ).
#
# Fuentes:
#   pass@k y pass^k   τ-bench, Yao et al. 2024, §3 "Pass^k metric" (arXiv 2406.12045):
#                       pass^k = E_tarea[ C(c,k) / C(n,k) ]
#                       pass@k = 1 − E_tarea[ C(n−c,k) / C(n,k) ]
#                     con n corridas por tarea y c éxitos. Son estimadores insesgados.
#   Wilson            intervalo de confianza de una proporción (Wilson, 1927).
#   Cohen κ           acuerdo entre dos evaluadores corregido por azar (Cohen, 1960).
from __future__ import annotations

import math
from typing import Iterable, Sequence


# ── Resumen de un conjunto de casos ─────────────────────────────────────────

def media(valores: Iterable[float]) -> float:
    """Promedio simple; nan si no hay valores (no hay nada que promediar)."""
    xs = list(valores)
    return sum(xs) / len(xs) if xs else float("nan")


def tasa(booleanos: Iterable[bool]) -> float:
    """Fracción de verdaderos: el promedio de una métrica de aprobado / reprobado."""
    return media(1.0 if b else 0.0 for b in booleanos)


def conteo(valores: Iterable[int]) -> int:
    """Para métricas de conteo (acciones irreversibles de más): se suma."""
    return sum(valores)


# ── Confiabilidad entre corridas ────────────────────────────────────────────
# Con n corridas de la misma tarea y c éxitos entre ellas, se estima qué pasaría si se
# eligieran k corridas al azar. k = 1 es la tasa de éxito común; al subir k, pass^k
# exige que TODAS salgan bien (cae) y pass@k que ALGUNA salga bien (sube).

def _validar(n: int, c: int, k: int) -> None:
    if not (0 <= c <= n) or k < 1 or k > n:
        raise ValueError(f"se requiere 0 <= c <= n y 1 <= k <= n (n={n}, c={c}, k={k})")


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Probabilidad de que k corridas elegidas al azar entre las n sean TODAS exitosas."""
    _validar(n, c, k)
    return math.comb(c, k) / math.comb(n, k)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probabilidad de que AL MENOS UNA de k corridas elegidas al azar sea exitosa."""
    _validar(n, c, k)
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def promedio_por_tarea(estimador, resultados: dict[str, tuple[int, int]], k: int) -> float:
    """Promedia un estimador (pass_hat_k o pass_at_k) entre tareas.
    `resultados` mapea tarea -> (n corridas, c éxitos). Se promedia por TAREA,
    no por corrida (así lo define τ-bench)."""
    return media(estimador(n, c, k) for n, c in resultados.values())


def wilson(c: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson al ~95 % para una proporción c/n (z = 1.96).
    A diferencia del intervalo «normal», nunca se sale de [0, 1] y no se degenera
    cuando c = 0 o c = n. Con n = 0 devuelve (0, 1): no se sabe nada."""
    if n == 0:
        return (0.0, 1.0)
    p = c / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centro - margen), min(1.0, centro + margen))


# ── Acuerdo entre evaluadores (juez vs. etiqueta humana) ────────────────────

def matriz_confusion(juez: Sequence[bool], humano: Sequence[bool]) -> dict[str, int]:
    """'Positivo' = el evaluador marca el problema (p. ej. 'alucina').
    Claves: vp = verdadero positivo (ambos lo marcan), fp = falso positivo (solo el juez),
    fn = falso negativo (solo la persona), vn = verdadero negativo (ninguno lo marca)."""
    if len(juez) != len(humano):
        raise ValueError("las dos listas deben tener el mismo largo")
    return {
        "vp": sum(j and h for j, h in zip(juez, humano)),
        "fp": sum(j and not h for j, h in zip(juez, humano)),
        "fn": sum(h and not j for j, h in zip(juez, humano)),
        "vn": sum((not j) and (not h) for j, h in zip(juez, humano)),
    }


def acuerdo(juez: Sequence[bool], humano: Sequence[bool]) -> float:
    """Fracción de casos en que juez y persona dicen lo mismo: (vp + vn) / total.
    Engaña cuando una clase es rara: por eso se mide también κ."""
    m = matriz_confusion(juez, humano)
    total = sum(m.values())
    return (m["vp"] + m["vn"]) / total if total else float("nan")


def cohen_kappa(juez: Sequence[bool], humano: Sequence[bool]) -> float:
    """κ = (po − pe) / (1 − pe). Indefinido (nan) si el azar ya explica todo (pe = 1).
    po = acuerdo observado; pe = acuerdo que se esperaría por azar dadas las
    frecuencias con que cada uno marca «problema». κ = 1 es acuerdo perfecto; κ = 0,
    el que daría el azar."""
    m = matriz_confusion(juez, humano)
    n = sum(m.values())
    if n == 0:
        return float("nan")
    po = (m["vp"] + m["vn"]) / n
    p_juez_pos = (m["vp"] + m["fp"]) / n         # con qué frecuencia el juez marca problema
    p_hum_pos = (m["vp"] + m["fn"]) / n          # y la persona
    pe = p_juez_pos * p_hum_pos + (1 - p_juez_pos) * (1 - p_hum_pos)
    if math.isclose(pe, 1.0):
        return float("nan")
    return (po - pe) / (1 - pe)
