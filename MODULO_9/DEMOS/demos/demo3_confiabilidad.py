# demo3_confiabilidad.py — DEMO 3 · «¿Cuántas veces sale bien?»
#
# Las demos 1 y 2 miden con corridas ya escritas. Esta corre el agente REAL: los siete casos del
# corpus, n veces cada uno, con las dos versiones de la instrucción (V1: lo que se escribe la
# primera semana; V2: con las reglas de negocio explícitas). Un agente es un modelo y no es
# determinista: una sola corrida por caso no dice cuán confiable es. Acá se repite, y se
# reporta una tasa con su intervalo, pass@k y pass^k en lugar de un único número.
#
# ── Lo que se fijó ANTES de la primera corrida ──────────────────────────────
#   Éxito de una corrida (el veredicto, mide RESULTADO):
#       el estado final de la tienda es el esperado del caso  Y
#       cero acciones irreversibles de más (issue_refund / cancel_order que el caso no
#       autorizaba: otro monto, otro pedido o repetida).
#     Una llamada irreversible que la tienda rechazó (pedido inexistente, monto mayor al
#     total) cuenta como «de más» igual: es un intento de acción irreversible sin
#     autorización, aunque no haya cambiado el mundo. Es la misma definición de la demo 1.
#     La columna «solo estado» muestra cuánto cambia el resultado si se ignoran esos intentos.
#   Diagnóstico (se mira, no decide): éxito por trayectoria = tool_trajectory_avg_score de ADK
#       en modo IN_ORDER (tolera llamadas de más entre las esperadas; el modo se eligió antes de
#       correr).
#   n por defecto = 8 corridas por caso y por versión; k = 1, 2, 4 y 8 (k no puede superar n).
#   Hipótesis previa: V2 ≥ V1 en pass^k. Si V2 falla algún caso, se reporta; la instrucción V2
#       no se retoca después de ver los resultados.
#
# ── Lo que NO mide ──────────────────────────────────────────────────────────
#   Si lo que el agente le dice al cliente es verdad: una respuesta que agrega un hecho inventado
#   (como la corrida R11 de la demo 1) cuenta como éxito si el mundo quedó bien. Eso lo miran los
#   jueces de la demo 2. Tampoco usa jueces, así que el único costo es el del propio agente.
#   Una corrida que termina en error del servicio (cuota, red) NO es una falla del agente: se
#   cuenta aparte y se saca de n.
#
# Llama al modelo (~7 casos × n × 2 versiones, varias llamadas por corrida): a precio de lista
# cuesta centavos. Con la capa gratuita no se paga, pero se consume cuota. Imprime la estimación
# ANTES de llamar y aborta si el peor escenario supera --max-usd.
#
# Qué hace, en orden:
#   1. `main` estima el costo y se detiene si el peor escenario supera el tope,
#   2. `correr` corre las dos versiones (`correr_muchas`, con concurrencia acotada),
#   3. `resumir_por_caso` evalúa cada corrida (`evaluar_corrida`) y junta los conteos por caso,
#   4. `imprimir_*` muestra: éxito por caso, pass^k y pass@k, contraste con la trayectoria,
#      qué falló, y costo real.
#
# Uso (desde esta carpeta, con el entorno virtual activado):
#   python demos/demo3_confiabilidad.py --dry-run                      # solo estima, no llama al modelo
#   python demos/demo3_confiabilidad.py --solo taza_rota --n 1        # prueba barata
#   python -u demos/demo3_confiabilidad.py --n 8 --max-usd 0.60       # la corrida completa (-u: sin buffer)
#   python demos/demo3_confiabilidad.py --guardar corridas.json       # además guarda cada corrida (JSON)
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import warnings
from dataclasses import asdict
from pathlib import Path

# ADK marca algunas piezas como EXPERIMENTAL; el aviso ensucia la salida.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from entorno.corpus import CORPUS, POR_ID, Caso  # noqa: E402
from entorno.tienda import (  # noqa: E402
    INSTRUCCION_V1, INSTRUCCION_V2, IRREVERSIBLES, Corrida, correr_muchas, verificar_credenciales,
)
from metricas import adk_nativo  # noqa: E402
from metricas.agregacion import pass_at_k, pass_hat_k, promedio_por_tarea, wilson  # noqa: E402
from metricas.costo import Tokens  # noqa: E402
from metricas.planificacion import acciones_irreversibles_no_autorizadas  # noqa: E402


# ── Qué se compara y cuánto cuesta ──────────────────────────────────────────

INSTRUCCIONES = {"V1": INSTRUCCION_V1, "V2": INSTRUCCION_V2}
MODO_TRAYECTORIA = "IN_ORDER"
KS = (1, 2, 4, 8)

# (tokens de entrada, tokens de salida) por CORRIDA del agente, en tres escenarios; «alto»
# se usa para el tope de gasto. «esperado» sigue lo medido el 2026-10-19 en una prueba de humo
# (ADK 2.12, Gemini 2.5 Flash, 14 corridas, V1 y V2): ~1.130 de entrada y ~470 de salida por
# corrida, con 2,1 llamadas al modelo en promedio. Es una muestra chica y una corrida con más
# vueltas o más razonamiento cuesta más: por eso «alto» duplica lo medido. El costo real se
# mide siempre (bloque 5 del reporte).
AGENTE_POR_CORRIDA = {"bajo": (900, 350), "esperado": (1200, 500), "alto": (2400, 1000)}


def estimar(corridas: int) -> dict[str, Tokens]:
    """Costo estimado de `corridas` corridas del agente, en cada escenario."""
    return {esc: Tokens(corridas * e, corridas * s) for esc, (e, s) in AGENTE_POR_CORRIDA.items()}


# ── Evaluar una corrida ─────────────────────────────────────────────────────

def evaluar_corrida(c: Corrida, caso: Caso) -> dict:
    """Aplica la definición de éxito (y el diagnóstico) a UNA corrida del agente real."""
    esperado = {"reembolsos": sorted(caso.estado_esperado["reembolsos"]),
                "cancelados": sorted(caso.estado_esperado["cancelados"])}
    estado_ok = c.estado == esperado
    de_mas = acciones_irreversibles_no_autorizadas(c.llamadas, caso.esperadas, IRREVERSIBLES)
    return {
        "estado_ok": estado_ok,
        "irreversibles_de_mas": de_mas,
        "exito": estado_ok and de_mas == 0,                                  # el veredicto
        "trayectoria": adk_nativo.trayectoria(c.llamadas, caso.esperadas, MODO_TRAYECTORIA) >= 1.0,
    }


def resumir_por_caso(corridas: list[Corrida], casos: list[Caso]) -> dict[str, dict]:
    """Conteos por caso: n (corridas válidas), c (éxitos), errores (no cuentan en n), y los
    desacuerdos entre el resultado y la trayectoria. `fallas` guarda las corridas sin éxito."""
    res = {c.id: {"n": 0, "c": 0, "c_estado": 0, "c_traj": 0, "errores": 0,
                  "traj_aprueba_y_falla": 0, "traj_rechaza_y_sirve": 0, "fallas": []} for c in casos}
    for corrida in corridas:
        r = res[corrida.caso_id]
        if corrida.error:
            r["errores"] += 1
            continue
        ev = evaluar_corrida(corrida, POR_ID[corrida.caso_id])
        r["n"] += 1
        r["c"] += ev["exito"]
        r["c_estado"] += ev["estado_ok"]
        r["c_traj"] += ev["trayectoria"]
        r["traj_aprueba_y_falla"] += ev["trayectoria"] and not ev["exito"]
        r["traj_rechaza_y_sirve"] += (not ev["trayectoria"]) and ev["exito"]
        if not ev["exito"]:
            r["fallas"].append((corrida, ev))
    return res


# ── Correr el agente real ───────────────────────────────────────────────────

async def correr(casos: list[Caso], n: int, concurrencia: int) -> dict[str, list[Corrida]]:
    """Las dos versiones, una después de la otra; dentro de cada una, en paralelo acotado."""
    pedidos = [c for c in casos for _ in range(n)]
    salida = {}
    for nombre, instruccion in INSTRUCCIONES.items():
        print(f"corriendo {nombre}: {len(pedidos)} corridas (concurrencia {concurrencia})…", flush=True)
        t0 = time.perf_counter()
        salida[nombre] = list(await correr_muchas(pedidos, instruccion, concurrencia))
        print(f"  listo en {time.perf_counter() - t0:.0f} s", flush=True)
    return salida


# ── Impresión ───────────────────────────────────────────────────────────────

def _celda(r: dict) -> str:
    """«c/n  tasa  [Wilson 95 %]» de un caso."""
    if r["n"] == 0:
        return f"{'sin corridas':<27}"
    lo, hi = wilson(r["c"], r["n"])
    return f"{r['c']:>3}/{r['n']:<3} {r['c'] / r['n']:>5.2f}  [{lo:.2f}, {hi:.2f}]"


def imprimir_definiciones() -> None:
    print("── Definiciones fijadas antes de correr ──")
    print("  éxito de una corrida = estado final esperado  Y  cero acciones irreversibles de más")
    print(f"  diagnóstico: trayectoria ADK en modo {MODO_TRAYECTORIA} · hipótesis previa: V2 ≥ V1 en pass^k")
    print("  no mide si lo que se le dice al cliente es verdad (eso es la demo 2)")


def imprimir_exito_por_caso(res: dict[str, dict[str, dict]]) -> None:
    print("\n══ 1 · Éxito por caso: éxitos/corridas, tasa y intervalo de Wilson al 95 % ═══════════")
    print(f"{'caso':<21}{'V1':^27}   {'V2':^27}")
    for caso_id in res["V1"]:
        print(f"{caso_id:<21}{_celda(res['V1'][caso_id])}   {_celda(res['V2'][caso_id])}")
    medias = {v: promedio_por_tarea(pass_at_k, {i: (r["n"], r["c"]) for i, r in res[v].items() if r["n"]}, 1)
              for v in res}
    print(f"{'promedio entre casos':<21}{'':<8}{medias['V1']:>5.2f}{'':<14}   {'':<8}{medias['V2']:>5.2f}")
    print("  Con tan pocas corridas por caso los intervalos son anchos: eso es lo que dicen cuánto se sabe.")


def _ks_validos(res: dict[str, dict[str, dict]]) -> list[int]:
    n_min = min(r["n"] for v in res.values() for r in v.values())
    return [k for k in KS if k <= n_min]


def imprimir_pass_k(res: dict[str, dict[str, dict]]) -> dict:
    """Imprime pass^k y pass@k promediados por caso; devuelve {version: {k: pass^k}}."""
    ks = _ks_validos(res)
    print("\n══ 2 · pass^k (¿salen TODAS bien?) y pass@k (¿sale ALGUNA bien?), promedio entre casos ══")
    if not ks:
        print("  algún caso quedó sin corridas válidas: no se puede calcular (ver los errores abajo).")
        return {}
    print(f"{'':<14}" + "".join(f"{'k = ' + str(k):>9}" for k in ks))
    hat = {}
    for v in res:
        tareas = {i: (r["n"], r["c"]) for i, r in res[v].items()}
        hat[v] = {k: promedio_por_tarea(pass_hat_k, tareas, k) for k in ks}
        print(f"{'pass^k ' + v:<14}" + "".join(f"{hat[v][k]:>9.2f}" for k in ks))
    for v in res:
        tareas = {i: (r["n"], r["c"]) for i, r in res[v].items()}
        print(f"{'pass@k ' + v:<14}" + "".join(f"{promedio_por_tarea(pass_at_k, tareas, k):>9.2f}" for k in ks))
    cumple = [k for k in ks if hat["V2"][k] >= hat["V1"][k]]
    print(f"  Hipótesis previa (V2 ≥ V1 en pass^k): se cumple en k = {cumple or 'ningún k'}"
          + ("" if len(cumple) == len(ks) else f"; NO se cumple en k = {[k for k in ks if k not in cumple]}"))
    return hat


def imprimir_contraste(res: dict[str, dict[str, dict]]) -> None:
    print("\n══ 3 · El mismo agente, medido por resultado y por camino ════════════════════════════")
    print(f"{'':<10}{'corridas':>9}{'éxito':>8}{'solo estado':>13}{'trayectoria':>13}"
          f"{'camino ✓, resultado ✗':>24}{'camino ✗, resultado ✓':>24}")
    for v in res:
        tot = {k: sum(r[k] for r in res[v].values()) for k in
               ("n", "c", "c_estado", "c_traj", "traj_aprueba_y_falla", "traj_rechaza_y_sirve")}
        print(f"{v:<10}{tot['n']:>9}{tot['c']:>8}{tot['c_estado']:>13}{tot['c_traj']:>13}"
              f"{tot['traj_aprueba_y_falla']:>24}{tot['traj_rechaza_y_sirve']:>24}")
    print(f"  éxito = estado ∧ cero irreversibles de más · trayectoria = {MODO_TRAYECTORIA} de ADK.")
    print("  «camino ✓, resultado ✗»: la trayectoria aprobó una corrida que dejó el mundo mal (falso aprobado).")
    print("  «camino ✗, resultado ✓»: la trayectoria rechazó una corrida que dejó el mundo bien (falso rechazo).")


def imprimir_fallas(res: dict[str, dict[str, dict]], maximo: int) -> None:
    print("\n══ 4 · Qué falló (las corridas sin éxito) ════════════════════════════════════════════")
    mostradas = 0
    total = sum(len(r["fallas"]) for v in res.values() for r in v.values())
    if total == 0:
        print("  ninguna corrida falló. Antes de creerlo conviene abrir algunas respuestas (--guardar).")
        return
    for v in res:
        for caso_id, r in res[v].items():
            for corrida, ev in r["fallas"]:
                if mostradas >= maximo:
                    break
                mostradas += 1
                motivo = []
                if not ev["estado_ok"]:
                    motivo.append("estado distinto del esperado")
                if ev["irreversibles_de_mas"]:
                    motivo.append(f"{ev['irreversibles_de_mas']} irreversible(s) de más")
                llamadas = ", ".join(f"{c['tool']}({', '.join(str(x) for x in c['params'].values())})"
                                     for c in corrida.llamadas) or "ninguna"
                print(f"  {v} · {caso_id}: {' y '.join(motivo)}")
                print(f"      llamadas: {llamadas}")
                print(f"      estado:   {corrida.estado}")
                print(f"      dijo:     {corrida.respuesta.strip()[:150]!r}")
    if total > mostradas:
        print(f"  … y {total - mostradas} corrida(s) más sin éxito (se muestran las primeras {maximo}).")


def imprimir_costo(corridas: dict[str, list[Corrida]], res: dict[str, dict[str, dict]], est, peor: float) -> None:
    todas = [c for v in corridas.values() for c in v]
    t = Tokens(sum(c.tok_entrada for c in todas), sum(c.tok_salida for c in todas))
    errores = sum(r["errores"] for v in res.values() for r in v.values())
    print("\n══ 5 · Costo REAL y corridas con error ═══════════════════════════════════════════════")
    print(f"corridas={len(todas)}  llamadas al modelo={sum(c.llamadas_modelo for c in todas)}  "
          f"entrada={t.entrada:,.0f}  salida(+razonamiento)={t.salida:,.0f}  USD={t.usd:.4f}   "
          f"(estimado esperado ${est['esperado'].usd:.3f}, peor ${peor:.3f})")
    print(f"≈ ${t.usd / max(len(todas), 1):.4f} por corrida · {sum(c.segundos for c in todas) / max(len(todas), 1):.1f} s por corrida")
    if errores:
        print(f"AVISO: {errores} corrida(s) terminaron en error del servicio y NO cuentan en n "
              f"(no son fallas del agente):")
        vistos = set()
        for c in todas:
            if c.error and c.error not in vistos:
                vistos.add(c.error)
                print(f"  {c.error}")
    else:
        print("Corridas con error del servicio: 0.")


def imprimir_lectura() -> None:
    print("\n══ 6 · Cómo leerlo ═══════════════════════════════════════════════════════════════════")
    print("  • Es UNA serie de corridas de un agente no determinista: otra serie daría otros números.")
    print("  • El éxito mide el resultado. Una respuesta que inventa un dato pero deja el mundo bien")
    print("    cuenta como éxito; para verla hacen falta los jueces (demo 2).")
    print("  • pass^k baja al subir k aunque la tasa por corrida sea alta: es la pregunta «¿puedo")
    print("    confiar en que lo haga bien k veces seguidas?».")


# ── main ─────────────────────────────────────────────────────────────────────

async def main(a) -> int:
    casos = [c for c in CORPUS if not a.solo or c.id in a.solo]
    if not casos:
        print(f"ningún caso coincide con --solo {a.solo}")
        return 1
    # 1. Estimar el costo ANTES de llamar.
    total = len(casos) * a.n * len(INSTRUCCIONES)
    est = estimar(total)
    print(f"── Estimación previa: {len(casos)} casos × n = {a.n} × {len(INSTRUCCIONES)} versiones → {total} corridas del agente ──")
    for esc in ("bajo", "esperado", "alto"):
        t = est[esc]
        print(f"  {esc:<9} entrada {t.entrada:>9,.0f}  salida {t.salida:>8,.0f}   USD {t.usd:.3f}")
    peor = est["alto"].usd
    # 2. Detenerse antes de gastar: con --dry-run solo se estima; si el peor escenario
    #    supera el tope, se aborta (salvo --forzar).
    if a.dry_run:
        print("--dry-run: no se llamó al modelo.")
        return 0
    if peor > a.max_usd and not a.forzar:
        print(f"ABORTADO: el peor escenario (${peor:.3f}) supera --max-usd ${a.max_usd:.2f}.")
        return 2

    # 3. Correr el agente real y evaluar cada corrida.
    verificar_credenciales()
    imprimir_definiciones()
    corridas = await correr(casos, a.n, a.concurrencia)
    errores = [c.error for cs in corridas.values() for c in cs if c.error]
    if len(errores) == sum(len(cs) for cs in corridas.values()):
        print(f"\nTodas las corridas terminaron en error del servicio: no hay nada que medir.\n  {errores[0]}")
        print("Revisá GOOGLE_API_KEY y MODEL_NAME en .env, y tu cuota (https://aistudio.google.com/rate-limit).")
        return 1
    res = {v: resumir_por_caso(cs, casos) for v, cs in corridas.items()}

    # 4. Imprimir los bloques del reporte.
    imprimir_exito_por_caso(res)
    imprimir_pass_k(res)
    imprimir_contraste(res)
    imprimir_fallas(res, a.mostrar)
    imprimir_costo(corridas, res, est, peor)
    imprimir_lectura()
    if a.guardar:
        guardar(a.guardar, corridas)
    return 0


def guardar(ruta: str, corridas: dict[str, list[Corrida]]) -> None:
    """Guarda cada corrida (llamadas, respuesta, estado, tokens) y su evaluación, para auditarlas."""
    filas = []
    for v, cs in corridas.items():
        for c in cs:
            fila = {"version": v, **asdict(c)}
            if not c.error:
                fila["evaluacion"] = evaluar_corrida(c, POR_ID[c.caso_id])
            filas.append(fila)
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ncorridas guardadas en {ruta}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Demo 3 · confiabilidad del agente real (pass^k, V1 vs V2)")
    ap.add_argument("--n", type=int, default=8, help="corridas por caso y por versión (default 8)")
    ap.add_argument("--solo", nargs="*", help="ids de casos a correr (prueba barata)")
    ap.add_argument("--concurrencia", type=int, default=2,
                    help="corridas en paralelo (default 2; bajalo a 1 si tu cuota es chica)")
    ap.add_argument("--max-usd", type=float, default=0.60, help="tope de gasto: aborta si el peor escenario lo supera")
    ap.add_argument("--forzar", action="store_true", help="ignora el tope --max-usd")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime la estimación de costo; no llama al modelo")
    ap.add_argument("--mostrar", type=int, default=8, help="cuántas corridas sin éxito mostrar en el bloque 4")
    ap.add_argument("--guardar", metavar="RUTA.json", help="guarda cada corrida y su evaluación en un JSON")
    sys.exit(asyncio.run(main(ap.parse_args())))
