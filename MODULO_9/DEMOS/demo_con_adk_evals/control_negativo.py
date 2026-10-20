#!/usr/bin/env python3
# control_negativo.py — ¿los jueces de test_config.json marcan una respuesta MALA conocida?
#
# El veredicto de la demo depende de dos jueces (hallucinations_v1 y el juez de rúbricas). Un
# juez es otro modelo y nadie lo evaluó: si diera siempre «aprobado», el veredicto se vería
# verde sin medir nada. El control negativo es la comprobación mínima: pasarle respuestas ya
# escritas, de las que una persona sabe que inventan algo, junto a una fiel, y mirar que las
# marque.
#
# Usa los mismos jueces y la misma configuración que `adk eval` (se leen de test_config.json) y
# las respuestas de entorno/juez_items.py, con su etiqueta humana. Solo se aplica la rúbrica
# general `sin_inventar`: son respuestas sueltas, sin las rúbricas de ningún caso.
#
# Con tres ítems no calibra nada (la calibración, con matriz de confusión y κ de Cohen, está en
# demos/demo2_juez.py): solo detecta un juez que aprueba todo.
#
# CUESTA DINERO: unas 15 llamadas al juez (del orden de $0.05).
#
# Uso (desde DEMOS/, con el entorno virtual activado):
#   python demo_con_adk_evals/control_negativo.py
import asyncio
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import soporte_tienda  # noqa: E402,F401  (agrega los paths e instala el parser tolerante)

from google.adk.evaluation.eval_config import get_eval_metrics_from_config, get_evaluation_criteria_or_default  # noqa: E402
from google.adk.evaluation.metric_evaluator_registry import register_custom_metrics_from_config  # noqa: E402

from entorno.juez_items import ITEMS, invocacion  # noqa: E402

JUECES = ("hallucinations_v1", "rubric_based_final_response_quality_v1")
# (ítem, qué debería pasar si el juez sirve)
CONTROL = [("fiel_reembolso", "aprobar"), ("comprobante_inventado", "desaprobar"), ("accion_inventada", "desaprobar")]


async def main() -> None:
    config = get_evaluation_criteria_or_default(str(AQUI / "soporte_tienda" / "test_config.json"))
    registro = register_custom_metrics_from_config(config)
    metricas = [m for m in get_eval_metrics_from_config(config) if m.metric_name in JUECES]
    por_id = {i.id: i for i in ITEMS}

    print(f"{'ítem':<24}{'debería':<12}" + "".join(f"{m.metric_name.split('_v1')[0][:22]:>24}" for m in metricas))
    for item_id, esperado in CONTROL:
        item = por_id[item_id]
        fila = []
        for m in metricas:
            evaluador = registro.get_evaluator(m)         # uno por ítem: el juez de rúbricas guarda estado
            r = await evaluador.evaluate_invocations([invocacion(item)], None)
            puntaje = r.overall_score
            fila.append("sin score" if puntaje is None else f"{puntaje:.2f} {'aprueba' if puntaje >= 1.0 else 'DESAPRUEBA'}")
        print(f"{item_id:<24}{esperado:<12}" + "".join(f"{x:>24}" for x in fila))
    print("\nSi los dos jueces aprueban los ítems que deberían desaprobar, el veredicto no vale nada.")


if __name__ == "__main__":
    asyncio.run(main())
