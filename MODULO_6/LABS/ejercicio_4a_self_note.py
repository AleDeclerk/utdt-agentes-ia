"""Ejercicio 4 · Parte A — Self-note: el modelo anota el contexto antes de responder.

Reutiliza `rag_answer` (Ejercicio 1E) y `retrieve_local` (`rag_pipeline.py`).

Retrieval determinista esperado para la pregunta de síntesis: ['norm_004', 'norm_005', 'norm_006']. Los dos
que hacen falta son norm_005 (legajo sin actualizar > 12 meses inhabilita) y norm_004 (elevar al Comité);
norm_006 es ruido. Lo que hay que evaluar no es qué respuesta "suena mejor" sino si alguna detecta el
conflicto: el legajo tiene 14 meses y el umbral es 12. Necesita `GOOGLE_API_KEY`; el texto no es determinista.

Uso:  python ejercicio_4a_self_note.py
"""
from ejercicio_1e_rag_generacion import rag_answer
from lab_util import generar
from rag_pipeline import retrieve_local

SELF_NOTE_PROMPT = """Lee los siguientes fragmentos de normativa financiera y genera notas
analíticas breves antes de responder la pregunta.

FRAGMENTOS:
{context}

INSTRUCCIONES:
1. Genera 3-5 notas clave sobre los fragmentos (prefija cada una con [NOTA])
2. Luego responde la pregunta basándote en las notas y los fragmentos

PREGUNTA: {question}"""


def self_note_answer(question: str, top_k: int = 3) -> dict:
    """RAG con auto-anotación: el modelo anota el contexto antes de responder."""
    chunks = retrieve_local(question, top_k=top_k)
    context_parts = [f"[Fragmento {i} — Fuente: {c['source']}]\n{c['text']}" for i, c in enumerate(chunks, 1)]
    context = "\n\n---\n\n".join(context_parts)
    prompt = SELF_NOTE_PROMPT.format(context=context, question=question)
    return {"question": question, "answer": generar(prompt, "self_note"), "chunks_used": len(chunks),
            "chunk_ids": [c["id"] for c in chunks]}


synthesis_question = (
    "Soy oficial de cuentas y quiero aprobar una nueva operación activa de "
    "capital de trabajo para un cliente persona jurídica cuyo legajo no se "
    "actualiza desde hace 14 meses, y el monto excede mis facultades. "
    "¿Qué reglas debo tener en cuenta?"
)

if __name__ == "__main__":
    print("Retrieval:", [c["id"] for c in retrieve_local(synthesis_question, 3)], "\n")
    print("--- RAG estándar (sin self-note) ---")
    print(rag_answer(synthesis_question)["answer"])
    print("\n--- RAG con self-note ---")
    print(self_note_answer(synthesis_question)["answer"])
