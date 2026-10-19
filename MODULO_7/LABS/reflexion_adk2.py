"""
Reflexion con memoria persistente en ADK2. Fallo → reflexión → memoria →
reintento, y lo aprendido SOBREVIVE a la tarea y se recupera por parecido.

Es la versión del paper de Reflexion: el agente escribe una reflexión tras cada intento
fallido; las reflexiones se guardan en una memoria de largo plazo (acá, un archivo JSON)
y se anteponen al prompt cuando el agente reintenta la misma tarea u otra parecida.

Dos partes (la parte 1 siempre parte de una memoria VACÍA y sobrescribe el archivo):

  1. APRENDER  (TRAIN, en orden fijo, UNA tarea a la vez). Cada tarea recupera las
               lecciones parecidas de las anteriores, falla o acierta, reflexiona si
               falla y, al terminar, deja sus reflexiones en `memoria_reflexiones.json`.
               Se corre en secuencia a propósito: así se VE que la segunda tarea de una
               categoría ya llega con la lección de la primera.
  2. PROBAR    (TEST, tareas NUEVAS). Se compara "sin memoria" contra "Reflexion con la
               memoria aprendida" sobre una instantánea de solo lectura de la memoria,
               de modo que las condiciones no se contaminen entre sí.

Lo que Reflexion NO hace (y ExpeL sí): generalizar. Cada lección queda atada a un caso
("en esta comisión de $90.300 debí redondear a 994"); no se destila en una regla ni se
vota. Mirá `memoria_reflexiones.json` después de correrlo y compará con las reglas que
destila ExpeL (`reglas_expel_caso.json`, ver `expel_caso_adk2.py`).

Qué esperar (~5 min, unas 75 llamadas al modelo):
  - TRAIN: sin memoria casi nunca acierta; con Reflexion resuelve las 9 tareas, y las
    tareas posteriores de una categoría suelen acertar al primer intento por las lecciones.
  - TEST : Reflexion mejora el primer intento respecto de sin memoria, sin reglas.
Los números varían entre corridas (n chico): sirven para ilustrar el mecanismo.

Salidas: memoria_reflexiones.json (la memoria) y reflexion_resultados.json (resúmenes y
trayectorias; ExpeL reutiliza las trayectorias como su "experiencia").
Con --solo-aprender (solo la parte 1) dura ~3-4 min.

Uso:  python reflexion_adk2.py                   # aprender + probar
      python reflexion_adk2.py --solo-aprender   # solo la parte 1 (el aprendizaje)
      python reflexion_adk2.py --solo-probar     # parte 2 con memoria_reflexiones.json existente
"""
import asyncio
import json
import sys

from comun import (ARCHIVO_MEMORIA, MemoriaReflexiones, baseline_vs_tecnica, con_reintentos,
                   correr_en_paralelo, crear_recuperador_lecciones, crear_workflow, narrar,
                   registrar_costo, resolver_tarea, resumen)
from tareas import TEST, TRAIN

REPETICIONES_BASE = 2    # TRAIN sin memoria (referencia)
REPETICIONES_TEST = 3
ARCHIVO_RESULTADOS = "reflexion_resultados.json"


async def aprender(memoria: MemoriaReflexiones) -> list[dict]:
    """Pasada de aprendizaje: corre TRAIN en orden fijo, una tarea por vez, y deja las
    reflexiones de cada una en `memoria` (que se persiste al final).

    Las tareas se corren en secuencia porque la memoria evoluciona entre una y otra: el
    orden de TRAIN (por categoría) hace visible el efecto. Devuelve los resultados por tarea."""
    wf = crear_workflow(max_intentos=3, recuperar=crear_recuperador_lecciones(memoria))
    resultados = []
    for t in TRAIN:
        r = await con_reintentos(lambda t=t: resolver_tarea(wf, t))
        guardadas = memoria.retener(t, r)          # Retain: recién cuando la tarea terminó
        marca = "✓" if r["primer_intento"] else "✗"
        recup = ", ".join(r["lecciones"]) if r["lecciones"] else "—"
        print(f"  {t['id']:<6} 1er intento {marca} | {r['intentos']} intento(s) | "
              f"lecciones recuperadas: {recup} | lecciones guardadas: {guardadas}")
        resultados.append(r)
    memoria.guardar()
    print(f"  → memoria persistente: {len(memoria)} lecciones en {memoria.archivo or ARCHIVO_MEMORIA}")
    return resultados


def explicar_aprendizaje(resultados: list[dict], memoria: MemoriaReflexiones) -> None:
    """«Qué pasó» de la parte 1, armado a partir de los resultados por tarea."""
    cat = {t["id"]: t["categoria"] for t in TRAIN}
    fallaron = [r for r in resultados if not r["primer_intento"]]
    con_leccion = [r for r in resultados
                   if any(cat[i] == r["categoria"] for i in r["lecciones"])]
    ok_con = sum(r["primer_intento"] for r in con_leccion)
    narrar(f"{len(fallaron)} de {len(resultados)} tareas fallaron al primer intento; en cada una el agente "
           f"escribió una reflexión sobre qué convención le faltó, reintentó y la guardó en la memoria "
           f"(solo los fallos generan lecciones: {len(memoria)} en total). Después, {len(con_leccion)} tareas "
           f"llegaron con una lección de su misma categoría y {ok_con} de ellas acertaron al primer intento"
           + (": la lección se recuperó por parecido y se usó." if ok_con else
              ": en esta corrida la lección no alcanzó para acertar al primer intento."))


async def probar(memoria: MemoriaReflexiones) -> list[dict]:
    """Parte 2: transferencia a tareas NUEVAS, sin memoria vs. Reflexion con la memoria
    aprendida (instantánea de solo lectura; las reflexiones que se generen durante TEST
    quedan en el buffer de cada tarea y no se guardan)."""
    snapshot = memoria.copia_solo_lectura()
    sin = crear_workflow(max_intentos=1)
    con = crear_workflow(max_intentos=3, recuperar=crear_recuperador_lecciones(snapshot))
    res_sin, res_con = await asyncio.gather(
        correr_en_paralelo([lambda t=t: resolver_tarea(sin, t) for t in TEST for _ in range(REPETICIONES_TEST)]),
        correr_en_paralelo([lambda t=t: resolver_tarea(con, t) for t in TEST for _ in range(REPETICIONES_TEST)]),
    )
    print("\nRESULTADOS sobre tareas NUEVAS (TEST)")
    out = [resumen("sin memoria (1 intento)", res_sin),
           resumen("Reflexion + memoria persistente", res_con)]
    ej = next((r for r in res_con if r["lecciones"]), None)
    if ej:
        t = next(t for t in TEST if t["id"] == ej["id"])
        print(f"\nEjemplo — tarea {ej['id']}: recuperó las lecciones de {ej['lecciones']}")
        for e in snapshot.buscar(t["prompt"]):
            print(f"  lección ({e['id_tarea']}): {e['reflexion'][:200].replace(chr(10), ' ')}...")
        print(f"  resultado: {ej['intentos']} intento(s), "
              f"{'acertó al primer intento' if ej['primer_intento'] else 'acertó tras reflexionar' if ej['resuelta'] else 'no resuelta'}")
    baseline_vs_tecnica("Reflexion", res_sin, res_con)
    a = sum(r["primer_intento"] for r in res_sin)
    b = sum(r["primer_intento"] for r in res_con)
    ids_entrenamiento = {e["id_tarea"] for e in snapshot.entradas}
    narrar(f"Estas tareas son NUEVAS: ninguna aparece en la memoria ({len(snapshot)} lección(es), de "
           f"{', '.join(sorted(ids_entrenamiento))}). Sin memoria el agente acertó {a} de {len(res_sin)} al "
           f"primer intento; con la memoria persistente, {b} de {len(res_con)}. "
           + ("Recuperar lecciones de casos parecidos le dio la convención que le faltaba. " if b > a else
              "En esta corrida la memoria no mejoró el primer intento. ")
           + "Cada lección sigue atada a un caso: no se destiló en una regla general (eso lo agrega ExpeL).")
    return out


async def main():
    print("REFLEXION con memoria persistente — aprender de los propios fallos")
    print("Cuando el agente falla, escribe una reflexión; se guarda en un archivo y se recupera por parecido.")
    print("(Tareas sintéticas: las convenciones están inventadas para el curso.)\n")
    solo_probar = "--solo-probar" in sys.argv
    solo_aprender = "--solo-aprender" in sys.argv
    salida: dict = {}
    if solo_probar:
        memoria = MemoriaReflexiones(ARCHIVO_MEMORIA)
        print(f"Memoria cargada: {len(memoria)} lecciones de {ARCHIVO_MEMORIA}")
        if not len(memoria):
            sys.exit("No hay memoria: corré primero sin --solo-probar.")
    else:
        print(f"PARTE 1 — APRENDER: {len(TRAIN)} tareas de entrenamiento, una por vez, con memoria persistente")
        sin = crear_workflow(max_intentos=1)
        base = await correr_en_paralelo([lambda t=t: resolver_tarea(sin, t) for t in TRAIN
                                         for _ in range(REPETICIONES_BASE)])
        print("Referencia sin memoria:")
        salida["entrenamiento_sin_memoria"] = resumen("sin memoria (1 intento)", base)
        print("Con Reflexion + memoria persistente (una tarea por vez):")
        memoria = MemoriaReflexiones(ARCHIVO_MEMORIA, cargar=False)   # siempre desde cero
        entrenamiento = await aprender(memoria)
        salida["entrenamiento"] = entrenamiento
        salida["entrenamiento_resumen"] = resumen("Reflexion (hasta 3 int.)", entrenamiento)
        explicar_aprendizaje(entrenamiento, memoria)
    if not solo_aprender:
        salida["transferencia"] = await probar(memoria)
    if not solo_probar:
        with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as f:
            json.dump(salida, f, indent=2, ensure_ascii=False)
    registrar_costo("reflexion_adk2")


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__)
        sys.exit(0)
    asyncio.run(main())
