"""MÓDULO 2 — el agente reclutador (ADK 2) sobre el grafo de talento, en modo script.

Corre 7 preguntas y, para cada corrida, imprime qué herramientas llamó el agente y verifica DOS cosas con código,
sin confiar en lo que el modelo dice de sí mismo:
  1. que haya usado las herramientas que la pregunta pide;
  2. que toda persona nombrada en la respuesta aparezca en lo que devolvieron las herramientas (auditoría).
Cada pregunta se puede repetir (--repeticiones) para mostrar cuánto varía el agente. Al final fuerza el tope de llamadas al modelo.

Requiere el Neo4j de la demo con el grafo cargado (./run.sh up y ./run.sh 01). Normalmente se corre con ./run.sh 02.
Uso:  python 02_agente.py [--repeticiones 1]
Con la capa gratuita de AI Studio, 3 repeticiones (21 corridas) pueden chocar con el límite de pedidos por minuto: el script
espera y reintenta, pero tarda más.
"""
import argparse
import asyncio
import json
import logging

import comun
import herramientas
from adk_util import ejecutar
from agente import MAX_LLAMADAS_MODELO, construir_agente

# (etiqueta, pregunta, herramientas que el código ESPERA que se usen)
PREGUNTAS = [
    ("Skills de una persona", "¿Qué skills tiene Lucy Turner?", {"habilidades_de_persona"}),
    ("Skills similares", "¿Qué skills son parecidas a PowerBI y a Data Visualization?", {"habilidades_similares"}),
    ("Personas similares", "¿Qué personas tienen skills parecidas a las de Daniel Hill?", {"personas_similares"}),
    ("Personas con skills", "¿Quién tiene experiencia en Python y AWS?", {"personas_con_habilidades"}),
    ("Pregunta compuesta", "Daniel Hill se va del proyecto: ¿quién podría reemplazarlo y qué skills tiene "
                           "esa persona que él no tiene?", {"personas_similares"}),
    ("Cadena de herramientas", "Quiero armar un equipo con Lucy Turner: ¿qué skills tiene y quién más en la "
                               "empresa sabe Security?", {"habilidades_de_persona", "personas_con_habilidades"}),
    ("Ninguna herramienta", "Hola, ¿qué podés hacer por mí?", set()),
]


def nombres_del_grafo() -> list[str]:
    return [r["n"] for r in comun.leer("MATCH (p:Person) RETURN p.name AS n")]


def auditar(r: dict, nombres: list[str]) -> list[str]:
    """Personas nombradas en la respuesta que NINGUNA herramienta devolvió."""
    evidencia = json.dumps([c.get("resp") for c in r["llamadas"]], ensure_ascii=False)
    texto = r["texto"] or ""
    return [n for n in nombres if n in texto and n not in evidencia]


def resumen(c: dict) -> str:
    x = c.get("resp") or {}
    if "error" in x:
        return f"ERROR: {x['error']}"
    if c["tool"] == "habilidades_de_persona":
        return f"{x.get('persona')}: {x.get('skills')}"
    if c["tool"] == "habilidades_similares":
        return "; ".join(f"{i['consulta']} -> {[s['skill'] for s in i['coincidencias']]} + {i['relacionadas']}"
                         for i in x.get("resultados", []))
    if c["tool"] == "personas_similares":
        return f"{[(s['persona'], s['puntaje'], s['skills_exactas_en_comun']) for s in x.get('similares', [])]}"
    if c["tool"] == "personas_con_habilidades":
        return f"{[(p['persona'], p['cubre_directo'], p['cubre_con_parecidas']) for p in x.get('personas', [])[:5]]}"
    return str(x)[:100]


def mostrar(r: dict, etiqueta: str) -> None:
    print(f"  {etiqueta}: turnos del modelo={r['turnos_modelo']}, "
          f"herramientas={[c['tool'] for c in r['llamadas']] or 'ninguna'}")
    for c in r["llamadas"]:
        print(f"      {c['tool']}({c['args']}) -> {resumen(c)[:230]}")


async def main(repeticiones: int) -> None:
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)  # aviso informativo de AFC en cada llamada
    comun.esperar_neo4j()
    comun.cliente_gemini()  # corta enseguida, con un mensaje claro, si falta la API key
    nombres = nombres_del_grafo()
    if len(nombres) < 100:
        raise SystemExit("El grafo está vacío. Corré primero:  ./run.sh 01")

    print("=" * 78)
    print("Topes EN LAS HERRAMIENTAS (sin modelo): el código acota lo que el agente pida")
    print("=" * 78)
    r = herramientas.personas_con_habilidades(["Python", "AWS", "Docker", "SQL", "Java", "Go", "Rust"])
    print(f"  7 skills pedidas -> se consideran {len(r['pedidas'])} (MAX_SKILLS={herramientas.MAX_SKILLS}), "
          f"{len(r['personas'])} personas (MAX_RESULTADOS={herramientas.MAX_RESULTADOS})")
    print(f"  persona inexistente -> {herramientas.habilidades_de_persona('Pedro Inexistente')}")
    print(f"  tope de llamadas al modelo del agente: {MAX_LLAMADAS_MODELO} (before_model_callback)")

    aciertos = total = fuera_de_evidencia = 0
    for etiqueta, pregunta, esperadas in PREGUNTAS:
        print("\n" + "=" * 78)
        print(f"{etiqueta} — {pregunta}")
        print("=" * 78)
        secuencias = []
        for i in range(1, repeticiones + 1):
            r = await ejecutar(pregunta, agente=construir_agente(), app="talento")
            mostrar(r, f"corrida {i}")
            usadas = {c["tool"] for c in r["llamadas"]}
            secuencias.append([c["tool"] for c in r["llamadas"]])
            faltan = sorted(esperadas - usadas)
            sobran_si_ninguna = sorted(usadas) if not esperadas else []
            total += 1
            aciertos += not faltan and not sobran_si_ninguna
            if faltan:
                print(f"      VERIFICACIÓN DEL CÓDIGO: faltaron herramientas esperadas {faltan}")
            if sobran_si_ninguna:
                print(f"      VERIFICACIÓN DEL CÓDIGO: no hacía falta ninguna y usó {sobran_si_ninguna}")
            sin_respaldo = auditar(r, nombres)
            fuera_de_evidencia += bool(sin_respaldo)
            if sin_respaldo:
                print(f"      AUDITORÍA: personas nombradas SIN respaldo en las herramientas: {sin_respaldo}")
            print(f"  RESPUESTA (corrida {i}): {r['texto']}")
        iguales = all(s == secuencias[0] for s in secuencias)
        print(f"  Variación entre corridas: {'misma secuencia de herramientas' if iguales else 'SECUENCIAS DISTINTAS'} "
              f"{secuencias}")

    print("\n" + "=" * 78)
    print(f"RESUMEN: {aciertos}/{total} corridas usaron las herramientas esperadas; "
          f"{fuera_de_evidencia}/{total} nombraron personas sin respaldo.")

    print("\n" + "=" * 78)
    print("TOPE FORZADO: la cadena de herramientas con un tope de 1 llamada al modelo")
    print("=" * 78)
    r = await ejecutar(PREGUNTAS[5][1], agente=construir_agente(max_llamadas=1), app="talento_tope")
    mostrar(r, "con tope=1")
    print(f"  Respuesta entregada: {r['texto']}")
    print("\n429 durante la corrida:", comun.AVISOS_429 or "ninguno")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=1)
    args = ap.parse_args()
    asyncio.run(main(args.repeticiones))
