"""Utilidades de ADK 2 para las demos con agentes.

Ejecuta un Workflow o un Agent y devuelve un resultado uniforme: texto final, llamadas a herramientas,
tokens y si el tope de llamadas al modelo cortó la corrida. También trae los reintentos ante errores
transitorios (el límite de requests por minuto de la API key gratuita, cortes de red).
"""
import asyncio
import time
import warnings

from google.adk import Runner
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ADK avisa que la generación de esquemas de tools es EXPERIMENTAL; es informativo, no un error.
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")

AVISOS_429: list[str] = []  # reintentos por cuota o por red, para reportarlos al final de la corrida


def es_429(e: Exception) -> bool:
    t = f"{type(e).__name__} {e}"
    return "429" in t or "RESOURCE_EXHAUSTED" in t or "ResourceExhausted" in t


def es_red(e: Exception) -> bool:
    """Corte de red transitorio (DNS, conexión). Se reintenta; un error de credenciales o de API, no."""
    t = f"{type(e).__name__} {e}"
    return any(m in t for m in ("name resolution", "NameResolutionError", "ConnectionError",
                                "Max retries exceeded", "ServiceUnavailable", "Connection reset",
                                "503 UNAVAILABLE", "UNAVAILABLE", "DEADLINE_EXCEEDED", "ReadTimeout", "ConnectTimeout",
                                "RemoteProtocolError", "Server disconnected", "timed out"))


def es_transitorio(e: Exception) -> bool:
    return es_429(e) or es_red(e)


def con_reintentos(fn, etiqueta: str, intentos: int = 5):
    """Reintenta ante 429 (cuota por minuto) o cortes de red con espera exponencial, y lo reporta."""
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if es_transitorio(e) and i < intentos - 1:
                espera = 10 * (2 ** i)
                causa = "429" if es_429(e) else "red"
                AVISOS_429.append(f"{etiqueta}: {causa} (intento {i + 1}), espero {espera}s")
                print(f"  [{causa}] {etiqueta}: reintento en {espera}s")
                time.sleep(espera)
                continue
            raise


async def con_reintentos_async(fn, etiqueta: str, intentos: int = 5):
    """Igual que `con_reintentos`, para una corrutina: `fn` es una función SIN argumentos que devuelve la corrutina.
    Solo reintenta errores transitorios (cuota, red, 503); cualquier otro error se propaga."""
    for i in range(intentos):
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001
            if es_transitorio(e) and i < intentos - 1:
                espera = 10 * (2 ** i)
                causa = "429" if es_429(e) else "red"
                AVISOS_429.append(f"{etiqueta}: {causa} (intento {i + 1}), espero {espera}s")
                print(f"  [{causa}] {etiqueta}: reintento en {espera}s", flush=True)
                await asyncio.sleep(espera)
                continue
            raise


def _asociar_respuesta(llamadas: list[dict], fr) -> None:
    """Asocia la respuesta de una herramienta con SU llamada. Si el modelo lanza varias llamadas a la misma herramienta en un mismo turno
    (en paralelo), emparejar por nombre mezcla los resultados: se empareja por el `id` de la llamada y, solo si no hay id, por orden
    (la llamada más antigua de esa herramienta que todavía no tiene respuesta)."""
    if getattr(fr, "id", None):
        for c in llamadas:
            if c.get("id") == fr.id and "resp" not in c:
                c["resp"] = fr.response
                return
    for c in llamadas:
        if c["tool"] == fr.name and "resp" not in c:
            c["resp"] = fr.response
            return


async def _una_vez(texto, nodo, agente, run_config, app, seguimiento=None):
    """Corre el agente o el Workflow sobre `texto`. Si se pasa `seguimiento`, después de cada vuelta se lo llama con el resultado
    acumulado: si devuelve un mensaje, se lo manda como un turno más EN LA MISMA SESIÓN (el código le recuerda algo al agente);
    si devuelve None, se termina. Sin `seguimiento` el comportamiento es el de siempre."""
    svc = InMemorySessionService()
    runner = Runner(app_name=app, session_service=svc, **(dict(node=nodo) if nodo is not None else dict(agent=agente)))
    await svc.create_session(app_name=app, user_id="u", session_id="s")
    res = {"texto": None, "llamadas": [], "turnos_modelo": 0, "cortado": False,
           "llamadas_modelo": 0, "tokens_entrada": 0, "tokens_salida": 0, "seguimientos": 0}

    async def turno(mensaje: str) -> None:
        msg = types.Content(role="user", parts=[types.Part(text=mensaje)])
        async for ev in runner.run_async(user_id="u", session_id="s", new_message=msg, run_config=run_config):
            um = ev.usage_metadata
            if um and not ev.partial:
                res["llamadas_modelo"] += 1
                res["tokens_entrada"] += um.prompt_token_count or 0
                res["tokens_salida"] += um.candidates_token_count or 0
            if isinstance(ev.output, str) and ev.output.strip():
                res["texto"] = ev.output.strip()
            if not (ev.content and ev.content.parts):
                continue
            if ev.content.role == "model" and not ev.partial:
                res["turnos_modelo"] += 1
            for p in ev.content.parts:
                if p.function_call:
                    res["llamadas"].append({"tool": p.function_call.name, "args": dict(p.function_call.args or {}),
                                            "id": getattr(p.function_call, "id", None)})
                elif p.function_response:
                    _asociar_respuesta(res["llamadas"], p.function_response)
                elif p.text and ev.content.role == "model":
                    res["texto"] = p.text.strip()

    try:
        await turno(texto)
        while seguimiento is not None:
            siguiente = seguimiento(res)
            if not siguiente:
                break
            res["seguimientos"] += 1
            await turno(siguiente)
    except LlmCallsLimitExceededError as e:
        res["cortado"] = True
        res["error"] = str(e)
    return res


async def ejecutar(texto, *, nodo=None, agente=None, run_config=None, app="demo", intentos=4, seguimiento=None, antes=None):
    """Reintenta ante 429 o cortes de red (y lo reporta). El tope de llamadas NO se reintenta: es una decisión de código.
    `antes()` se llama al empezar CADA intento (sirve para limpiar el estado de una corrida que se reintenta);
    `seguimiento(res)` permite que el código le mande mensajes al agente en la misma sesión (ver `_una_vez`)."""
    for i in range(intentos):
        try:
            if antes is not None:
                antes()
            return await _una_vez(texto, nodo, agente, run_config, app, seguimiento)
        except Exception as e:  # noqa: BLE001
            if es_transitorio(e) and i < intentos - 1:
                espera = 15 * (i + 1)
                causa = "429" if es_429(e) else "red"
                AVISOS_429.append(f"{app}: {causa} (intento {i + 1}), espero {espera}s")
                print(f"  [{causa}] {app}: reintento en {espera}s")
                await asyncio.sleep(espera)
                continue
            raise
