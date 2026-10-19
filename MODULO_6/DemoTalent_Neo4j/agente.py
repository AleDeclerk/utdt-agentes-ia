"""El agente reclutador (arquetipo ReAct): el modelo elige y encadena herramientas de lectura sobre el grafo.

Qué decide el modelo y qué decide el código:
  - El MODELO elige la herramienta, sus argumentos y cuándo ya puede responder.
  - El CÓDIGO fija el Cypher (plantillas), los topes de cada herramienta y el tope de llamadas al modelo.

El tope de llamadas es un `before_model_callback`, no `RunConfig.max_llm_calls`: así, al agotarse, el usuario recibe un
mensaje en vez de una excepción, y funciona igual en `adk web` (donde no armamos el RunConfig).
"""
from google.adk import Agent
from google.adk.models import LlmResponse
from google.genai import types

from comun import DEMO_MODEL
from herramientas import HERRAMIENTAS

MAX_LLAMADAS_MODELO = 6

INSTRUCCION = """Sos un asistente de talento de una empresa. Respondés preguntas sobre las personas y sus skills
usando SOLO las herramientas, que consultan un grafo de conocimiento:
- habilidades_de_persona(nombre): las skills de una persona.
- habilidades_similares(habilidades): skills del grafo que coinciden o se relacionan con otras o con un tema.
- personas_similares(nombre): personas parecidas a una dada. Por cada una devuelve skills_exactas_en_comun,
  pares_relacionados (skill de una ~ skill parecida de la otra), todas_sus_skills y si es de la misma comunidad.
- personas_con_habilidades(habilidades): quién tiene ciertas skills, ordenado por cuántas cubre de verdad.

Reglas:
- Usá solo las herramientas que la pregunta necesite, y encadenalas si hace falta (por ejemplo, para saber qué le
  faltaría a un reemplazo, mirá las skills de ambos). Si no hace falta ninguna, respondé directamente.
- Nunca nombres a una persona ni una skill que no haya devuelto una herramienta. No inventes.
- Si una herramienta devuelve un error o no encuentra nada, decilo con claridad; si hay sugerencias, ofrecelas.
- En personas_con_habilidades, quien tiene la skill pedida (cubre_directo) pesa más que quien tiene una parecida:
  aclará cuál es cuál.
- Es una conversación: «esas skills», «esas personas», «ellos» se refieren a lo que mostraste en tu respuesta anterior.
  Si piden gente parecida a «esas personas», llamá personas_similares una vez por cada una de las primeras 3 que nombraste,
  todas en el mismo paso. Podés llamar a la misma herramienta varias veces: no hay un límite de una persona por vez.
  Nunca pidas aclaración sobre a cuál se refieren.
- misma_comunidad (en personas_similares) es solo un dato informativo: NO indica si dos personas se parecen. No lo uses para
  decir que alguien se parece más o menos, y no lo pongas junto a cada persona. Si lo mencionás, hacelo una sola vez, al final,
  en una línea aparte, aclarando que no mide el parecido.
- Cuando hables de skills EN COMÚN, usá solo skills_exactas_en_comun; las demás son parecidas, no iguales.
- Respondé en español, breve y con los nombres tal como los devolvieron las herramientas."""


def _tope_de_llamadas(maximo: int):
    def antes_del_modelo(callback_context, llm_request):
        # `temp:` vive solo durante la invocación actual (no se arrastra entre turnos del chat).
        n = callback_context.state.get("temp:llamadas_modelo", 0) + 1
        callback_context.state["temp:llamadas_modelo"] = n
        if n > maximo:
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=(
                f"Corté la búsqueda: llegué al tope de {maximo} llamada(s) al modelo sin poder cerrar una respuesta. "
                "Probá con una pregunta más acotada."))]))
        return None
    return antes_del_modelo


def construir_agente(max_llamadas: int = MAX_LLAMADAS_MODELO) -> Agent:
    return Agent(
        name="reclutador", model=DEMO_MODEL, instruction=INSTRUCCION, tools=HERRAMIENTAS,
        before_model_callback=_tope_de_llamadas(max_llamadas))
