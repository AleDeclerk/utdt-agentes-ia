"""Helper común de los labs que llaman a Gemini (Ejercicios 1E, 1F, 4A y 4B).

Crea un único `genai.Client()` (toma `GOOGLE_API_KEY` del `.env`) y reintenta ante 429 o cortes de red
(ver `adk_util.py`).
"""
import os

from dotenv import load_dotenv

load_dotenv()

from google import genai

from adk_util import con_reintentos

GEMINI_MODEL = os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
_cliente = None


def generar(prompt: str, etiqueta: str = "gemini") -> str:
    """Una llamada a Gemini; devuelve el texto de la respuesta."""
    global _cliente
    if _cliente is None:
        _cliente = genai.Client()
    r = con_reintentos(lambda: _cliente.models.generate_content(model=GEMINI_MODEL, contents=prompt), etiqueta)
    return r.text
