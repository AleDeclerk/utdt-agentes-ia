"""GraphRAG + ADK 2 — el Workflow como plano de control, el grafo como plano de datos.

Versión ejecutable de la arquitectura router -> ejecutor -> validador -> respuesta,
con la API REAL de ADK 2 (`Workflow(edges=[...])`, `Event(route=...)`, `Runner(node=...)`)
y con el grafo en memoria de `graphrag.py`. No usa una base de grafos ni ningún modelo.

QUÉ HACE Y QUÉ NO (para no sobre-vender la demo):
  - Router DETERMINISTA: busca el nombre de una entidad del grafo en la pregunta.
    No parsea strings emitidos por un modelo.
  - Ejecutor: traversal multi-hop (BFS) con un tope de saltos fijado por el código.
  - Validador ESTRUCTURAL: si al llegar al tope de saltos quedan aristas sin explorar
    en la frontera, vuelve al ejecutor con un salto más (ciclo real del Workflow).
    Hay un tope de expansiones: el agente propone, el código decide.
  - La suma de exposiciones la hace el código, no un modelo.
  - Búsqueda GLOBAL: NO implementada. Requiere comunidades + resúmenes (Leiden + LLM),
    que este grafo de 8 tripletas no tiene. El nodo lo dice explícitamente.
  - No hay síntesis con LLM: la respuesta se arma de forma determinista. En un
    sistema real, ahí iría un `Agent` que redacte sobre `retrieved_context`.

Uso:  python graphrag_adk2.py
"""
import asyncio
import re

from google.adk import Event, Runner, Workflow
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import START
from google.genai import types

from graphrag import TRIPLES, build_graph, multi_hop_traversal

APP_NAME = "graphrag_adk2"
USER_ID = "analista_demo"

GRAFO = build_graph(TRIPLES)
SALTOS_INICIALES = 3

# Entidades consultables: todo nodo salvo las exposiciones (son hojas descriptivas).
ENTIDADES = sorted(
    {s for s, _, _ in TRIPLES} | {o for _, p, o in TRIPLES if p != "tiene_exposicion"}
)
PALABRAS_GLOBALES = ("principales", "panorama", "en general", "toda la", "todo el", "patrones")
SUFIJOS_LEGALES = {"sa", "srl", "bv"}


def _clave(texto: str) -> str:
    """Normaliza para comparar: minúsculas, sin signos, sin sufijos legales.
    Evita el fallo de 'Textil Norte' contra 'Textil Norte S.A.' (dos nodos distintos)."""
    t = re.sub(r"[.,¿?¡!]", "", texto.lower())
    return " ".join(w for w in t.split() if w not in SUFIJOS_LEGALES)


def construir_grafo(tope_expansiones: int = 2) -> Workflow:
    """Arma el Workflow. `tope_expansiones` es el tope de código del ciclo de expansión."""

    def enrutar(node_input) -> Event:
        pregunta = node_input.parts[0].text
        clave_pregunta = _clave(pregunta)
        candidatas = [e for e in ENTIDADES if _clave(e) in clave_pregunta]
        estado = {"pregunta": pregunta, "traza": []}
        if candidatas:
            entidad = max(candidatas, key=lambda e: len(_clave(e)))
            estado.update(entidad=entidad, max_hops=SALTOS_INICIALES, expansiones=0)
            estado["traza"].append(f"enrutar: entidad='{entidad}' -> local")
            return Event(output=estado, route="local")
        if any(p in pregunta.lower() for p in PALABRAS_GLOBALES):
            estado["traza"].append("enrutar: sin entidad, pregunta agregada -> global")
            return Event(output=estado, route="global")
        estado["traza"].append("enrutar: sin entidad ni pregunta agregada -> aclarar")
        return Event(output=estado, route="aclarar")

    def traversal_local(node_input: dict) -> Event:
        estado = dict(node_input)
        entidad, saltos = estado["entidad"], estado["max_hops"]
        aristas = multi_hop_traversal(entidad, GRAFO, max_hops=saltos)
        mas = multi_hop_traversal(entidad, GRAFO, max_hops=saltos + 1)
        estado["aristas"] = aristas
        estado["frontera_abierta"] = len(mas) > len(aristas)
        estado["traza"] = estado["traza"] + [
            f"traversal: {saltos} saltos -> {len(aristas)} aristas, "
            f"frontera {'ABIERTA' if estado['frontera_abierta'] else 'cerrada'}"
        ]
        return Event(output=estado)

    def validar_subgrafo(node_input: dict) -> Event:
        estado = dict(node_input)
        if not estado["frontera_abierta"]:
            estado["traza"] = estado["traza"] + ["validar: subgrafo completo -> ok"]
            return Event(output=estado, route="listo")
        if estado["expansiones"] >= tope_expansiones:
            estado["truncado"] = True
            estado["traza"] = estado["traza"] + [
                f"validar: frontera abierta y tope de {tope_expansiones} expansiones -> truncado"
            ]
            return Event(output=estado, route="listo")
        estado["expansiones"] += 1
        estado["max_hops"] += 1
        estado["traza"] = estado["traza"] + [
            f"validar: frontera abierta -> expandir a {estado['max_hops']} saltos "
            f"(expansión {estado['expansiones']} de {tope_expansiones})"
        ]
        return Event(output=estado, route="expandir")

    def responder(node_input: dict) -> Event:
        estado = dict(node_input)
        aristas = estado["aristas"]
        total = round(sum(
            float(m) for a in aristas if "--tiene_exposicion-->" in a
            for m in re.findall(r"USD ([\d.]+)M", a)
        ), 1)
        lineas = [f"Relaciones alcanzadas desde {estado['entidad']} "
                  f"({estado['max_hops']} saltos, {len(aristas)} aristas):"]
        lineas += [f"  {a}" for a in aristas]
        lineas.append(f"Exposición sumada sobre el subgrafo: USD {total} M.")
        if estado.get("truncado"):
            lineas.append("ADVERTENCIA: subgrafo truncado por el tope de expansiones; "
                          "puede haber exposición no incluida.")
        estado["respuesta_final"] = "\n".join(lineas)
        return Event(output=estado)

    def busqueda_global(node_input: dict) -> Event:
        estado = dict(node_input)
        estado["respuesta_final"] = (
            "Búsqueda global NO implementada: requiere comunidades y resúmenes "
            "(Leiden + LLM) que este grafo de 8 tripletas no tiene."
        )
        return Event(output=estado)

    def pedir_aclaracion(node_input: dict) -> Event:
        estado = dict(node_input)
        estado["respuesta_final"] = (
            "No identifiqué ninguna entidad del grafo en la pregunta. "
            f"Entidades disponibles: {', '.join(ENTIDADES)}."
        )
        return Event(output=estado)

    return Workflow(
        name="graphrag_adk2",
        description="Router determinista, traversal con expansión validada y respuesta.",
        edges=[
            (START, enrutar),
            (enrutar, {"local": traversal_local, "global": busqueda_global,
                       "aclarar": pedir_aclaracion}),
            (traversal_local, validar_subgrafo),
            # Una sola ruta hacia `responder`: ADK 2 rechaza dos rutas distintas del
            # mismo nodo al mismo destino ("Duplicate edge"). El flag `truncado`
            # del estado distingue el caso completo del truncado.
            (validar_subgrafo, {"expandir": traversal_local, "listo": responder}),
        ],
    )


async def procesar(grafo: Workflow, pregunta: str) -> dict:
    svc = InMemorySessionService()
    session = await svc.create_session(app_name=APP_NAME, user_id=USER_ID)
    runner = Runner(node=grafo, app_name=APP_NAME, session_service=svc)
    content = types.Content(role="user", parts=[types.Part(text=pregunta)])
    ultimo = None
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=content):
        if isinstance(event.output, dict):
            ultimo = event.output
    return ultimo


async def main():
    casos = [
        ("¿Qué exposición vinculada tiene Textil Norte S.A.?", 2),
        ("¿Qué exposición tiene Logística Andes?", 2),
        ("¿Qué exposición vinculada tiene Textil Norte S.A.?", 1),
        ("¿Cuáles son los principales riesgos de toda la cartera?", 2),
        ("¿Cómo está el clima hoy?", 2),
    ]
    for pregunta, tope in casos:
        print("=" * 72)
        print(f"PREGUNTA (tope de expansiones = {tope}): {pregunta}")
        estado = await procesar(construir_grafo(tope), pregunta)
        print("TRAZA:")
        for paso in estado["traza"]:
            print(f"  - {paso}")
        print("RESPUESTA:")
        print(estado["respuesta_final"])
        print()


if __name__ == "__main__":
    asyncio.run(main())
