"""Ejercicio 1 · Parte E — RAG completo: recuperar -> construir prompt -> generar con Gemini.

El retrieval es `retrieve_local` de `rag_pipeline.py` (FAISS + MiniLM local) y la generación usa Gemini
(necesita `GOOGLE_API_KEY`). No es determinista: el retrieval sí, el texto no.

Lo que hay que mirar es la línea FUENTES: lista los chunks que ENTRARON al prompt, no los que sustentan
la respuesta.

Uso:  python ejercicio_1e_rag_generacion.py
"""
from lab_util import generar
from rag_pipeline import retrieve_local


def build_prompt(question: str, chunks: list[dict]) -> str:
    """Construye el prompt RAG con contexto y pregunta."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[Fragmento {i} — Fuente: {chunk['source']}]\n{chunk['text']}")
    context = "\n\n" + "\n\n---\n\n".join(context_parts) + "\n"

    return f"""Sos un asistente de normativa interna de una entidad financiera.
Respondé la consulta basándote ÚNICAMENTE en los fragmentos normativos
proporcionados. Si la información no está en los fragmentos, decí explícitamente
que no la tenés y no la infieras.

FRAGMENTOS NORMATIVOS:
{context}
CONSULTA: {question}

RESPUESTA:"""


def rag_answer(question: str, top_k: int = 3) -> dict:
    """Pipeline RAG completo: recuperar → construir prompt → generar."""
    chunks = retrieve_local(question, top_k=top_k)
    prompt = build_prompt(question, chunks)
    answer = generar(prompt, "rag_answer")
    return {
        "question": question,
        "answer": answer,
        "sources": [c["source"] for c in chunks],
        "chunk_ids": [c["id"] for c in chunks],
        "chunks_used": len(chunks),
    }


test_questions = [
    "¿Cuánto es el máximo que le puedo prestar a un solo cliente?",
    "¿Cuánto tiempo tiene el liquidador para pronunciarse sobre un siniestro?",
    "¿Qué pasa si el legajo del cliente está vencido?",
    "¿Cuáles son los requisitos para aprobar una póliza de suma asegurada alta?",
    "¿Se puede bonificar el recargo de zona inundable?",
]

if __name__ == "__main__":
    print("=" * 60)
    print("EVALUACIÓN DEL PIPELINE RAG")
    print("=" * 60)
    for question in test_questions:
        result = rag_answer(question)
        print(f"\nPREGUNTA: {result['question']}")
        print(f"CHUNKS RECUPERADOS: {result['chunk_ids']}")
        print(f"FUENTES: {', '.join(sorted(set(result['sources'])))}")
        print(f"RESPUESTA:\n{result['answer']}")
        print("-" * 40)
