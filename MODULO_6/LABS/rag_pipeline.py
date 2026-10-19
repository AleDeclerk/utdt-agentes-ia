"""Pipeline RAG local: embeddings + índice FAISS + retrieval (sin LLM).

Ejercicio 1, Partes C y D. Este paso no llama a ningún modelo generativo ni usa la API key:
los embeddings se calculan con un modelo local de `sentence-transformers` y corren 100% en CPU.
"""
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

from rag_corpus import CORPUS

# Modelo local multilingüe (funciona bien en español) — se descarga una sola
# vez de Hugging Face y corre 100% en CPU, sin llamadas de red por embedding.
embed_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Genera embeddings usando el modelo local de sentence-transformers."""
    embeddings = embed_model.encode(texts)
    return np.asarray(embeddings).tolist()


def _build_index():
    print(f"Corpus cargado: {len(CORPUS)} documentos")
    print("Generando embeddings del corpus...")
    corpus_texts = [doc["text"] for doc in CORPUS]
    corpus_embeddings = embed_texts(corpus_texts)
    print(f"Embeddings generados: {len(corpus_embeddings)} vectores")
    print(f"Dimensión de cada vector: {len(corpus_embeddings[0])}")

    embeddings_array = np.array(corpus_embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings_array)

    dim = embeddings_array.shape[1]
    idx = faiss.IndexFlatIP(dim)
    idx.add(embeddings_array)
    print(f"Índice FAISS creado con {idx.ntotal} vectores de dimensión {dim}")
    return idx


index = _build_index()


def retrieve_local(query: str, top_k: int = 3) -> list[dict]:
    """Recupera los top_k documentos más similares a la query (FAISS local)."""
    query_emb = embed_texts([query])
    query_array = np.array(query_emb, dtype=np.float32)
    faiss.normalize_L2(query_array)

    scores, indices = index.search(query_array, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0:
            doc = CORPUS[idx].copy()
            doc["similarity_score"] = float(score)
            results.append(doc)
    return results


if __name__ == "__main__":
    test_query = "¿Cuánto es el máximo que le puedo prestar a un cliente?"
    retrieved = retrieve_local(test_query, top_k=3)
    print(f"\nQuery: '{test_query}'")
    for i, doc in enumerate(retrieved):
        print(f"\n[{i+1}] Score: {doc['similarity_score']:.4f}")
        print(f"    Fuente: {doc['source']}")
        print(f"    Texto: {doc['text'][:100]}...")
