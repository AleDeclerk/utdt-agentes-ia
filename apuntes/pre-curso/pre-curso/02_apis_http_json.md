# Módulo 02 — APIs, HTTP y JSON

## Por qué hace falta

Los agentes del curso se conectan a modelos (Google AI Studio) y a herramientas externas vía llamadas HTTP. Los schemas de las tools (qué parámetros recibe cada función que el agente puede invocar) se definen en JSON. Sin esta base, los módulos 4 (tool use) y 8 (multiagente / A2A) son difíciles de seguir.

## Autodiagnóstico

1. ¿Sabés qué es un endpoint y qué diferencia hay entre un `GET` y un `POST`?
2. ¿Entendés qué es una API key y por qué no se debe subir a un repo público?
3. ¿Podés leer un objeto JSON anidado (con listas y diccionarios adentro) sin confundirte?
4. ¿Usaste alguna vez una librería tipo `requests` (Python) o `fetch` (JS) para consumir una API externa?
5. ¿Sabés qué es un código de estado HTTP (200, 401, 429, 500) y qué implica cada uno a grandes rasgos?

## Si hay brechas: recursos gratuitos

**Fundamentos de HTTP**
- MDN, "An overview of HTTP": https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview

**Qué es una API (nivel conceptual, no técnico)**
- freeCodeCamp, "What is an API": https://www.freecodecamp.org/news/what-is-an-api-in-english-please-b880a3214a82/

**JSON**
- Documentación oficial de json.org (referencia corta del formato): https://www.json.org/json-en.html

**Consumir APIs en Python**
- Documentación de la librería `requests`: https://requests.readthedocs.io/en/latest/user/quickstart/

## Tiempo estimado

2-3 horas — es el módulo más rápido de resolver si ya se programó alguna vez, porque suele ser más falta de vocabulario que de habilidad real.
