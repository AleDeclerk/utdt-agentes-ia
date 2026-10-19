"""Script de la demo: tabla por pregunta + agregado + barrido de alpha.

Reusa el buscador de `hybrid.py` y no llama a ningún modelo generativo. Sirve para ver, pregunta por
pregunta, dónde falla cada método de retrieval.
"""
# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 · TRAER EL BUSCADOR Y LAS MÉTRICAS
#   Reusa el HybridRetriever, el EVAL_SET y evaluate_retriever de hybrid.py.
# ══════════════════════════════════════════════════════════════════════════════
from hybrid import retriever, EVAL_SET, evaluate_retriever

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 · POR PREGUNTA: dónde falla cada método
#   Para cada una de las 7 preguntas muestra el top-3 de cada método y si el
#   fragmento correcto está (HIT) o no (MISS).
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 64)
print("POR QUERY — dónde falla cada método (top-3 ids)   alpha =", retriever.alpha)
for item in EVAL_SET:
    rel = item["relevant_ids"][0]
    print(f"\nQ: {item['query']}   (relevante: {rel})")
    for method in ["bm25", "semantic", "hybrid"]:
        ids = [c["id"] for c in retriever.retrieve(item["query"], method=method, top_k=3).chunks]
        print(f"   {method:9} {'HIT' if rel in ids else 'MISS':4} {ids}")

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 3 · AGREGADO: el promedio de las 7 preguntas
#   recall@3, MRR y latencia media de cada método. Con este corpus los tres
#   dan lo mismo: el promedio esconde las diferencias de arriba.
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 64)
print("AGREGADO")
for method in ["bm25", "semantic", "hybrid"]:
    m = evaluate_retriever(EVAL_SET, method, top_k=3)
    print(f"  {method:9} recall@3={m['recall@3']:.3f}  mrr={m['mrr']:.3f}  "
          f"lat={m['avg_latency_ms']:.1f} ms")

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 4 · BARRIDO DE ALPHA
#   Repite la evaluación del híbrido con alpha de 0.0 a 1.0 para ver si existe
#   una mezcla mejor.
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 64)
print("BARRIDO DE ALPHA")
base = retriever.alpha
for a in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
    retriever.alpha = a
    m = evaluate_retriever(EVAL_SET, "hybrid", top_k=3)
    print(f"  alpha={a:.1f}  recall@3={m['recall@3']:.3f}  mrr={m['mrr']:.3f}")
retriever.alpha = base
