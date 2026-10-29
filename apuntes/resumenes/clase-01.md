# Clase 1 · 24/09 · Introducción a los agentes IA (Módulo 1)

> **Aviso:** la transcripción de esta clase no es confiable (Zoom la reconoció como inglés y mezcla palabras sin sentido); el contenido sale sobre todo del material del módulo 1 del repo. **[T]** = se entiende en la transcripción. **[R]** = sale del repo `MODULO_1`; no se puede confirmar que se dijera así en clase.

**Docente e invitados:** Matías Zabaljauregui. No se identifican invitados.
**Material del campus:** "Slides Mod 1". En el repo coincide con `MODULO_1/slides_preview.pdf` (32 páginas, última slide "LAB 01, entrega la próxima clase"). Tres PDFs más de la carpeta se cruzan con fragmentos de la transcripción: `slides_apertura_modelos_julio_v3.pdf`, `slides_operacion_encubierta.pdf` y `GCP_Agent_Platform.pdf`.

## En una frase
Qué es un agente, dónde cae en el espectro de agencia (código, workflow, agente), cómo elegir modelo y protocolos, y un lab que resuelve un mismo reclamo bancario de tres maneras.

## Recorrido de la clase
La transcripción tiene una sola marca, [00:46]; el orden es el del texto.

**1. Espectro de agencia [00:46]**
- [T] Los workflows con LLM conservan partes deterministas; más agencia es más grados de libertad para el sistema. El workflow tiene menos latencia; el agente es más "estadístico".
- [R] Script determinista, workflow IA, agente autónomo. La autonomía se calibra según variabilidad de la tarea y tolerancia al riesgo. Se elige la arquitectura más simple: código, workflow, RAG, agente.

**2. Modelos de fundación y selección**
- [T] Model routing: derivar cada tarea a distintos modelos según su complejidad, con un clasificador (ML o LLM). Model selection: empezar por un generalista. Se nombran Claude Code, DeepSeek (open source) y "Fable" (dudoso).
- [R] En ADK2 `model` es un string intercambiable. Ejemplo de costos con 50.000 consultas/mes: ~805 USD todo en `gemini-2.5-pro`, ~255 USD con router 70/30, ~5 USD con un workflow de una llamada a flash.

**3. Tipos de agentes**
- [T] Roles: business task, conversacional, investigación, analytics (lista parcial).
- [R] "7 + 2 tipos": además developer, domain-specific, browser-using y voice.

**4. Protocolos, async y resiliencia**
- [T] MCP se presenta como protocolo. Hay una "dimensión horizontal" donde los agentes se comunican, se descubren y se autentican, con alusión a la Linux Foundation (consistente con A2A, dudoso). Se pregunta al grupo por funciones asíncronas, hilos y multiproceso, y se mencionan resiliencia y fallbacks.
- [R] MCP (Módulo 4), A2A (Módulo 8) y 5 principios: escalabilidad, modularidad, aprendizaje continuo, resiliencia, future-proofing. El fallback a otro modelo es lógica de aplicación, no un parámetro de `Agent`.

**5. Lab en tres arquitecturas**
- [T] Primero un `if/else` "muy básico"; luego un agente con salida en formato fijo (Pydantic) y `instruction`; luego tools con confirmación y human in the loop.

**6. Cierre**
- [T] Preguntas sobre material y producción, y un debate largo sobre seguridad de IA.

## Conceptos clave
- **Agente IA [R]:** modelo de fundación más herramientas, memoria y orquestación para entradas no estructuradas y tareas de varios pasos.
- **Model routing [T]:** asignar la tarea a un modelo según su complejidad.
- **`output_schema` [T/R]:** fuerza la forma del JSON con un modelo Pydantic.
- **HITL granular [T/R]:** `FunctionTool(..., require_confirmation=True)` pide aprobación humana solo en las tools irreversibles.

## Demos y ejemplos mostrados
Todo [R], salvo lo indicado. Carpeta `MODULO_1/LABS`: un banco recibe reclamos de tarjeta en texto libre (p. ej. desconocer tres consumos y pedir bloqueo y devolución).
- **A `lab01_v_a_determinista.py`:** palabras clave en orden fijo, sin LLM. Con dos pedidos en un mensaje gana la primera regla y el resto se pierde sin error.
- **B `lab01_v_b_workflow.py`:** `Agent` de ADK2 sin tools con `output_schema`; un diccionario Python mapea categoría a acción, así que el ruteo sigue siendo determinista.
- **C `lab01_v_c_agente_hitl.py`:** tres tools; solo `bloquear_tarjeta` lleva `require_confirmation=True`. El bloque `[HITL]` indica que quedó esperando aprobación.
- **Opcional `lab01_ej2_investigacion.py`:** plan, búsqueda, evaluación y síntesis con un `while` de Python, para contrastar con C.

## Recomendaciones y advertencias del docente
- [R] Cada nivel de agencia suma latencia, costo e imprevisibilidad.
- [R] En industria regulada: lógica determinista en los pasos regulados y LLM en el resto (EU AI Act, NIST AI RMF, BCRA).

## Preguntas de la clase que vale la pena recordar
- Un alumno preguntó cómo se pone en producción un agente y se consume desde una web o un celular → [T] por la API del servicio publicado, con la capa agéntica detrás; se mencionan canales como Teams y un gateway (parcial).
- Un alumno preguntó si el lab es obligatorio → [T] parece que correr el repo es opcional, pero la última slide indica entrega.
- Debate sobre el rol del arquitecto y AI safety [T, muy dudoso]: agentes que escapan de un sandbox y se coordinan por un canal propio, que coincide con `slides_operacion_encubierta.pdf` [R].

## Anuncios, tareas y material referenciado
- **LAB 01 [R]:** "entrega la próxima clase". El README marca solo `ej2` como opcional.
- **Setup [R]:** `./setup.sh`, `GOOGLE_API_KEY` de Google AI Studio en `.env` (gratuita, con límite; error 429), `./run.sh 1 | 2 | 3 | aside | all`. Fijados `google-adk==2.2.0` y `gemini-2.5-flash`.
- **Material [T]:** ejemplos y material en el GitHub del curso; hay un tutorial de ADK (`ADK_Tutorial0`).
- **Próxima clase [R]:** Módulo 2, componentes del agente (herramientas, memoria, orquestación).
- **Plataforma [T, dudoso]:** consola de GCP y un equivalente en otra nube; en el repo, `GCP_Agent_Platform.pdf` (Build, Scale, Govern, Optimize).
