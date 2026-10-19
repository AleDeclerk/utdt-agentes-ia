"""Agentic RAG con ADK 2 — el agente elige las herramientas, el código fija los topes.

Un Agent (Gemini) decide QUÉ herramienta usar, en qué orden y si necesita alguna, sobre lo que ya tiene
esta carpeta: el retriever híbrido de `hybrid.py` (BM25 + FAISS) sobre las 8 normas y el grafo de 8
tripletas de `graphrag.py`. Tiene tres:
  - buscar_normativa(consulta, k)       recuperación híbrida sobre las normas
  - consultar_grafo(entidad, saltos)    relaciones societarias del cliente (BFS de graphrag.py)
  - sumar_exposiciones(entidad, saltos) suma de exposiciones calculada por el CÓDIGO, no por el modelo

El agente propone; el código fija los topes:
  - los saltos del grafo se acotan a MAX_SALTOS dentro de cada herramienta (no depende del modelo);
  - `k` de la búsqueda se acota a MAX_K;
  - las llamadas al modelo se acotan con RunConfig(max_llm_calls=N).
El modelo NUNCA toca el grafo ni el índice directamente: solo elige la herramienta y sus argumentos.

Tres consultas, una por comportamiento: una sola herramienta, cadena de herramientas, ninguna herramienta.
Cada una se corre varias veces para mostrar cuánto varía el agente. Necesita `GOOGLE_API_KEY`; con la capa
gratuita conviene `--repeticiones 1` (menos llamadas por minuto).

Uso:  python agentic_rag.py [--repeticiones 2]
"""
import argparse
import asyncio
import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from adk_util import AVISOS_429, ejecutar
from graphrag import TRIPLES, build_graph, multi_hop_traversal
from hybrid import retriever

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · CONFIGURACIÓN Y TOPES DE CÓDIGO
#   El modelo (Gemini) y los dos límites que fija el código: MAX_K (fragmentos
#   por búsqueda) y MAX_SALTOS (saltos del grafo).
# ══════════════════════════════════════════════════════════════════════════════
DEMO_MODEL = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
MAX_K = 5
MAX_SALTOS = 5  # tope de código para cualquier recorrido del grafo

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · DATOS Y AYUDAS PARA RECONOCER AL CLIENTE
#   El grafo de la demo anterior, la lista de entidades consultables y cómo
#   encontrar una en un texto ("Textil Norte" vale como "Textil Norte S.A.").
# ══════════════════════════════════════════════════════════════════════════════
GRAFO = build_graph(TRIPLES)
# Entidades consultables: todo nodo salvo las exposiciones (son hojas descriptivas).
ENTIDADES = sorted({s for s, _, _ in TRIPLES} | {o for _, p, o in TRIPLES if p != "tiene_exposicion"})
_SUFIJOS_LEGALES = {"sa", "srl", "bv"}
_MONTO = re.compile(r"USD\s*([\d.]+)M")


def _clave(texto: str) -> str:
    """Normaliza para comparar nombres: minúsculas, sin signos, sin sufijos legales.
    Evita que 'Textil Norte' y 'Textil Norte S.A.' se traten como entidades distintas."""
    t = re.sub(r"[.,¿?¡!]", "", texto.lower())
    return " ".join(w for w in t.split() if w not in _SUFIJOS_LEGALES)


def _encontrar_entidad(texto: str) -> str | None:
    """Busca en el texto el nombre (normalizado) de una entidad del grafo; gana el más largo."""
    ct = _clave(texto)
    candidatas = [e for e in ENTIDADES if _clave(e) in ct]
    return max(candidatas, key=lambda e: len(_clave(e))) if candidatas else None


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · LAS TRES HERRAMIENTAS DEL AGENTE
#   Funciones Python comunes: ADK deriva el esquema de la firma y del
#   docstring. Cada una recorta en código lo que pide el modelo.
# ══════════════════════════════════════════════════════════════════════════════
# ── 3a · buscar_normativa: busca en las normas con el buscador híbrido (k acotado por MAX_K) ──
def buscar_normativa(consulta: str, k: int = 3) -> dict:
    """Busca en la normativa interna del banco (límites de crédito, plazos, legajos, seguros).
    Devuelve los fragmentos más relevantes con su id para poder citarlos."""
    k = max(1, min(int(k), MAX_K))
    r = retriever.retrieve(consulta, method="hybrid", top_k=k)
    return {"fragmentos": [{"id": d["id"], "fuente": d["source"], "texto": d["text"]} for d in r.chunks]}


# ── 3b · consultar_grafo: devuelve las relaciones de un cliente (saltos acotados por MAX_SALTOS) ──
def consultar_grafo(entidad: str, saltos: int = 2) -> dict:
    """Devuelve las relaciones societarias y de exposición de un cliente: quién lo controla, quién es el
    beneficiario final, qué otras sociedades están vinculadas y qué exposiciones tienen. Para la exposición
    vinculada de un cliente usar saltos=5."""
    e = _encontrar_entidad(entidad)
    if not e:
        return {"error": "entidad no encontrada", "entidades_disponibles": ENTIDADES}
    saltos = max(1, min(int(saltos), MAX_SALTOS))
    return {"entidad": e, "saltos": saltos, "relaciones": multi_hop_traversal(e, GRAFO, max_hops=saltos)}


# ── 3c · sumar_exposiciones: suma los montos EN CÓDIGO, no con el modelo ──
def sumar_exposiciones(entidad: str, saltos: int = 5) -> dict:
    """Suma, en millones de USD, las exposiciones alcanzables desde un cliente dentro de los saltos indicados.
    La suma la calcula el código: usar siempre esta herramienta en lugar de sumar a mano."""
    e = _encontrar_entidad(entidad)
    if not e:
        return {"error": "entidad no encontrada", "entidades_disponibles": ENTIDADES}
    saltos = max(1, min(int(saltos), MAX_SALTOS))
    marca = " --tiene_exposicion--> "
    detalle = [a.split(marca)[1] for a in multi_hop_traversal(e, GRAFO, max_hops=saltos) if marca in a]
    total = sum(float(_MONTO.search(d).group(1)) for d in detalle)
    return {"entidad": e, "saltos": saltos, "detalle": detalle, "total_usd_m": round(total, 1)}


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · EL AGENTE
#   Gemini con las tres herramientas y una instrucción que le dice cuándo usar
#   cada una, y que nunca sume montos él.
# ══════════════════════════════════════════════════════════════════════════════
def construir_agente() -> Agent:
    return Agent(
        name="analista", model=DEMO_MODEL,
        tools=[buscar_normativa, consultar_grafo, sumar_exposiciones],
        instruction=(
            "Sos un analista de riesgo crediticio de un banco. Tenés tres herramientas: buscar_normativa (normas "
            "internas), consultar_grafo (relaciones societarias y exposiciones de un cliente) y sumar_exposiciones "
            "(suma exacta calculada por código). Usá SOLO las herramientas que la pregunta necesite; si no hace falta "
            "buscar nada, respondé directamente sin herramientas. Nunca sumes montos vos: usá sumar_exposiciones. "
            "Citá los ids de las normas entre corchetes. Si las herramientas no traen evidencia suficiente, decilo. "
            "Respondé en pocas líneas."),
    )


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 5 · AYUDAS PARA IMPRIMIR LO QUE HIZO EL AGENTE
#   Resumen de cada llamada a herramienta y de cada corrida: turnos del modelo
#   y herramientas usadas.
# ══════════════════════════════════════════════════════════════════════════════
def _resumen(c: dict) -> str:
    r = c.get("resp") or {}
    if c["tool"] == "buscar_normativa":
        return "ids=" + str([f["id"] for f in r.get("fragmentos", [])])
    if c["tool"] == "consultar_grafo":
        return f"{len(r.get('relaciones', []))} relaciones" if "relaciones" in r else str(r)[:80]
    if c["tool"] == "sumar_exposiciones":
        return f"total USD {r.get('total_usd_m')} M" if "total_usd_m" in r else str(r)[:80]
    return str(r)[:80]


def mostrar(r: dict, etiqueta: str) -> None:
    secuencia = [c["tool"] for c in r["llamadas"]]
    print(f"  {etiqueta}: turnos del modelo={r['turnos_modelo']}, herramientas={secuencia or 'ninguna'}")
    for c in r["llamadas"]:
        print(f"      {c['tool']}({c['args']}) -> {_resumen(c)}")
    if r["cortado"]:
        print(f"      CORTADO POR EL TOPE DE CÓDIGO: {r['error']}")


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 6 · LA DEMO
#   Prueba los topes sin modelo, corre tres preguntas dos veces cada una y
#   termina con un corte forzado del modelo.
# ══════════════════════════════════════════════════════════════════════════════
async def main(repeticiones: int) -> None:
    # ── 6a · Los topes funcionan sin modelo: el código recorta lo que el agente pida ──
    print("=" * 76)
    print("Prueba de topes EN LAS HERRAMIENTAS (sin modelo): el código acota lo que el agente pida")
    print("=" * 76)
    r = consultar_grafo("Textil Norte S.A.", 99)
    print(f"  consultar_grafo('Textil Norte S.A.', saltos=99) -> saltos efectivos={r['saltos']} "
          f"(MAX_SALTOS={MAX_SALTOS}), {len(r['relaciones'])} relaciones")
    print(f"  buscar_normativa('plazo', k=50) -> {len(buscar_normativa('plazo', 50)['fragmentos'])} fragmentos (MAX_K={MAX_K})")
    for s in (3, 5):
        print(f"  sumar_exposiciones('Textil Norte S.A.', saltos={s}) -> USD {sumar_exposiciones('Textil Norte S.A.', s)['total_usd_m']} M")
    print(f"  Tope de llamadas al modelo por defecto de ADK (RunConfig): {RunConfig().max_llm_calls}")

    # ── 6b · Tres preguntas, tres comportamientos: una herramienta, una cadena y ninguna ──
    # (etiqueta, pregunta, herramientas que el código ESPERA que se usen)
    consultas = [
        ("UNA herramienta", "¿Cuál es el plazo máximo de la línea de capital de trabajo para Pymes?",
         {"buscar_normativa"}),
        ("CADENA de herramientas", "¿Podemos ampliar la línea de Textil Norte S.A.? Considerá su grupo económico y "
                                   "el límite normativo para clientes vinculados.",
         {"buscar_normativa", "consultar_grafo", "sumar_exposiciones"}),
        ("NINGUNA herramienta", "Hola, ¿qué podés hacer por mí?", set()),
    ]
    for etiqueta, pregunta, esperadas in consultas:
        print("\n" + "=" * 76)
        print(f"{etiqueta} — {pregunta}")
        print("=" * 76)
        secuencias = []
        for i in range(1, repeticiones + 1):
            r = await ejecutar(pregunta, agente=construir_agente(), app="agentic")
            mostrar(r, f"corrida {i}")
            usadas = {c["tool"] for c in r["llamadas"]}
            secuencias.append([c["tool"] for c in r["llamadas"]])
            faltan = sorted(esperadas - usadas)
            if faltan:
                print(f"      VERIFICACIÓN DEL CÓDIGO: faltaron herramientas esperadas {faltan}; "
                      "la respuesta no se apoya en esa evidencia")
            print(f"  RESPUESTA (corrida {i}): {r['texto']}")
        iguales = all(s == secuencias[0] for s in secuencias)
        print(f"  Variación entre corridas: {'misma secuencia de herramientas' if iguales else 'SECUENCIAS DISTINTAS'} "
              f"{secuencias}")

    # ── 6c · Corte forzado: max_llm_calls=1 corta al modelo antes de que redacte ──
    print("\n" + "=" * 76)
    print("TOPE FORZADO: la cadena de herramientas con RunConfig(max_llm_calls=1)")
    print("=" * 76)
    print("(ADK registra este corte como un error en su propio log; acá se silencia ese log y se captura la excepción)")
    logging.disable(logging.CRITICAL)
    try:
        r = await ejecutar(consultas[1][1], agente=construir_agente(), app="agentic_tope",
                           run_config=RunConfig(max_llm_calls=1))
    finally:
        logging.disable(logging.NOTSET)
    mostrar(r, "con tope=1")
    print(f"  ¿Cortó el código? {'SÍ: el modelo alcanzó a pedir herramientas pero no a redactar la respuesta' if r['cortado'] else 'NO'}")
    print(f"  Respuesta entregada: {r['texto']}")

    print("\n429/red durante la corrida:", AVISOS_429 or "ninguno")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=2)
    args = ap.parse_args()
    asyncio.run(main(args.repeticiones))
