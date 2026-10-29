# Setup y problemas encontrados

Problemas reales que aparecieron al correr los labs, con la fecha en que se verificó cada uno. Antes de aplicar un arreglo viejo, conviene confirmar que sigue vigente.

## API key y modelos

- **La key de Google AI Studio empieza con `AQ.`**, no con `AIza` (formato viejo). Funciona con ADK. *(26/09)*
- **Los modelos `gemini-2.5-*` dan 404** ("no longer available to new users"). Reemplazo: `gemini-3.8-flash`. Si da 503 (saturado), `gemini-3.7-flash` o `gemini-3.5-flash-lite`. *(26/09 y 27/09)*
  - Ya está aplicado en el commit propio de este repo: `MODULO_1/LABS` (versiones B y C) y `ADK_Tutorial0` (`tools_agent`, `structured_output`).
  - Siguen con modelos 2.5: `MODULO_2`, `MODULO_5` y el default de `MODULO_9/DEMOS` (ahí alcanza con `MODEL_NAME=gemini-3.8-flash` en el `.env`, lo sugiere su README).
- **La tool `google_search` da 429 con la capa gratuita**: el grounding con Google Search no está disponible gratis para Gemini 3.x. Con plan pago anda (se cargaron USD 5 el 30/09). *(30/09)*

## ADK_Tutorial0

- **`requirements.txt` no instalaba**: pedía `google-genai<2.0.0` y `google-adk>=2.8.0`, que necesita `google-genai>=2.19`. Se sacó el tope (commit propio). *(26/09)*
- El README dice `cd ADK/Tutorial0`, pero la carpeta es `ADK_Tutorial0` en la raíz.
- **`sessions_and_agents`** no corre con `adk web`: tiene su script `run_agent_with_session.py`. El modelo sale de la variable `GOOGLE_GENAI_MODEL`, así que hay que copiar su `.env.example`, no el `.env` de otro ejemplo. *(27/09)*
- **`agents_and_callbacks`**: los `.env.example` traen activa la opción de Vertex. Copiar el `.env` de `tools_agent` y cambiar la línea `model=` de cada `agent.py`. *(30/09)*
- **`marketing_campaign_agent`**: el README dice que ADK inyecta el estado, pero las instrucciones escriben `state['clave']` sin llaves y ADK solo reemplaza `{clave}`. Los agentes leen lo anterior por el historial. *(30/09)*

## Otros módulos

- **`MODULO_6/LABS` necesita Python 3.10 a 3.13** (no 3.14) y PyTorch 2.14, que solo tiene paquetes para Apple Silicon con macOS 14 o superior. El entorno ocupa unos 1,6 GB más 450 MB del modelo de embeddings. *(según su README, 29/10)*
- **`MODULO_9/DEMOS`** fija la versión de ADK porque las métricas cambiaron entre 2.10 y 2.12. Probado con Python 3.12. *(según su README, 29/10)*

## Rutina

- Cada terminal nueva: `cd` a la carpeta del ejemplo y `source .venv/bin/activate`.
- Correr los comandos en la Terminal propia, no en una sin el venv activado.
- Para ver los eventos de una sesión de `adk web` sin abrir el navegador: `curl 127.0.0.1:8000/apps/<app>/users/user/sessions/<id>`.
