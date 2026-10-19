"""Ejercicio 4 · Parte B — GraphRAG simplificado con síntesis de Gemini (`graph_rag_answer`).

`graphrag.py` ya trae el BFS; este script agrega la variante que pasa el sub-grafo al modelo. Se corre con
`max_hops=3` (el valor por defecto del lab, que subestima la exposición: USD 4.6 M) y con `max_hops=5`
(la exposición real: USD 5.4 M). Necesita `GOOGLE_API_KEY`; el texto no es determinista, las aristas y las
sumas sí.

Uso:  python ejercicio_4b_graphrag_gemini.py
"""
from graphrag import TRIPLES, build_graph, multi_hop_traversal
from lab_util import generar


def graph_rag_answer(question: str, start_entities: list[str], graph: dict, max_hops: int = 3) -> str:
    """GraphRAG simplificado: traversal multi-hop + generación con el sub-grafo como contexto.

    En un GraphRAG de producción, start_entities se extraería de la pregunta con un LLM; acá se pasan
    directamente para mantener el ejercicio corto y determinístico.
    """
    edges = []
    for entity in start_entities:
        edges.extend(multi_hop_traversal(entity, graph, max_hops=max_hops))
    context = "\n".join(dict.fromkeys(edges))  # dedupe preservando el orden

    prompt = f"""Respondé la consulta usando ÚNICAMENTE las relaciones del grafo
societario. Si una relación necesaria para responder no está en el grafo, decilo
explícitamente en vez de completarla.

RELACIONES DEL GRAFO:
{context}

CONSULTA: {question}

RESPUESTA:"""
    return generar(prompt, f"graph_rag_h{max_hops}")


multi_hop_question = (
    "¿Quién es el beneficiario final de Textil Norte S.A. y qué exposición "
    "consolidada tiene el grupo económico con la entidad?"
)

if __name__ == "__main__":
    graph = build_graph(TRIPLES)
    print(f"Pregunta multi-hop: {multi_hop_question}")
    for hops in (3, 5):
        aristas = multi_hop_traversal("Textil Norte S.A.", graph, max_hops=hops)
        print(f"\n=== max_hops={hops}: {len(aristas)} aristas ===")
        print(f"Respuesta (GraphRAG simplificado): "
              f"{graph_rag_answer(multi_hop_question, ['Textil Norte S.A.'], graph, max_hops=hops)}")
