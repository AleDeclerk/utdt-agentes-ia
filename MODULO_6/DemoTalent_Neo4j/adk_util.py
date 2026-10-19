"""Ejecuta un Agent de ADK 2 y devuelve un resultado uniforme: texto final, llamadas a herramientas
y si el tope de llamadas al modelo cortó la corrida."""
import asyncio
import warnings

from google.adk import Runner
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.sessions import InMemorySessionService
from google.genai import types

import comun

# ADK 2.10 avisa que la generación de esquemas de tools es EXPERIMENTAL; es informativo, no un error.
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")


async def _una_vez(texto, agente, app):
    svc = InMemorySessionService()
    runner = Runner(app_name=app, session_service=svc, agent=agente)
    await svc.create_session(app_name=app, user_id="u", session_id="s")
    msg = types.Content(role="user", parts=[types.Part(text=texto)])
    res = {"texto": None, "llamadas": [], "turnos_modelo": 0, "cortado": False}
    try:
        async for ev in runner.run_async(user_id="u", session_id="s", new_message=msg):
            if isinstance(ev.output, str) and ev.output.strip():
                res["texto"] = ev.output.strip()
            if not (ev.content and ev.content.parts):
                continue
            if ev.content.role == "model" and not ev.partial:
                res["turnos_modelo"] += 1
            for p in ev.content.parts:
                if p.function_call:
                    res["llamadas"].append({"tool": p.function_call.name, "args": dict(p.function_call.args or {})})
                elif p.function_response:
                    for c in reversed(res["llamadas"]):
                        if c["tool"] == p.function_response.name and "resp" not in c:
                            c["resp"] = p.function_response.response
                            break
                elif p.text and ev.content.role == "model":
                    res["texto"] = p.text.strip()
    except LlmCallsLimitExceededError as e:
        res["cortado"] = True
        res["error"] = str(e)
    return res


async def ejecutar(texto, *, agente, app="demo", intentos=5):
    """Reintenta ante 429 (y lo reporta). El tope de llamadas NO se reintenta: es una decisión de código."""
    for i in range(intentos):
        try:
            return await _una_vez(texto, agente, app)
        except Exception as e:  # noqa: BLE001
            if comun.es_429(e) and i < intentos - 1:
                espera = min(60, 20 * (i + 1))
                comun.AVISOS_429.append(f"{app}: 429 (intento {i + 1}), espero {espera}s")
                print(f"  [429] {app}: reintento en {espera}s")
                await asyncio.sleep(espera)
                continue
            msg = comun.explicar_error(e)
            if msg:
                raise SystemExit(msg) from e
            raise
