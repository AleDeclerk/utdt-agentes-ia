# demo2_juez.py — DEMO 2 · «¿Y quién evalúa al juez?»
#
# La Demo 1 terminó con una corrida que ninguna regla ve: la respuesta agrega un hecho
# que nadie verificó. Para eso hay jueces LLM. Pero un juez es otro modelo: puede
# aprobar todo, rechazar todo o equivocarse. Esta demo lo mide como a cualquier métrica:
# contra etiquetas humanas, sobre catorce respuestas conocidas (siete fieles y siete con un
# problema), con matriz de confusión y κ de Cohen.
#
# Jueces nativos de ADK 2.12 usados (los dos llaman a Gemini):
#   hallucinations_v1                        segmenta la respuesta en oraciones y clasifica
#                                            cada una como respaldada / no respaldada /
#                                            contradictoria / no aplicable. Score = fracción
#                                            de oraciones respaldadas o no aplicables.
#   rubric_based_final_response_quality_v1   el juez recibe rúbricas en texto y contesta sí/no
#                                            para cada una, num_samples veces; el veredicto
#                                            por rúbrica es por mayoría y el score, el promedio.
#
# Llama al modelo (~70 llamadas al juez): a precio de lista, la estimación previa da USD 0.48
# esperado y USD 0.71 en el peor caso, y una corrida de referencia costó USD 0.21. Con la capa
# gratuita no se paga, pero se consume cuota. Imprime la estimación ANTES de llamar y aborta si
# el peor escenario supera --max-usd.
#
# Qué hace, en orden (cada paso es una función):
#   1. `main` estima el costo y se detiene si el peor escenario supera el tope,
#   2. `juzgar` corre los dos jueces sobre los catorce ítems (`evaluar_item`),
#   3. `veredictos` y `acuerdo_por_criterio` comparan juez y persona (matriz de confusión, κ),
#   4. `imprimir_*` cuenta el resultado en el orden en que se lee: qué se mide, las respuestas
#      juzgadas, qué dijo cada juez (✓ coincide / ✗ discrepa), cuánto coincide con la persona, dónde
#      se equivocó y qué razonó, la lectura y el costo real.
#
# Uso (desde esta carpeta, con el entorno virtual activado):
#   python demos/demo2_juez.py --dry-run                 # solo estima, no llama al modelo
#   python demos/demo2_juez.py --max-usd 0.75            # corre los catorce ítems
#   python demos/demo2_juez.py --solo accion_inventada   # un solo ítem (prueba barata)
#   python demos/demo2_juez.py --comparar-razonamiento --max-usd 0.90
#         # además repite todo con el razonamiento del juez apagado: mismo juez, otro costo
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import textwrap
import time
import warnings
from pathlib import Path

# ADK marca su registro de evaluadores como EXPERIMENTAL; el aviso ensucia la salida.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from google.genai import types  # noqa: E402

from google.adk.evaluation.eval_metrics import (  # noqa: E402
    EvalMetric, HallucinationsCriterion, JudgeModelOptions, PrebuiltMetrics, RubricsBasedCriterion,
)
from google.adk.evaluation.eval_rubrics import Rubric, RubricContent  # noqa: E402
from google.adk.evaluation.metric_evaluator_registry import DEFAULT_METRIC_EVALUATOR_REGISTRY  # noqa: E402

from entorno.juez_items import ITEMS, TRAZAS, invocacion  # noqa: E402
from entorno.tienda import verificar_credenciales  # noqa: E402
from metricas import agregacion as ag  # noqa: E402
from metricas import costo, juez_tolerante  # noqa: E402


# ── Configuración de los jueces ─────────────────────────────────────────────

# El mismo modelo que usa el agente (MODEL_NAME en .env; por defecto, gemini-2.5-flash).
MODELO_JUEZ = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

# Las dos rúbricas que recibe el juez de rúbricas; cada una se contesta con sí / no.
RUBRICAS = [
    ("cita_pedido", "La respuesta menciona el número del pedido sobre el que se actuó o consultó."),
    ("sin_inventar", "La respuesta afirma solo hechos respaldados por las respuestas de las herramientas "
                     "o por las instrucciones del agente: no inventa plazos, montos, estados ni acciones."),
]

# Los tres criterios que se miden contra la persona. En los tres, «positivo» = el juez
# marca un problema (por eso «→ alucina» / «→ no cita»).
CRITERIOS = ["hallucinations_v1 → alucina", "rúbrica sin_inventar → alucina", "rúbrica cita_pedido → no cita"]


def metricas_juez(num_samples: int, presupuesto_razonamiento: int | None = None) -> dict[str, EvalMetric]:
    """`presupuesto_razonamiento`: None = el default del modelo; 0 = sin razonamiento."""
    config = None
    if presupuesto_razonamiento is not None:
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=presupuesto_razonamiento))
    opciones_h = JudgeModelOptions(judge_model=MODELO_JUEZ, judge_model_config=config)
    opciones_r = JudgeModelOptions(judge_model=MODELO_JUEZ, judge_model_config=config, num_samples=num_samples)
    return {
        "hallucinations": EvalMetric(
            metric_name=PrebuiltMetrics.HALLUCINATIONS_V1.value, threshold=1.0,
            criterion=HallucinationsCriterion(threshold=1.0, judge_model_options=opciones_h)),
        "rubricas": EvalMetric(
            metric_name=PrebuiltMetrics.RUBRIC_BASED_FINAL_RESPONSE_QUALITY_V1.value, threshold=1.0,
            criterion=RubricsBasedCriterion(
                threshold=1.0, judge_model_options=opciones_r,
                rubrics=[Rubric(rubric_id=i, rubric_content=RubricContent(text_property=t)) for i, t in RUBRICAS])),
    }


# ── Correr los jueces sobre un ítem ─────────────────────────────────────────

def _oraciones(texto: str | None) -> list[tuple[str, str, str]]:
    """La validación por oración de hallucinations_v1 es un JSON; se la lee como
    [(etiqueta, oración, razonamiento)], con la etiqueta en minúsculas (supported / unsupported /
    contradictory / disputed / not_applicable)."""
    if not texto:
        return []
    try:
        filas = json.loads(texto)
    except (ValueError, TypeError):
        return []
    return [(str(f.get("label", "?")).strip().lower(), f.get("sentence", ""), f.get("rationale", ""))
            for f in filas if isinstance(f, dict)]


def _capturar_detalle(evaluador) -> dict:
    """ADK calcula la validación por oración de hallucinations_v1 pero la descarta: lo único que
    devuelve es el score. Para poder mostrar QUÉ oración aprobó o marcó el juez, y por qué, se
    envuelve el método privado que la produce (`_evaluate_nl_response`, de ADK 2.12.0) en ESTA
    instancia del evaluador. Si ese método no existe, no se captura nada y la demo sigue igual."""
    captura = {"oraciones": [], "avisos": []}
    original = getattr(evaluador, "_evaluate_nl_response", None)
    if original is None:
        return captura

    async def envuelto(nl_response, context):
        score, detalle = await original(nl_response, context)
        if score is None:
            captura["avisos"].append(str(detalle))          # ADK explica por qué no pudo puntuar
        else:
            captura["oraciones"].extend(_oraciones(detalle))
        return score, detalle

    try:
        evaluador._evaluate_nl_response = envuelto
    except (AttributeError, TypeError, ValueError):     # un evaluador que no admite el atributo
        pass
    return captura


async def evaluar_item(item, metricas, sem) -> dict:
    """Pasa un ítem por cada juez y junta sus puntajes y razonamientos. `sem` acota
    cuántos ítems se juzgan en paralelo."""
    inv = invocacion(item)
    out: dict = {"item": item}
    async with sem:
        for nombre, metrica in metricas.items():
            # El registro de ADK devuelve el evaluador que corresponde a cada métrica.
            evaluador = DEFAULT_METRIC_EVALUATOR_REGISTRY.get_evaluator(metrica)
            captura = _capturar_detalle(evaluador) if nombre == "hallucinations" else None
            try:
                r = await evaluador.evaluate_invocations([inv], None)
            except Exception as e:  # un fallo del juez es un dato, no un crash de la demo
                out[nombre] = {"score": None, "error": f"{type(e).__name__}: {str(e)[:120]}"}
                continue
            pir = r.per_invocation_results[0] if r.per_invocation_results else None
            detalle = {"score": r.overall_score}
            if r.overall_score is None:
                detalle["error"] = "el juez no devolvió ningún score parseable"
            if nombre == "rubricas":
                # El razonamiento por rúbrica está en el resultado por invocación; el agregado
                # general trae un texto genérico de ADK.
                detalle["por_rubrica"] = {rs.rubric_id: (rs.score, rs.rationale)
                                          for rs in ((pir.rubric_scores if pir else None)
                                                     or r.overall_rubric_scores or [])}
            else:
                detalle["oraciones"] = captura["oraciones"]
                detalle["avisos"] = captura["avisos"]
            out[nombre] = detalle
    return out


# ── Comparar al juez con la persona ─────────────────────────────────────────

def veredictos(resultados: list[dict]) -> dict[str, list]:
    """Por criterio: [(ítem, lo que dice el juez, lo que dice la persona)]; True = 'hay problema'.
    El juez marca problema cuando su score es menor que 1.0; None = el juez no dio score."""
    crit: dict[str, list] = {k: [] for k in CRITERIOS}
    for r in resultados:
        for nombre, v in zip(CRITERIOS, _veredictos_item(r)):
            crit[nombre].append((r["item"], v["juez"], v["persona"]))
    return crit


def acuerdo_por_criterio(ver: dict) -> dict[str, dict]:
    """Matriz de confusión, acuerdo y κ de cada criterio. Los ítems sin score del juez
    no entran en la cuenta (se informan aparte en `sin_score`)."""
    out = {}
    for nombre, filas in ver.items():
        validas = [(j, h) for _, j, h in filas if j is not None]
        if not validas:
            out[nombre] = None
            continue
        j, h = zip(*validas)
        out[nombre] = {**ag.matriz_confusion(j, h), "acuerdo": ag.acuerdo(j, h),
                       "kappa": ag.cohen_kappa(j, h), "sin_score": len(filas) - len(validas)}
    return out


# ── Orquestar: los dos jueces sobre todos los ítems ─────────────────────────

async def juzgar(items, num_samples: int, presupuesto: int | None) -> dict:
    """Corre los dos jueces sobre todos los ítems y mide lo que costó."""
    antes = (costo.USO["llamadas"], costo.USO["entrada"], costo.USO["salida"])
    t0 = time.perf_counter()
    metricas = metricas_juez(num_samples, presupuesto)
    sem = asyncio.Semaphore(4)
    resultados = await asyncio.gather(*(evaluar_item(i, metricas, sem) for i in items))
    gasto = costo.Tokens(costo.USO["entrada"] - antes[1], costo.USO["salida"] - antes[2])
    ver = veredictos(resultados)
    return {"resultados": resultados, "ver": ver, "acuerdo": acuerdo_por_criterio(ver),
            "llamadas": costo.USO["llamadas"] - antes[0], "tokens": gasto,
            "segundos": time.perf_counter() - t0}


# ── Reporte ─────────────────────────────────────────────────────────────────
# Todo lo que sigue solo IMPRIME: no llama al modelo. Recibe el diccionario que devuelve
# `juzgar` y lo cuenta en el orden en que se lee: qué se mide, qué respuestas se juzgan, qué
# dijo cada juez, cuánto coincide con la persona, dónde discrepa, qué se aprende y qué costó.

ANCHO = 100          # columnas del texto corrido

# Las tres preguntas que se le hacen a los jueces. `pos` es la respuesta que cuenta como
# «hay un problema» (la clase positiva de la matriz de confusión) y `neg` la contraria.
PREGUNTAS = {
    CRITERIOS[0]: {"letra": "A", "pregunta": "¿inventa algo?", "corta": "¿inventa algo?", "juez": "hallucinations_v1",
                   "pos": "inventa", "neg": "no inventa"},
    CRITERIOS[1]: {"letra": "B", "pregunta": "¿inventa algo?", "corta": "¿inventa algo?", "juez": "rúbrica sin_inventar",
                   "pos": "inventa", "neg": "no inventa"},
    CRITERIOS[2]: {"letra": "C", "pregunta": "¿cita el número de pedido?", "corta": "¿cita el pedido?",
                   "juez": "rúbrica cita_pedido", "pos": "no cita", "neg": "cita"},
}

# Cómo llama hallucinations_v1 a lo que concluye de cada oración, en español.
ETIQUETA_ORACION = {"supported": "respaldada", "unsupported": "SIN respaldo", "contradictory": "CONTRADICE",
                    "disputed": "discutida", "not_applicable": "no aplica (no afirma un hecho)"}


def _parrafo(texto: str, sangria: str = "", primera: str | None = None) -> str:
    """Texto en un solo párrafo, cortado en palabras al ancho del reporte. `primera` es la
    sangría (o la viñeta) de la primera línea; `sangria`, la de las siguientes."""
    return textwrap.fill(" ".join(str(texto).split()), width=ANCHO,
                         initial_indent=sangria if primera is None else primera, subsequent_indent=sangria)


def _campo(etiqueta: str, texto: str, base: int = 6) -> str:
    """«etiqueta: texto», con las líneas siguientes alineadas bajo el texto."""
    prefijo = " " * base + f"{etiqueta + ':':<18}"
    return _parrafo(texto, " " * len(prefijo), prefijo)


def _lineas(texto: str, sangria: str, maximo: int = 900) -> str:
    """El texto con sus saltos de línea (el juez razona en viñetas), cada línea cortada al ancho
    del reporte y el total limitado a `maximo` caracteres, cortando entre líneas."""
    salida, usados = [], 0
    for linea in str(texto).splitlines():
        if not linea.strip():
            continue
        if usados + len(linea) > maximo and salida:
            salida.append(sangria + "…")
            break
        viñeta = re.match(r"\s*([-*•]|\d+[.)])\s", linea)          # una viñeta sangra su continuación
        salida.append(_parrafo(linea, sangria + ("  " if viñeta else ""), sangria))
        usados += len(linea)
    return "\n".join(salida)


def _llamadas(item) -> str:
    """Las herramientas que el agente llamó en la traza del ítem, como texto."""
    return " → ".join(f"{c['tool']}({', '.join(str(v) for v in c['params'].values())})" for c in TRAZAS[item.traza])


def _persona(item) -> str:
    return ("INVENTA" if item.alucina else "fiel") + ("" if item.cita_pedido else " · no cita el pedido")


def imprimir_intro(items, num_samples: int) -> None:
    fieles = sum(not i.alucina for i in items)
    print("══ Qué mide esta demo ════════════════════════════════════════════════════════════════")
    print(_parrafo("Un juez es otro modelo: lee la respuesta que el agente le dio a un cliente y decide si tiene un "
                   "problema. Pero un juez también puede equivocarse. Acá se lo mide como a cualquier métrica: "
                   "contra lo que dice una persona."))
    print(_parrafo(f"Se le dan {len(items)} respuestas ya escritas. Una persona las etiquetó ANTES de llamar a "
                   f"cualquier juez: {fieles} son fieles (todo lo que afirman está respaldado por lo que hicieron las "
                   f"herramientas y por las reglas del agente) y {len(items) - fieles} inventan algo.", "    ", "  • "))
    print(_parrafo("Se consultan dos jueces de ADK, con tres preguntas. Para cada una se cuenta cuántas veces el "
                   "juez coincide con la persona:", "    ", "  • "))
    for p in PREGUNTAS.values():
        print(f"        {p['letra']}   {p['pregunta']:<28} juez {p['juez']}")
    print("      (hallucinations_v1 parte la respuesta en oraciones y revisa cada una contra lo que devolvieron las")
    print(f"       herramientas; el juez de rúbricas contesta sí o no a cada rúbrica {num_samples} veces, y vale la mayoría.)")


def imprimir_respuestas(items) -> None:
    print("\n══ 1 · Las respuestas que se juzgan, y qué dice la persona de cada una ═════════════════")
    for n, it in enumerate(items, 1):
        print(f"\n {n:>2}. {it.id}   →   la persona dice: {_persona(it)}")
        print(_campo("el agente llamó", _llamadas(it)))
        print(_campo("respondió", f"«{it.respuesta}»"))
        print(_campo("por qué", it.por_que))


def _veredictos_item(r: dict) -> list[dict]:
    """Para un ítem y cada pregunta: lo que dijo el juez, lo que dijo la persona y el score.
    `juez` es True si el juez marcó un problema (score menor que 1.0) y None si no dio score."""
    it = r["item"]
    rub = r["rubricas"].get("por_rubrica", {})
    scores = [r["hallucinations"].get("score"), (rub.get("sin_inventar") or (None,))[0],
              (rub.get("cita_pedido") or (None,))[0]]
    personas = [it.alucina, it.alucina, not it.cita_pedido]
    return [{"juez": None if s is None else s < 1.0, "persona": p, "score": s} for s, p in zip(scores, personas)]


def imprimir_items(corrida: dict) -> None:
    print("\n══ 2 · Qué dijo cada juez ═══════════════════════════════════════════════════════════════")
    print("  ✓ = el juez coincide con la persona · ✗ = discrepa · entre paréntesis, el score del juez")
    print("  (1.00 = sin problema; el juez marca un problema cuando el score es menor que 1.00)\n")
    print(f"{'#':>3}  {'ítem':<27}{'la persona dice':<27}" + "".join(f"{p['letra'] + ' ' + p['corta']:<23}" for p in PREGUNTAS.values()).rstrip())
    for n, r in enumerate(corrida["resultados"], 1):
        celdas = []
        for p, v in zip(PREGUNTAS.values(), _veredictos_item(r)):
            if v["juez"] is None:
                celdas.append(f"{'sin score':<23}")
                continue
            palabra = p["pos"].upper() if v["juez"] else p["neg"]
            marca = "✓" if v["juez"] == v["persona"] else "✗"
            celdas.append(f"{palabra + ' ' + marca + ' (' + format(v['score'], '.2f') + ')':<23}")
        print(f"{n:>3}  {r['item'].id:<27}{_persona(r['item']):<27}" + "".join(celdas).rstrip())


def imprimir_acuerdo(corrida: dict, n: int) -> None:
    print("\n══ 3 · ¿Cuánto coincide cada juez con la persona? ═══════════════════════════════════════")
    print("  Cada cuadro cruza lo que dijo el juez (filas) con lo que dijo la persona (columnas).")
    for nombre, d in corrida["acuerdo"].items():
        p = PREGUNTAS[nombre]
        print(f"\n  {p['letra']} · {p['pregunta']}   (juez {p['juez']})")
        if d is None:
            print("      sin score en ningún ítem")
            continue
        print(f"      {'':<30}{'la persona dice:':>26}")
        print(f"      {'':<30}{p['pos']:>12}{p['neg']:>14}")
        print(f"      {'el juez dice: ' + p['pos']:<30}{d['vp']:>12}{d['fp']:>14}      "
              f"← marcó un problema que no estaba: {d['fp']}")
        print(f"      {'el juez dice: ' + p['neg']:<30}{d['fn']:>12}{d['vn']:>14}      "
              f"← dejó pasar un problema: {d['fn']}")
        total = d["vp"] + d["fp"] + d["fn"] + d["vn"]
        k = d["kappa"]
        print(f"      Coinciden en {d['vp'] + d['vn']} de {total} (acuerdo {d['acuerdo']:.2f}). "
              + ("κ de Cohen no se puede calcular: todas las etiquetas, o todos los veredictos, son iguales."
                 if k != k else f"κ de Cohen = {k:.2f}  (descuenta los aciertos que daría el azar: 0 = como el azar, 1 = perfecto)."))
        if d["sin_score"]:
            print(f"      ({d['sin_score']} ítem(s) sin score del juez: no entran en la cuenta)")


def imprimir_discrepancias(corrida: dict) -> None:
    print("\n══ 4 · Dónde el juez se equivocó, y qué razonó ══════════════════════════════════════════")
    hubo = False
    for r in corrida["resultados"]:
        it = r["item"]
        malas = [(p, v) for p, v in zip(PREGUNTAS.values(), _veredictos_item(r)) if v["juez"] != v["persona"]]
        if not malas:
            continue
        hubo = True
        print(f"\n• {it.id}")
        print(_campo("la respuesta", f"«{it.respuesta}»", base=4))
        print(_campo("la persona dice", f"{_persona(it)}. {it.por_que}", base=4))
        rub = r["rubricas"].get("por_rubrica", {})
        for p, v in malas:
            if v["juez"] is None:
                avisos = r["hallucinations"].get("avisos") if p["letra"] == "A" else None
                print(f"    {p['letra']} (juez {p['juez']}): no devolvió un resultado utilizable"
                      + (f" — ADK dijo: {_lineas(' '.join(avisos), '').strip()}" if avisos else "."))
                continue
            que = "marcó un problema que no estaba" if v["juez"] else "dejó pasar un problema"
            print(f"    {p['letra']} (juez {p['juez']}) {que} — dijo «{p['pos'] if v['juez'] else p['neg']}», score {v['score']:.2f}:")
            if p["letra"] == "A":
                oraciones = r["hallucinations"].get("oraciones", [])
                if not oraciones:
                    print("        (ADK no devolvió el detalle por oración de este ítem)")
                for etiqueta, oracion, razon in oraciones:
                    print(_parrafo(f"«{oracion}» → {ETIQUETA_ORACION.get(etiqueta, etiqueta)}", "          ", "        · "))
                    if razon:
                        print(_parrafo(f"el juez: {razon}", "          "))
            else:
                rid = "sin_inventar" if p["letra"] == "B" else "cita_pedido"
                razon = (rub.get(rid) or (None, ""))[1]
                print(_lineas(razon, "        ") if razon else "        (el juez no dejó razonamiento)")
    if not hubo:
        print("  Ninguna: el juez coincidió con la persona en todas las preguntas.")


def imprimir_lectura(corrida: dict, n: int) -> None:
    print("\n══ 5 · Lectura ══════════════════════════════════════════════════════════════════════════")
    pasaron: dict[str, set] = {}
    for nombre, d in corrida["acuerdo"].items():
        if d is None:
            continue
        p = PREGUNTAS[nombre]
        filas = corrida["ver"][nombre]
        pasaron[p["letra"]] = {it.id for it, j, h in filas if j is False and h is True}
        de_mas = [it.id for it, j, h in filas if j is True and h is False]
        print(_parrafo(f"{p['letra']} ({p['juez']}): coincide en {d['vp'] + d['vn']} de {d['vp'] + d['fp'] + d['fn'] + d['vn']}. "
                       f"Dejó pasar: {', '.join(sorted(pasaron[p['letra']])) or 'nada'}. "
                       f"Marcó de más: {', '.join(de_mas) or 'nada'}.", "    ", "  • "))
    comunes = sorted(pasaron.get("A", set()) & pasaron.get("B", set()))
    if comunes:
        print(_parrafo(f"A y B dejaron pasar lo mismo ({', '.join(comunes)}). Pero los dos usan el mismo modelo "
                       f"({MODELO_JUEZ}): que coincidan entre sí no es una segunda opinión independiente.", "    ", "  • "))
    print(_parrafo(f"Con {n} respuestas esto ilustra el método; no calibra al juez. Una calibración real necesita decenas "
                   "de casos por criterio y más de una persona etiquetando.", "    ", "  • "))


def imprimir_costo(corrida: dict, n_items: int, est, peor: float) -> None:
    t = corrida["tokens"]
    print("\n══ 6 · Cuánto costó juzgar ══════════════════════════════════════════════════════════════")
    print(f"  USD {t.usd:.4f} en total  (≈ ${t.usd / n_items:.4f} por respuesta, con estos dos jueces) · "
          f"{corrida['llamadas']:.0f} llamadas al juez · {corrida['segundos']:.0f} s")
    print(f"  Tokens: entrada {t.entrada:,.0f} · salida (con razonamiento) {t.salida:,.0f}")
    print(f"  La estimación previa daba: esperado ${est['esperado'].usd:.3f}, peor caso ${peor:.3f}.")
    s = juez_tolerante.STATS
    if s["muestras"]:
        print(_parrafo(f"El juez de rúbricas contestó {s['muestras']} veces; {s['rescatadas']} tenían un formato que el "
                       f"analizador de ADK descarta en silencio, y metricas/juez_tolerante.py las rescató "
                       f"({s['descartadas']} descartadas, {s['vacias']} vacías).", "  "))
    if s["descartadas"] or s["vacias"]:
        print("  AVISO: hubo muestras descartadas; los scores se calcularon con menos muestras de las pedidas.")


def imprimir_comparacion(base: dict, sin_razonar: dict) -> None:
    print("\n══ 7 · El mismo juez con y sin razonamiento: ¿cuánto cuesta, cuánto pierde? ═════════════")
    print(f"{'variante':<22}{'llamadas':>9}{'tok salida':>12}{'USD':>9}{'seg':>6}" + "".join(f"{'κ ' + p['letra']:>8}" for p in PREGUNTAS.values()))
    for nombre, c in (("razonamiento default", base), ("razonamiento apagado", sin_razonar)):
        ks = []
        for crit in CRITERIOS:
            d = c["acuerdo"][crit]
            ks.append("n/d" if d is None or d["kappa"] != d["kappa"] else f"{d['kappa']:.2f}")
        print(f"{nombre:<22}{c['llamadas']:>9.0f}{c['tokens'].salida:>12,.0f}{c['tokens'].usd:>9.4f}"
              f"{c['segundos']:>6.0f}" + "".join(f"{k:>8}" for k in ks))
    ahorro = 1 - sin_razonar["tokens"].usd / base["tokens"].usd if base["tokens"].usd else 0
    print(_parrafo(f"→ Apagar el razonamiento ahorró {ahorro:.0%} del costo. Si el κ no se movió, fue gratis; si bajó, el "
                   f"ahorro se pagó con calidad. En ambos casos hay que volver a medir al juez después de tocarlo.", "  "))


# ── Programa principal ──────────────────────────────────────────────────────

async def main(a) -> int:
    items = [i for i in ITEMS if not a.solo or i.id in a.solo]
    if not items:
        print(f"ningún ítem coincide con --solo {a.solo}")
        return 1
    # 1. Estimar el costo ANTES de llamar: hallucinations_v1 hace 2 llamadas por ítem y el
    #    juez de rúbricas, `num_samples`.
    n_llamadas = len(items) * (2 + a.num_samples)
    est = costo.estimar_juez(n_llamadas)
    veces = 2 if a.comparar_razonamiento else 1
    print(f"── Antes de llamar al modelo: {len(items)} respuestas × (hallucinations_v1: 2 llamadas + rúbricas: "
          f"{a.num_samples} llamadas) = {n_llamadas} llamadas al juez ──")
    print(f"  {'escenario':<10}{'tokens de entrada':>19}{'tokens de salida':>18}{'USD':>9}")
    for esc in ("bajo", "esperado", "alto"):
        t = est[esc]
        print(f"  {esc:<10}{t.entrada:>19,.0f}{t.salida:>18,.0f}{t.usd:>9.3f}")
    peor = est["alto"].usd * (1.2 if a.comparar_razonamiento else 1)   # la variante sin razonamiento cuesta menos
    print(f"  Se aborta si el escenario «alto» supera --max-usd (${a.max_usd:.2f}).")
    if a.comparar_razonamiento:
        print(f"  (con --comparar-razonamiento el tope se evalúa sobre ≈ ${peor:.3f})")
    # 2. Detenerse antes de gastar: con --dry-run solo se estima; si el peor escenario
    #    supera el tope, se aborta (salvo --forzar).
    if a.dry_run:
        print("--dry-run: no se llamó al modelo.")
        return 0
    if peor > a.max_usd and not a.forzar:
        print(f"ABORTADO: el peor escenario (${peor:.3f}) supera --max-usd ${a.max_usd:.2f}.")
        return 2

    # 3. Instalar el contador de tokens y el parser tolerante, y correr los jueces.
    verificar_credenciales()
    costo.instalar_contador()
    juez_tolerante.instalar()
    base = await juzgar(items, a.num_samples, None)
    # 4. Imprimir el reporte: qué se mide, las respuestas, qué dijo cada juez, cuánto coincide
    #    con la persona, dónde se equivocó, qué se aprende y qué costó (y, si se pidió, la comparación).
    print()
    imprimir_intro(items, a.num_samples)
    imprimir_respuestas(items)
    imprimir_items(base)
    imprimir_acuerdo(base, len(items))
    imprimir_discrepancias(base)
    imprimir_lectura(base, len(items))
    imprimir_costo(base, len(items), est, est["alto"].usd)
    if a.comparar_razonamiento:
        sin = await juzgar(items, a.num_samples, 0)
        imprimir_comparacion(base, sin)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-samples", type=int, default=3, help="muestras del juez de rúbricas (default de ADK: 5)")
    ap.add_argument("--max-usd", type=float, default=0.75, help="tope de gasto: aborta si el peor escenario lo supera")
    ap.add_argument("--forzar", action="store_true", help="ignora el tope --max-usd")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime la estimación de costo; no llama al modelo")
    ap.add_argument("--solo", nargs="*", help="ids de ítems a evaluar (prueba barata)")
    ap.add_argument("--comparar-razonamiento", action="store_true",
                    help="repite la corrida con el razonamiento del juez apagado")
    sys.exit(asyncio.run(main(ap.parse_args())))
