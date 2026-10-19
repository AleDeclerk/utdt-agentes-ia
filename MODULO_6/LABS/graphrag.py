"""GraphRAG simplificado — traversal multi-hop en memoria (sin LLM ni base de grafos).

Ejercicio 4, Parte B. Es un BFS de Python puro sobre un `dict`. Este archivo solo trae el recorrido
(`multi_hop_traversal`); la variante que le pasa el sub-grafo a Gemini para que redacte la respuesta
está en `ejercicio_4b_graphrag_gemini.py`.
"""
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · LOS DATOS: 8 hechos sobre el grupo de Textil Norte
#   Cada tripleta es (sujeto, relación, objeto). Las exposiciones están
#   escritas en el texto: USD 3.4M, 1.2M y 0.8M.
# ══════════════════════════════════════════════════════════════════════════════
# Grafo de juguete: estructura societaria y exposición consolidada (sintético).
TRIPLES = [
    ("Textil Norte S.A.",            "controlada_por",        "Grupo Andes Holding S.A."),
    ("Grupo Andes Holding S.A.",     "controlada_por",        "Andes Capital B.V."),
    ("Andes Capital B.V.",           "beneficiario_final_es", "M. Ferrari"),
    ("Grupo Andes Holding S.A.",     "controla_a",            "Logística Andes S.R.L."),
    ("Logística Andes S.R.L.",       "tiene_exposicion",      "Acuerdo en cuenta corriente por USD 1.2M"),
    ("Textil Norte S.A.",            "tiene_exposicion",      "Préstamo de capital de trabajo por USD 3.4M"),
    ("M. Ferrari",                   "director_en",           "Agroinsumos del Litoral S.A."),
    ("Agroinsumos del Litoral S.A.", "tiene_exposicion",      "Descuento de cheques por USD 0.8M"),
]


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · CONSTRUIR EL GRAFO
#   Convierte la lista de tripletas en un diccionario {sujeto: [(relación,
#   objeto), ...]}.
# ══════════════════════════════════════════════════════════════════════════════
def build_graph(triples: list[tuple]) -> dict:
    """Construye un grafo dirigido {sujeto: [(predicado, objeto), ...]}."""
    graph = defaultdict(list)
    for subj, pred, obj in triples:
        graph[subj].append((pred, obj))
    return graph


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · EL RECORRIDO POR NIVELES (BFS)
#   Desde una entidad sigue las relaciones hasta max_hops saltos y devuelve
#   las aristas. Acá es donde el tope de saltos corta el recorrido.
# ══════════════════════════════════════════════════════════════════════════════
def multi_hop_traversal(start_entity: str, graph: dict, max_hops: int = 3) -> list[str]:
    """BFS que devuelve los triples alcanzables desde start_entity en <= max_hops."""
    visited_edges = []
    frontier = [start_entity]
    seen = {start_entity}
    for _ in range(max_hops):
        next_frontier = []
        for entity in frontier:
            for pred, obj in graph.get(entity, []):
                visited_edges.append(f"{entity} --{pred}--> {obj}")
                if obj not in seen:
                    seen.add(obj)
                    next_frontier.append(obj)
        frontier = next_frontier
        if not frontier:
            break
    return visited_edges


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · LA DEMO: recorrer con 3 y con 5 saltos
#   Imprime cuántas aristas alcanza con cada tope y cuáles son. El script no
#   suma los montos.
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    graph = build_graph(TRIPLES)

    for hops in (3, 5):
        edges = multi_hop_traversal("Textil Norte S.A.", graph, max_hops=hops)
        print(f'multi_hop_traversal("Textil Norte S.A.", graph, max_hops={hops})   -> {len(edges)} aristas')
        for e in edges:
            print(f"  {e}")
        print()
