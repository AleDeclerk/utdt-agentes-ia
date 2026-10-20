#!/usr/bin/env python3
# generar_evalset.py — escribe el EvalSet de ADK a partir de los siete casos de
# entorno/corpus.py, que sigue siendo la única fuente de los casos.
#
# Resultado: soporte_tienda/soporte_tienda.evalset.json. Va DENTRO de la carpeta del agente
# porque ahí lo buscan `adk web` (pestaña Eval) y `adk eval` cuando se le pasa un id en lugar
# de una ruta.
#
# Cómo se traduce cada parte de un caso:
#   mensaje del cliente         → conversation[0].user_content
#   trayectoria esperada        → conversation[0].intermediate_data.tool_uses
#   respuesta de referencia     → conversation[0].final_response   (la usa ROUGE-1)
#   estado inicial de la sesión → session_input.state
#   criterios en texto (juez)   → rubrics   (a nivel de caso; los usa el juez de rúbricas)
#   estado final del mundo      → final_session_state   (ADK lo guarda pero ninguna métrica lo
#                                                        compara: lo mide estado_final_del_mundo)
#
# Uso (desde DEMOS/, con el entorno virtual activado):
#   python demo_con_adk_evals/generar_evalset.py
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from google.genai import types  # noqa: E402

from google.adk.evaluation.eval_case import EvalCase, IntermediateData, Invocation, SessionInput  # noqa: E402
from google.adk.evaluation.eval_rubrics import Rubric, RubricContent  # noqa: E402
from google.adk.evaluation.eval_set import EvalSet  # noqa: E402

from entorno.corpus import CORPUS  # noqa: E402
from entorno.zoologico import REFERENCIA  # noqa: E402

APP = "soporte_tienda"
SALIDA = AQUI / APP / f"{APP}.evalset.json"

# Respuesta de referencia de cada caso: texto escrito a mano (el corpus guarda frases que la
# respuesta debe contener, no una respuesta completa). La del primer caso es la misma que
# usa la demostración 1.
REFERENCIAS = {
    "taza_rota": REFERENCIA,
    "fuera_de_plazo": "Tu pedido B70415 se entregó hace 45 días y nuestra política de "
                      "devoluciones cubre hasta 30 días, así que no puedo reembolsarlo.",
    "cancelar_en_proceso": "Listo, cancelé el pedido C55120 como pediste.",
    "cancelar_entregado": "El pedido A89268 ya fue entregado, así que no puedo cancelarlo. "
                          "¿Querés que te derive con una persona del equipo?",
    "consulta_estado": "Tu pedido D31877 ya está en camino y debería llegar en unos 2 días.",
    "id_con_typo": "No encuentro el pedido A89286. ¿Podés confirmarme el número?",
    "consulta_politica": "Podés devolver un pedido hasta 30 días después de recibirlo; el "
                         "reembolso se acredita en 3 a 5 días hábiles.",
}


# Qué debe cumplir la respuesta de cada caso, en lenguaje natural, para que la evalúe un juez.
# Se derivan de la intención de cada caso (su `nota` y sus `frases` en corpus.py), no de lo
# que el agente contestó; aun así, se escribieron después de ver las corridas de diagnóstico.
# Reemplazan a las frases fijas de phrase_recall: piden lo que importa («pide verificar el
# número») sin exigir las palabras exactas.
# Una más, `sin_inventar`, vale para todos los casos y está en test_config.json.
RUBRICAS = {
    "taza_rota": [
        ("monto", "Informa que se reembolsó el precio de la taza (19,99) y no el total del pedido (39,99)."),
        ("plazo", "Informa que el reembolso se acredita en 3 a 5 días hábiles."),
    ],
    "fuera_de_plazo": [
        ("plazo", "Explica que el pedido está fuera del plazo de 30 días y que por eso no se reembolsa."),
    ],
    "cancelar_en_proceso": [
        ("cancelacion", "Confirma la cancelación del pedido C55120."),
    ],
    "cancelar_entregado": [
        ("aclara_o_deriva", "Aclara la intención del cliente o lo deriva con una persona del equipo, "
                            "y no dice que canceló ni que reembolsó."),
    ],
    "consulta_estado": [
        ("estado", "Informa dónde está el pedido D31877: el estado del envío y los días estimados de llegada."),
    ],
    "id_con_typo": [
        ("pide_verificar", "Dice que no encontró el pedido y pide verificar o confirmar el número, "
                           "sin actuar sobre otro pedido."),
    ],
    "consulta_politica": [
        ("plazo", "Informa el plazo de 30 días para las devoluciones."),
    ],
}


def a_rubricas(caso_id: str) -> list[Rubric]:
    """Las rúbricas de un caso como las espera ADK. Dos detalles que ADK no avisa si se olvidan:
    el `type` tiene que ser el del juez (FINAL_RESPONSE_QUALITY), o el juez las descarta en
    silencio; y los `rubric_id` no pueden repetirse con los de test_config.json (es un error),
    por eso llevan el id del caso como prefijo."""
    return [Rubric(rubric_id=f"{caso_id}__{clave}", rubric_content=RubricContent(text_property=texto),
                   type="FINAL_RESPONSE_QUALITY")
            for clave, texto in RUBRICAS[caso_id]]


def a_eval_case(caso) -> EvalCase:
    """Un caso del corpus como EvalCase de ADK: una conversación de un solo turno."""
    turno = Invocation(
        invocation_id="turno-1",
        user_content=types.Content(role="user", parts=[types.Part(text=caso.mensaje)]),
        final_response=types.Content(role="model", parts=[types.Part(text=REFERENCIAS[caso.id])]),
        intermediate_data=IntermediateData(tool_uses=[
            types.FunctionCall(name=ll["tool"], args=ll["params"]) for ll in caso.esperadas]),
    )
    return EvalCase(
        eval_id=caso.id,
        conversation=[turno],
        session_input=SessionInput(app_name=APP, user_id="alumno", state={}),
        rubrics=a_rubricas(caso.id),
        final_session_state=caso.estado_esperado,
    )


def main() -> None:
    assert set(REFERENCIAS) == {c.id for c in CORPUS}, "falta (o sobra) una respuesta de referencia"
    assert set(RUBRICAS) == {c.id for c in CORPUS}, "falta (o sobra) un conjunto de rúbricas"
    conjunto = EvalSet(
        eval_set_id=APP,
        name="Soporte de la tienda · módulo 9",
        description="Los siete casos de entorno/corpus.py, en el formato de ADK.",
        eval_cases=[a_eval_case(c) for c in CORPUS],
    )
    texto = conjunto.model_dump_json(by_alias=True, exclude_none=True, indent=2)
    EvalSet.model_validate_json(texto)            # ida y vuelta: lo que se escribe, ADK lo lee
    SALIDA.write_text(texto + "\n", encoding="utf-8")
    print(f"escrito {SALIDA.relative_to(AQUI.parent)} · {len(conjunto.eval_cases)} casos")


if __name__ == "__main__":
    main()
