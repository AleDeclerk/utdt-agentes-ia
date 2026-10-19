"""Ejercicio 1 · Parte F — RAG semántico vs. BM25 con una pregunta parafraseada.

Antes de generar, imprime el retrieval de cada método: es la parte determinista y la que sostiene el
punto (BM25 no recupera `norm_003`).

Salida determinista esperada del retrieval:
    BM25 top-3:      [('norm_004', 3.0437), ('norm_007', 2.2084), ('norm_002', 1.4096)]
    Semántico top-3: [('norm_003', 0.3788), ('norm_007', 0.3131), ('norm_006', 0.2866)]
La generación necesita `GOOGLE_API_KEY` y no es determinista.

Uso:  python ejercicio_1f_rag_vs_bm25.py
"""
import numpy as np
from rank_bm25 import BM25Okapi

from ejercicio_1e_rag_generacion import build_prompt, rag_answer
from lab_util import generar
from rag_corpus import CORPUS
from rag_pipeline import retrieve_local

# Construir índice BM25 sobre el mismo corpus
tokenized_corpus = [doc["text"].lower().split() for doc in CORPUS]
bm25 = BM25Okapi(tokenized_corpus)


def rag_bm25_answer(question: str, top_k: int = 3) -> dict:
    """RAG con BM25 en lugar de embeddings."""
    scores = bm25.get_scores(question.lower().split())
    top_idx = np.argsort(scores)[::-1][:top_k]
    chunks = [CORPUS[i] for i in top_idx if scores[i] > 0]

    if not chunks:
        return {"question": question, "answer": "Sin resultados BM25.", "method": "bm25"}

    prompt = build_prompt(question, chunks)
    return {"question": question, "answer": generar(prompt, "rag_bm25"), "method": "bm25"}


paraphrase_test = "¿Cuánto es lo máximo que puedo arriesgar en una única contraparte?"

if __name__ == "__main__":
    print("COMPARACIÓN: RAG Semántico vs. BM25")
    print("=" * 60)
    print(f"Pregunta (con paráfrasis): {paraphrase_test}\n")

    scores = bm25.get_scores(paraphrase_test.lower().split())
    top = np.argsort(scores)[::-1][:3]
    print("BM25 top-3:      ", [(CORPUS[i]["id"], round(float(scores[i]), 4)) for i in top])
    print("Semántico top-3: ", [(d["id"], round(d["similarity_score"], 4)) for d in retrieve_local(paraphrase_test, 3)])
    print()

    result_semantic = rag_answer(paraphrase_test)
    result_bm25 = rag_bm25_answer(paraphrase_test)

    print("--- RAG SEMÁNTICO (embeddings locales) ---")
    print(result_semantic["answer"])
    print("\n--- RAG BM25 (coincidencia léxica) ---")
    print(result_bm25["answer"])
