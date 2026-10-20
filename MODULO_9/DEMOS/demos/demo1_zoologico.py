# demo1_zoologico.py — DEMO 1 · «¿Qué métrica ve qué falla?»
#
# Once corridas del mismo pedido (la taza rota A89268), cada una con una falla o una
# virtud distinta, medidas con TODAS las métricas del módulo: las de planificación
# (metricas/planificacion.py), las evaluadoras nativas de ADK 2.12 y el estado final
# del mundo.
#
# No llama a ningún modelo: cuesta $0, tarda un segundo y da lo mismo en cada corrida.
# Las etiquetas «aceptable / no aceptable» se fijaron ANTES de medir (ver zoologico.py).
#
# La salida tiene seis secciones, cada una en su función `seccion_*`:
#   1 · el caso            4 · ¿acierta cada métrica? (veredicto contra la etiqueta)
#   2 · las once corridas  5 · lectura: qué se aprende de la matriz
#   3 · valores crudos     6 · los tres casos vacíos (qué devuelve cada convención)
#
# Uso (desde esta carpeta, con el entorno virtual activado):
#   python demos/demo1_zoologico.py
#   python demos/demo1_zoologico.py --sin-color      # para guardar la salida en un archivo
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from entorno import zoologico as z  # noqa: E402
from entorno.corpus import lookup  # noqa: E402
from metricas import adk_nativo, planificacion as m  # noqa: E402
from metricas.referencias import tool_metrics_simple, tool_metrics_v1  # noqa: E402


# ── Utilidades de impresión ─────────────────────────────────────────────────

COLOR = sys.stdout.isatty()     # con --sin-color (o redirigiendo la salida) no hay colores


def c(texto: str, codigo: str) -> str:
    """Envuelve `texto` en el código de color ANSI indicado (si hay color)."""
    return f"\033[{codigo}m{texto}\033[0m" if COLOR else texto


def titulo(t: str) -> None:
    print("\n" + c("═" * 4 + f" {t} " + "═" * max(4, 100 - len(t)), "1;33"))


def valor(x) -> str:
    """Un valor medido, listo para la tabla: sí / NO, entero o dos decimales."""
    if isinstance(x, bool):
        return "sí" if x else "NO"
    if isinstance(x, int):
        return str(x)
    return f"{x:.2f}"


# ── Sección 1 · El caso ─────────────────────────────────────────────────────

def seccion_caso() -> None:
    titulo("1 · El caso")
    caso = z.CASO
    print(f"Cliente: «{caso.mensaje}»")
    print("Pedido A89268: taza (19,99) + remera (20,00). Hay que devolver SOLO la taza.")
    print("Trayectoria esperada :", " → ".join(
        f"{x['tool']}({', '.join(f'{v}' for v in x['params'].values())})" for x in caso.esperadas))
    print("Frases esperadas     :", caso.frases)
    print("Estado final esperado: 1 reembolso de 19,99 sobre MUG-001; nada cancelado")


# ── Sección 2 · Las once corridas ───────────────────────────────────────────

def seccion_corridas() -> None:
    titulo("2 · Once corridas, con la etiqueta humana fijada ANTES de medir")
    print("Aceptable = estado final correcto · sin acciones irreversibles de más · respuesta veraz ·")
    print("            informa pedido, monto y plazo.  El camino NO importa si no afecta esas cuatro.\n")
    for i, x in enumerate(z.CORRIDAS, 1):
        marca = c("ACEPTABLE ", "32") if x.aceptable else c("NO ACEPTABLE", "31")
        print(f"R{i:<2} {x.id:<20} {marca:<12}  {x.que_pasa}")


# ── Sección 3 · Valores crudos ──────────────────────────────────────────────

# (clave en `medir`, encabezado de la columna). Las cuatro primeras son del módulo,
# las cuatro siguientes de ADK, y las dos últimas miran el mundo.
COLUMNAS = [
    ("tool_recall", "recall"), ("tool_precision", "precis"), ("param_accuracy", "params"),
    ("phrase_recall", "frases"), ("traj_exact", "EXACT"), ("traj_in_order", "IN_ORD"),
    ("traj_any_order", "ANY_ORD"), ("rouge1", "ROUGE1"), ("estado_ok", "estado"),
    ("irreversibles_de_mas", "irrev+"),
]


def seccion_valores(med: dict) -> None:
    titulo("3 · Lo que mide cada métrica (valores crudos)")
    print(" " * 26 + "".join(f"{etiqueta:>8}" for _, etiqueta in COLUMNAS))
    print(" " * 26 + c("──── módulo ────".center(32) + "──── ADK 2.12 (local) ────".center(24)
                        + "  mundo", "2"))
    for i, x in enumerate(z.CORRIDAS, 1):
        fila = "".join(f"{valor(med[x.id][k]):>8}" for k, _ in COLUMNAS)
        print(f"R{i:<2} {x.id:<22}{fila}")


# ── Sección 4 · ¿Acierta cada métrica? ──────────────────────────────────────

def seccion_veredictos(res: dict, med: dict) -> None:
    titulo("4 · ¿Acierta cada métrica? (su veredicto contra la etiqueta)")
    print("  ·  = coincide con la etiqueta   FA = FALSO APROBADO (dejó pasar una corrida mala)")
    print("  FR = FALSO RECHAZO (bloqueó una corrida buena)\n")
    print(f"{'':<46}" + "".join(f"R{i:<3}" for i in range(1, len(z.CORRIDAS) + 1)) + " errores")
    for nombre, f in [*z.VEREDICTOS, z.PANEL]:
        celdas = []
        for x in z.CORRIDAS:
            veredicto = f(med[x.id])
            if veredicto == x.aceptable:
                celdas.append(c("·   ", "2"))
            elif veredicto:
                celdas.append(c("FA  ", "1;31"))
            else:
                celdas.append(c("FR  ", "1;35"))
        errores = res[nombre]["errores"]
        sep = "\n" if nombre == z.PANEL[0] else ""
        print(f"{sep}{nombre:<46}{''.join(celdas)} {c(str(errores), '1' if errores else '1;32')}")


# ── Sección 5 · Lectura ─────────────────────────────────────────────────────

def seccion_lectura(res: dict, med: dict) -> None:
    titulo("5 · Lectura")
    individuales = {k: v for k, v in res.items() if not k.startswith("panel")}
    mejor = min(individuales.items(), key=lambda kv: kv[1]["errores"])
    panel = res[z.PANEL[0]]
    n_exact = len(res["trayectoria EXACT (ADK)"]["falsos_rechazos"])
    print(f"• Ninguna métrica sola acierta las {len(z.CORRIDAS)}. La mejor es «{mejor[0]}» con {mejor[1]['errores']} errores.")
    print(f"• El panel de tres (estado ∧ frases ∧ irreversibles = 0) deja {panel['errores']} error: "
          f"{', '.join(panel['falsos_aprobados'])}.")
    print("  Esa corrida dice algo que nadie verificó («te envié un comprobante por email»):")
    print("  para verla hace falta comparar la respuesta con lo que las herramientas devolvieron.")
    print("  → ese es el trabajo de un juez de fundamentación: Demo 2.")
    print(f"• Las trayectorias de ADK castigan caminos válidos (EXACT rechaza {n_exact} corridas aceptables)")
    print("  y IN_ORDER / ANY_ORDER dejan pasar el doble reembolso: elegir el modo es elegir qué falla tolerás.")
    print(f"• ROUGE-1 aprueba el reembolso equivocado ({med['monto_equivocado']['rouge1']:.2f}) y reprueba "
          f"la paráfrasis correcta ({med['parafrasis_correcta']['rouge1']:.2f}).")


# ── Sección 6 · Los tres casos vacíos ───────────────────────────────────────

def seccion_vacios() -> None:
    titulo("6 · Los tres casos vacíos: ¿qué devuelve tu métrica cuando no hay nada que medir?")
    L = lookup("A89268")
    R = z.CORRIDAS[0].llamadas[1]
    casos = [
        ("a) nada esperado, nada hecho", [], []),
        ("b) nada esperado, llamó issue_refund", [R], []),
        ("c) esperaba lookup_order, no hizo nada", [], [L]),
    ]
    # Una columna por convención: la simple, la primera versión del módulo, la V2 (la que
    # se adopta) y los tres modos de trayectoria de ADK.
    print(f"{'':<42}{'simple':>13}{'versión 1':>14}{'V2':>11}   ADK (EXACT / IN_ORDER / ANY_ORDER)")
    for nombre, pred, esp in casos:
        nombres = [p["tool"] for p in pred]
        simple = tool_metrics_simple(nombres, esp)
        v1 = tool_metrics_v1(nombres, esp)
        v2 = (m.tool_recall(pred, esp), m.tool_precision(pred, esp))
        adk = " / ".join(f"{adk_nativo.trayectoria(pred, esp, modo):.0f}" for modo in adk_nativo.MODOS)
        f = lambda r, p: f"{r:.1f}/{p:.1f}"  # noqa: E731
        print(f"{nombre:<42}{f(simple['tool_recall'], simple['tool_precision']):>13}"
              f"{f(v1['tool_recall'], v1['tool_precision']):>14}{f(*v2):>11}   {adk}")
    print("\n(recall/precisión)  Caso b: la convención simple da 1.0/1.0 aunque el agente haya reembolsado")
    print("sin que nadie lo pidiera; la v1 y la V2 dan precisión 0.0.  Caso a: la v1 daba precisión 0.0")
    print("a un agente que correctamente no hizo nada.  En ADK, IN_ORDER y ANY_ORDER aprueban el caso b")
    print("«por vacuidad»: «todo lo esperado (nada) está presente» es verdad; solo EXACT lo bloquea.")


# ── Programa principal ──────────────────────────────────────────────────────

def main() -> int:
    global COLOR
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-color", action="store_true")
    if ap.parse_args().sin_color:
        COLOR = False

    r = z.matriz()      # mide las once corridas una sola vez; las secciones leen de acá
    seccion_caso()
    seccion_corridas()
    seccion_valores(r["medidas"])
    seccion_veredictos(r["resumen"], r["medidas"])
    seccion_lectura(r["resumen"], r["medidas"])
    seccion_vacios()
    return 0


if __name__ == "__main__":
    sys.exit(main())
