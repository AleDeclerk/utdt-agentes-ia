"""
Few-shot dinámico en ADK2. Recuperar por similitud los ejemplos más
parecidos a la consulta — el mismo mecanismo que el RAG del Módulo 6 — en lugar de
pegar siempre los mismos. Marco: case-based reasoning (Retrieve → Reuse → Revise → Retain).

El banco de casos es un archivo (`banco_casos.json`) que SE VA LLENANDO:

  1. APRENDER (TRAIN, en orden, UNA tarea por vez). Cada tarea recupera los casos parecidos
     del banco que ya hay (Retrieve → Reuse), el verificador revela la respuesta correcta
     (Revise) y el caso (problema + respuesta CORRECTA, no la del agente) se guarda en el
     banco (Retain). Un fallo también aporta un caso válido. Parte siempre de un banco vacío.
  2. PROBAR (TEST, tareas NUEVAS, un solo intento). Con una copia de solo lectura del banco
     (lo que se guarde durante la prueba no entra al banco, así que no hay fuga):
       zero-shot          sin ejemplos (el baseline)
       fijo (primeros 3)  los 3 primeros del banco, siempre los mismos
       dinámico k=3       los 3 más parecidos al problema

Tareas: las de `tareas_caso.py` (cargo fijo al exterior y descuento Premium). Cada ejemplo
resuelto deja ver la convención, así que el ejemplo basta para deducirla. Los 3 primeros del
banco son los tres de exterior: sirven para exterior y no para Premium, y eso es lo que
recuperar por parecido corrige. Los dos controles (nacional, estándar) no tienen convención.

Con `--variantes` se agregan fijo diverso (uno por categoría) y dinámico k=1. Con
`--solo-probar` se reutiliza `banco_casos.json` (persistencia entre sesiones).

Sin reintentos ni reflexión (a diferencia de Reflexion): acá se aísla el efecto de ELEGIR
los ejemplos. Es la técnica más barata. Lo que guarda son casos resueltos, no lecciones ni reglas.

Los embeddings (`gemini-embedding-001`, ver `comun.embeber`) usan la misma API key de AI
Studio (`.env`). Son unas 60 llamadas al modelo en total (aprendizaje + prueba).
Salidas: banco_casos.json y few_shot_resultados.json (con --variantes,
ejemplos_dinamicos_resultados.json).

Uso:  python ejemplos_dinamicos_adk2.py                  # aprender + probar
      python ejemplos_dinamicos_adk2.py --solo-probar    # prueba con banco_casos.json existente
      python ejemplos_dinamicos_adk2.py --variantes      # además: fijo, fijo diverso, k=1
"""
import asyncio
import json
import os
import sys
from typing import Optional

import numpy as np

from comun import (baseline_vs_tecnica, con_reintentos, correr_en_paralelo, crear_workflow, embeber,
                   narrar, registrar_costo, resolver_tarea, resumen)
from google.adk import Event
from tareas_caso import TEST, TRAIN

REPETICIONES = 3
K = 3
ARCHIVO_BANCO = "banco_casos.json"


class BancoCasos:
    """Banco persistente de casos resueltos: {id, categoria, prompt, correct_answer}.

    Se recupera POR PARECIDO del enunciado (coseno sobre embeddings normalizados). Guarda
    la respuesta correcta que reveló el verificador, nunca la del agente. No reflexiona ni
    destila reglas: esa es la diferencia con Reflexion y ExpeL."""

    def __init__(self, archivo: Optional[str] = None, cargar: bool = True):
        """`cargar=False` parte de un banco VACÍO aunque el archivo exista (se sobrescribe al guardar)."""
        self.archivo = archivo
        self.entradas: list[dict] = []
        self._vectores: Optional[np.ndarray] = None   # caché; se invalida al agregar
        if cargar and archivo and os.path.exists(archivo):
            with open(archivo, encoding="utf-8") as f:
                self.entradas = json.load(f)

    def __len__(self) -> int:
        return len(self.entradas)

    def retener(self, tarea: dict) -> bool:
        """Paso 'Retain': agrega el caso (problema + respuesta correcta). Deduplica por id;
        devuelve True si lo agregó."""
        if any(e["id"] == tarea["id"] for e in self.entradas):
            return False
        self.entradas.append({"id": tarea["id"], "categoria": tarea["categoria"],
                              "prompt": tarea["prompt"], "correct_answer": tarea["correct_answer"],
                              "solucion": tarea.get("solucion", "")})
        self._vectores = None
        return True

    def buscar(self, problema: str, k: int = K) -> list[dict]:
        """Los `k` casos cuyo enunciado es más parecido a `problema`."""
        if not self.entradas:
            return []
        if self._vectores is None:
            self._vectores = embeber([e["prompt"] for e in self.entradas])
        q = embeber([problema])[0]
        return [self.entradas[i] for i in np.argsort(-(self._vectores @ q))[:k]]

    def copia_solo_lectura(self) -> "BancoCasos":
        """Instantánea sin archivo asociado, para evaluar sin contaminar el banco."""
        c = BancoCasos()
        c.entradas = [dict(e) for e in self.entradas]
        c._vectores = self._vectores
        return c

    def guardar(self) -> None:
        with open(self.archivo or ARCHIVO_BANCO, "w", encoding="utf-8") as f:
            json.dump(self.entradas, f, indent=2, ensure_ascii=False)


def formatear(casos: list[dict]) -> str:
    """Casos -> bloque de texto que entra al prompt vía `{ejemplos?}`."""
    bloques = [f"Problema: {c['prompt']}\n"
               + (f"Resolución: {c['solucion']}\n" if c.get("solucion") else "")
               + f"Respuesta correcta: {c['correct_answer']}" for c in casos]
    return "Ejemplos resueltos de la entidad (seguí sus mismas convenciones):\n\n" + "\n\n".join(bloques)


def crear_recuperador_banco(banco: BancoCasos, k: int = K):
    """Nodo-función del grafo: busca en el banco los k casos más parecidos y los deja en
    `state['ejemplos']`. Con el banco vacío no deja nada (el agente corre zero-shot)."""
    async def recuperar(node_input, ctx) -> Event:
        top = await asyncio.to_thread(banco.buscar, ctx.state["problema"], k)
        ctx.state["ejemplos"] = formatear(top) if top else ""
        # `lecciones_ids` es la clave que `resolver_tarea` devuelve en el campo `lecciones`.
        ctx.state["lecciones_ids"] = [e["id"] for e in top]
        return Event(output="recuperados")
    return recuperar


def crear_recuperador(banco: list[dict], vectores: np.ndarray, k: int):
    """Nodo-función para un banco FIJO (condición --variantes): embebe el problema, trae los
    k casos más parecidos y los deja en `state['ejemplos']`."""
    async def recuperar(node_input, ctx) -> Event:
        q = (await asyncio.to_thread(embeber, [ctx.state["problema"]]))[0]
        top = np.argsort(-(vectores @ q))[:k]
        ctx.state["ejemplos"] = formatear([banco[i] for i in top])
        ctx.state["ejemplos_ids"] = [banco[i]["id"] for i in top]
        return Event(output="recuperados")
    return recuperar


async def aprender(banco: BancoCasos) -> None:
    """Parte 1: TRAIN en orden fijo, una tarea por vez; cada caso entra al banco al terminar."""
    print(f"PARTE 1 — APRENDER: {len(TRAIN)} tareas en orden; el banco empieza vacío y se va llenando")
    wf = crear_workflow(max_intentos=1, recuperar=crear_recuperador_banco(banco))
    aciertos = []
    for t in TRAIN:
        r = await con_reintentos(lambda t=t: resolver_tarea(wf, t))
        recup = ", ".join(r["lecciones"]) if r["lecciones"] else "— (banco vacío)"
        banco.retener(t)                     # Retain: con la respuesta CORRECTA del verificador
        aciertos.append(r["primer_intento"])
        print(f"  {t['id']:<6} 1er intento {'✓' if r['primer_intento'] else '✗'} | "
              f"casos recuperados: {recup:<22} | banco: {len(banco)} caso(s)")
    banco.guardar()
    print(f"  → banco persistente: {len(banco)} casos en {banco.archivo}")
    if banco.entradas:
        e = banco.entradas[0]
        print(f"  Un caso guardado ({e['id']}): resolución = «{e.get('solucion', '')}»")
    narrar(f"El banco empezó vacío y terminó con {len(banco)} casos. Cada caso guarda el enunciado, su "
           f"resolución y la respuesta correcta que reveló el verificador, aunque el agente haya fallado: "
           f"un fallo también deja un caso válido. Mientras aprendía, el agente acertó {sum(aciertos)} de "
           f"{len(aciertos)} al primer intento; el archivo queda en disco para la próxima sesión.")


NOMBRES = {"cargo_exterior": "cargo fijo al exterior", "descuento_premium": "descuento Premium",
           "control_nacional": "control nacional", "control_estandar": "control estándar"}


def explicar_prueba(cero: list[dict], fijo: list[dict], dinamico: list[dict]) -> str:
    """«Qué pasó» armado a partir de los aciertos por categoría (dice también cuando no mejoró)."""
    n = REPETICIONES
    cat: dict = {}
    for i, t in enumerate(TEST):
        v = cat.setdefault(t["categoria"], [0, 0, 0, 0])
        for k, res in enumerate((cero, fijo, dinamico)):
            v[k] += sum(x["primer_intento"] for x in res[i * n:(i + 1) * n])
        v[3] += n
    conv = {k: v for k, v in cat.items() if not k.startswith("control")}
    ctl = {k: v for k, v in cat.items() if k.startswith("control")}
    partes = [f"{NOMBRES[k]}: sin ejemplos {v[0]}/{v[3]}, fijo {v[1]}/{v[3]}, dinámico {v[2]}/{v[3]}"
              for k, v in conv.items()]
    texto = ("Los 3 ejemplos fijos son siempre los mismos (los primeros del banco, todos de transferencias "
             "al exterior); el dinámico trae los 3 más parecidos a cada problema. Por tipo de tarea nueva — "
             + "; ".join(partes) + ". ")
    rota_fijo = [NOMBRES[k] for k, v in ctl.items() if v[1] < v[0]]
    rota_din = [NOMBRES[k] for k, v in ctl.items() if v[2] < v[0]]
    if rota_fijo or rota_din:
        texto += ("Controles: " + ("el fijo empeoró en " + ", ".join(rota_fijo) + " " if rota_fijo else "")
                  + ("el dinámico empeoró en " + ", ".join(rota_din) if rota_din else "")
                  + " (aplicó una convención donde no correspondía). ")
    else:
        texto += "En los controles no empeoró ninguna condición. "
    tot = [sum(v[k] for v in cat.values()) for k in range(4)]
    if tot[2] > tot[0] and all(v[2] >= v[0] for v in conv.values()):
        texto += "El dinámico mejoró al baseline en cada convención: recuperar por parecido le dio el ejemplo correcto."
    elif tot[2] > tot[0]:
        texto += ("El dinámico mejoró en total, pero no en toda convención: el few-shot imita lo que ve y no "
                  "extrae la regla, así que si el ejemplo no alcanza para deducirla, no ayuda.")
    else:
        texto += "En esta corrida el dinámico no mejoró al baseline."
    return texto


async def probar(banco: BancoCasos, variantes: bool) -> list[dict]:
    """Parte 2: TEST, un intento. Zero-shot contra dinámico k=3 con una copia de solo lectura."""
    snap = banco.copia_solo_lectura()
    sin = crear_workflow(max_intentos=1)
    casos = snap.entradas
    condiciones = {
        "zero-shot": (sin, None),
        "fijo (primeros 3)": (sin, {"ejemplos": formatear(casos[:3])}),
        f"dinámico k={K}": (crear_workflow(1, recuperar=crear_recuperador_banco(snap, K)), None),
    }
    if variantes:
        vectores = await asyncio.to_thread(embeber, [e["prompt"] for e in casos])
        diverso = [next(e for e in casos if e["categoria"] == c) for c in dict.fromkeys(e["categoria"] for e in casos)]
        condiciones.update({
            "fijo diverso (3)": (sin, {"ejemplos": formatear(diverso)}),
            "dinámico k=1": (crear_workflow(1, recuperar=crear_recuperador(casos, vectores, 1)), None),
        })
    print(f"\nPARTE 2 — PROBAR en {len(TEST)} tareas NUEVAS x {REPETICIONES} repeticiones, 1 intento, con una "
          f"copia de solo lectura del banco ({len(snap)} casos)")
    resultados = await asyncio.gather(*[
        correr_en_paralelo([lambda t=t, w=w, e=e: resolver_tarea(w, t, e)
                            for t in TEST for _ in range(REPETICIONES)])
        for w, e in condiciones.values()])
    print("\nRESULTADOS (acierto al primer intento)")
    out = [resumen(n, r) for n, r in zip(condiciones, resultados)]
    n = REPETICIONES
    print("\n  Por tarea (aciertos de 3 repeticiones):")
    print(f"   {'tarea':<7}{'correcto':>10}   " + "".join(f"{c:<20}" for c in condiciones))
    for i, t in enumerate(TEST):
        celdas = "".join(f"{sum(x['primer_intento'] for x in r[i * n:(i + 1) * n])}/{n:<19}" for r in resultados)
        print(f"   {t['id']:<7}{t['correct_answer']:>10g}   {celdas}")
    por_nombre = dict(zip(condiciones, resultados))
    ej = next((r for r in por_nombre[f"dinámico k={K}"] if r["lecciones"]), None)
    if ej:
        print(f"\n  Ejemplo — tarea {ej['id']}: recuperó los casos {ej['lecciones']} del banco "
              f"→ {'acertó' if ej['primer_intento'] else 'no acertó'} al primer intento")
    out.append(baseline_vs_tecnica(f"few-shot dinámico (k={K})", por_nombre["zero-shot"],
                                   por_nombre[f"dinámico k={K}"], etiqueta_baseline="zero-shot"))
    narrar(explicar_prueba(por_nombre["zero-shot"], por_nombre["fijo (primeros 3)"],
                           por_nombre[f"dinámico k={K}"]))
    return out


async def main():
    print("FEW-SHOT DINÁMICO — mostrarle al agente casos resueltos parecidos al problema")
    print("El banco de casos es un archivo que se llena solo; al probar se recuperan por parecido (embeddings).")
    print("(Tareas sintéticas: las convenciones están inventadas para el curso.)\n")
    solo_probar = "--solo-probar" in sys.argv
    variantes = "--variantes" in sys.argv
    if solo_probar:
        banco = BancoCasos(ARCHIVO_BANCO)
        if not len(banco):
            sys.exit(f"Falta {ARCHIVO_BANCO}: corré primero sin --solo-probar.")
        print(f"Banco cargado: {len(banco)} casos de {ARCHIVO_BANCO}")
    else:
        banco = BancoCasos(ARCHIVO_BANCO, cargar=False)      # siempre desde cero
        await aprender(banco)
    out = await probar(banco, variantes)
    destino = "ejemplos_dinamicos_resultados.json" if variantes else "few_shot_resultados.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    registrar_costo("ejemplos_dinamicos_adk2")


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__)
        sys.exit(0)
    asyncio.run(main())
