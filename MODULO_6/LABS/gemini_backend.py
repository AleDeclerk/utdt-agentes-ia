"""Backend de Gemini para `LocalMemoryBankService` (en `servicios_memoria.py`).

El servicio de memoria le pide al LLM dos cosas: extraer HECHOS de una conversación y decidir si un hecho nuevo
actualiza, agrega o ignora a uno existente. Las dos son llamadas a `chat_json(mensajes, modelo_pydantic)`, que devuelve
`(objeto validado | None, meta)`. Esta clase implementa esa función con Gemini:

  - Gemini 2.5 Flash piensa por defecto y los tokens de razonamiento cuentan contra `max_output_tokens`: se apaga con
    `thinking_budget=0` y el límite de salida es generoso; si no, el JSON sale vacío o cortado y el código lo toma
    como una extracción inválida.
  - `response_schema` recibe el modelo pydantic y el código VUELVE a validar (`model_validate_json`): el modelo
    propone, el código decide. Una salida vacía o inválida se reintenta, y si sigue mal se devuelve `None`.
  - Reintenta ante 429 y cortes de red (`adk_util.con_reintentos`) y cuenta llamadas, segundos y tokens propios
    (`resumen()`).

Necesita `GOOGLE_API_KEY` (ver `.env.example`).
"""
import time

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types
from pydantic import ValidationError

from adk_util import con_reintentos


INTENTOS_SALIDA_INVALIDA = 3  # llamadas máximas por consulta si la salida no es un JSON válido


class GeminiBackend:
    def __init__(self, modelo: str):
        self.modelo = modelo
        self._cliente = None
        self.llamadas = 0
        self.segundos = 0.0
        self.tokens_entrada = 0
        self.tokens_salida = 0

    def chat_json(self, mensajes: list[dict], modelo_pydantic, *, num_predict: int = 300):
        """Devuelve `(objeto validado | None, meta)`. `mensajes` es una lista de `{"role": "system"|"user"|"assistant", "content": str}`."""
        if self._cliente is None:
            self._cliente = genai.Client()
        sistema = "\n".join(m["content"] for m in mensajes if m["role"] == "system") or None
        contenidos = [types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
                      for m in mensajes if m["role"] != "system"]
        config = types.GenerateContentConfig(
            temperature=0.0, system_instruction=sistema, response_mime_type="application/json",
            response_schema=modelo_pydantic, max_output_tokens=max(num_predict * 4, 1024),
            thinking_config=types.ThinkingConfig(thinking_budget=0) if "flash" in self.modelo.lower() else None,
            # Sin herramientas en esta llamada, la llamada automática a funciones del SDK (AFC) no tiene nada que hacer; viene activada por
            # defecto y avisa por log. Se desactiva explícitamente: no cambia lo que se le manda al modelo.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        seg = entrada = salida = 0
        obj, texto = None, ""
        for _ in range(INTENTOS_SALIDA_INVALIDA):  # una salida vacía o inválida se reintenta: el código valida, no le cree al modelo
            t0 = time.perf_counter()
            r = con_reintentos(lambda: self._cliente.models.generate_content(model=self.modelo, contents=contenidos, config=config),
                               "gemini chat_json")
            seg += time.perf_counter() - t0
            um = r.usage_metadata
            entrada += (um.prompt_token_count or 0) if um else 0
            salida += (um.candidates_token_count or 0) if um else 0
            self.llamadas += 1
            texto = (r.text or "").strip()
            try:
                obj = modelo_pydantic.model_validate_json(texto)
                break
            except (ValidationError, ValueError):
                obj = None
        self.segundos += seg
        self.tokens_entrada += entrada
        self.tokens_salida += salida
        return obj, {"texto": texto, "segundos": seg, "tokens_entrada": entrada, "tokens_salida": salida}

    def resumen(self) -> str:
        return (f"Gemini ({self.modelo}) en extracción y consolidación: {self.llamadas} llamadas, {self.segundos:.0f} s, "
                f"{self.tokens_entrada} tokens de entrada / {self.tokens_salida} de salida (el agente final no está incluido)")
