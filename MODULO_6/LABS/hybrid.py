"""HybridRetriever (BM25 + FAISS local) y evaluación comparativa (sin LLM).

Ejercicio 3: implementación base del buscador híbrido y evaluación comparativa. Es puro `numpy` +
`rank_bm25` + `faiss`: no llama a ningún modelo generativo.
"""
import time
from dataclasses import dataclass

import numpy as np

from rag_corpus import CORPUS
from rag_pipeline import embed_model


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · EL RESULTADO DE UNA BÚSQUEDA
#   `RetrievalResult` agrupa la pregunta, el método usado, los fragmentos
#   recuperados y la latencia.
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class RetrievalResult:
    query: str
    method: str
    chunks: list[dict]
    latency_ms: float


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · EL BUSCADOR HÍBRIDO (BM25 + embeddings)
#   Una sola clase con tres formas de buscar: por palabras (bm25), por
#   significado (semantic) y la mezcla de ambas (hybrid).
# ══════════════════════════════════════════════════════════════════════════════
class HybridRetriever:
    """Combina BM25 léxico y embeddings semánticos."""

    def __init__(self, corpus: list[dict], embed_model, alpha: float = 0.5):
        self.corpus = corpus
        self.embed_model = embed_model
        self.alpha = alpha
        self._build_bm25_index()
        self._build_vector_index()

    # ── 2a · Construir los dos índices: uno por palabras (BM25) y otro por significado (FAISS) ──
    def _build_bm25_index(self):
        from rank_bm25 import BM25Okapi
        tokenized = [doc["text"].lower().split() for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        print("Índice BM25 construido.")

    def _build_vector_index(self):
        import faiss
        texts = [doc["text"] for doc in self.corpus]
        self.embeddings = np.array(
            self.embed_model.encode(texts), dtype=np.float32
        )
        faiss.normalize_L2(self.embeddings)
        dim = self.embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(dim)
        self.faiss_index.add(self.embeddings)
        print(f"Índice vectorial construido: {self.faiss_index.ntotal} vectores.")

    # ── 2b · Puntuar cada fragmento con cada método (BM25 se normaliza dividiendo por su máximo) ──
    def _bm25_scores(self, query: str) -> np.ndarray:
        scores = self.bm25.get_scores(query.lower().split())
        max_s = scores.max()
        return scores / (max_s + 1e-9)

    def _semantic_scores(self, query: str) -> np.ndarray:
        import faiss
        q_vec = np.array(self.embed_model.encode([query]), dtype=np.float32)
        faiss.normalize_L2(q_vec)
        scores, idxs = self.faiss_index.search(q_vec, len(self.corpus))
        ordered_scores = np.zeros(len(self.corpus))
        for score, idx in zip(scores[0], idxs[0]):
            if idx >= 0:
                ordered_scores[idx] = score
        return ordered_scores

    # ── 2c · retrieve(): elige el método y, en el híbrido, mezcla los puntajes con alpha; devuelve el top-k ──
    def retrieve(self, query: str, method: str = "hybrid", top_k: int = 3) -> RetrievalResult:
        t0 = time.time()

        if method == "bm25":
            scores = self._bm25_scores(query)
        elif method == "semantic":
            scores = self._semantic_scores(query)
        elif method == "hybrid":
            bm25_s = self._bm25_scores(query)
            sem_s = self._semantic_scores(query)
            scores = (1 - self.alpha) * bm25_s + self.alpha * sem_s
        else:
            raise ValueError(f"Método desconocido: {method}")

        top_idx = np.argsort(scores)[::-1][:top_k]
        chunks = []
        for idx in top_idx:
            doc = self.corpus[idx].copy()
            doc["retrieval_score"] = float(scores[idx])
            chunks.append(doc)

        latency = (time.time() - t0) * 1000
        return RetrievalResult(query=query, method=method, chunks=chunks, latency_ms=latency)


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · EL BUSCADOR LISTO PARA USAR
#   Se crea una instancia con el corpus de 8 normas y alpha = 0.6, el peso de
#   la mezcla entre BM25 y semántico.
# ══════════════════════════════════════════════════════════════════════════════
# Construir retriever híbrido
retriever = HybridRetriever(CORPUS, embed_model, alpha=0.6)

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · EL CONJUNTO DE EVALUACIÓN (EVAL_SET)
#   7 preguntas, cada una con el id del fragmento que debería aparecer entre
#   los primeros resultados.
# ══════════════════════════════════════════════════════════════════════════════
# Dataset de evaluación con respuestas esperadas
EVAL_SET = [
    {"query": "¿Cuánto puedo prestarle como máximo a un solo cliente?",
     "relevant_ids": ["norm_003"]},
    {"query": "Plazos para que el liquidador se expida sobre un siniestro",
     "relevant_ids": ["norm_008"]},
    {"query": "¿Qué pasa si el legajo está desactualizado?",
     "relevant_ids": ["norm_005"]},
    {"query": "Requisitos para aprobar una póliza de suma asegurada alta",
     "relevant_ids": ["norm_001"]},
    {"query": "¿Puedo bonificar el recargo de zona inundable?",
     "relevant_ids": ["norm_002"]},
    {"query": "Cuándo vence el dictamen de riesgos",
     "relevant_ids": ["norm_004"]},
    {"query": "Plazo máximo de la línea de capital de trabajo",
     "relevant_ids": ["norm_007"]},
]


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 5 · LAS MÉTRICAS: recall@k, MRR y latencia
#   Para cada pregunta mira si el fragmento correcto está en el top-k (recall)
#   y en qué posición (MRR), y promedia.
# ══════════════════════════════════════════════════════════════════════════════
def evaluate_retriever(eval_set: list[dict], method: str, top_k: int = 3) -> dict:
    """Calcula Recall@K, MRR y latencia promedio para un método."""
    recalls = []
    reciprocal_ranks = []
    latencies = []

    for item in eval_set:
        result = retriever.retrieve(item["query"], method=method, top_k=top_k)
        retrieved_ids = [c["id"] for c in result.chunks]
        relevant = set(item["relevant_ids"])

        hits = len(relevant & set(retrieved_ids))
        recall = hits / len(relevant)
        recalls.append(recall)

        rr = 0.0
        for rank, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in relevant:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)
        latencies.append(result.latency_ms)

    return {
        "method": method,
        f"recall@{top_k}": np.mean(recalls),
        "mrr": np.mean(reciprocal_ranks),
        "avg_latency_ms": np.mean(latencies),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 6 · EJECUCIÓN DIRECTA (opcional)
#   Imprime las métricas de los tres métodos. La demo usa comparar_metodos.py,
#   que además muestra el detalle por pregunta.
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("EVALUACIÓN COMPARATIVA DE MÉTODOS DE RETRIEVAL")
    print("=" * 60)
    for method in ["bm25", "semantic", "hybrid"]:
        metrics = evaluate_retriever(EVAL_SET, method, top_k=3)
        print(f"\nMétodo: {method.upper()}")
        print(f"  Recall@3:        {metrics['recall@3']:.3f}")
        print(f"  MRR:             {metrics['mrr']:.3f}")
        print(f"  Latencia media:  {metrics['avg_latency_ms']:.1f} ms")
