# Clase 3 · 01/10 · Componentes mínimos de un agente en ADK y primeros ejemplos en `adk web`

**Docente e invitados:** Matías Zabaljauregui (docente). Sin invitados. Unos 17 participantes en Zoom.
**Material del campus:** Mini Tutorial ADK (carpeta `ADK_Tutorial0` del repo del curso). Las slides aún no estaban subidas.

## En una frase

Se presentaron las cuatro piezas mínimas de un agente en Google ADK (Agent, Runner, Session, Model con sus Tools) y se las vio en `adk web` con tres ejemplos de juguete: tool calling, salida estructurada con Pydantic y un pipeline secuencial con estado de sesión compartido.

## Recorrido de la clase

**[00:00] Apertura**
- El docente pidió repasar el repo entre clases, porque la curva se empina pronto.
- Recomendó la documentación oficial de ADK: el framework cambia rápido, sobre todo la forma de implementar workflows en ADK 2 (el curso usa la 2.9, y la 2.10 en algunos ejercicios).
- Un alumno avisó que faltaban las slides en el campus. El docente lo reconoció como error propio.

**[00:07] Ubicación en el ciclo de vida de un agente**
- Mostró la consola de Google Cloud (rebranding de Vertex AI) con Playground, trazas, topología y sesiones, como versión en la nube de lo que se vería en local.
- Recordó los cuatro pilares presentados en Google Next 2026: Build, escalar, gobernanza y seguridad, y optimización.

**[00:12] Las cuatro piezas**
- Agent, Runner, Session y Model (más las Tools). Aclaró que la clase `Agent` solo sirve para instanciar agentes: un agente real surge de todas las piezas juntas.
- Insistió en el enfoque multi-modelo vía LiteLLM, para no depender de un proveedor.

**[00:24] Harness y ruteo**
- Un alumno preguntó qué es el harness; varios compañeros aportaron definiciones y el docente cerró con una analogía.
- Sobre ruteo dinámico: LiteLLM tiene un módulo para eso, pero casi siempre se implementa de forma explícita en el workflow. Quedó para más adelante.

**[00:31] `adk web` y tool calling**
- Presentó `adk web`: selector de agentes, lista de eventos y grafo (llave: tool; rombo: agente).
- Explicó el ciclo de tool calling y mostró el primer ejemplo.

**[00:49] Desvío sobre guardrails**
- Una pregunta fuera de dominio (pedir código Python) abrió una discusión de seguridad (ver Recomendaciones).

**[01:03] Salida estructurada con Pydantic**
- Mostró `output_schema`, `input_schema` y `output_key` con dos agentes encadenados.
- Resolvió dudas sobre la redundancia con el system prompt.

**[01:26] Estado compartido: campaña de marketing**
- Un orquestador ejecuta cinco subagentes en orden sobre la misma sesión.
- Se distinguió entre schemas y claves de estado, y se explicó por qué un flujo secuencial pasa por todos los agentes.

**[01:50] Cierre**
- Adelantó que la próxima clase trata tipos de tools (servidores MCP, agentes como tools).
- Respondió dudas sobre cuándo dividir en subagentes y sobre herramientas low-code.

## Conceptos clave

- **Agent (alias LlmAgent):** modelo + instrucción de sistema + tools. Sin memoria ni estado propios: transforma una conversación en la siguiente respuesta.
- **Runner:** orquestador y "corazón" del framework. Recibe un estímulo (mensaje, umbral de métrica, sensor, planificación tipo cron), ejecuta las tools que el modelo pide y emite eventos. Es un generador asíncrono. Si el código no lo instancia, ADK lo crea.
- **Session:** lista de eventos más un `state` con forma de diccionario clave-valor. Se usó `InMemorySessionService`.
- **Harness:** todo lo que rodea al LLM. El LLM es el cerebro, las tools son músculos y manos, el harness es el sistema nervioso.
- **Tool calling:** el modelo solo decide qué tool conviene; el Runner la ejecuta y devuelve el resultado al modelo.
- **Docstring:** en ADK es la descripción con la que el modelo decide cuándo llamar a la tool. No hace falta decorador: ADK extrae la firma de la función.
- **Pydantic:** valida tipos en ejecución, serializa a JSON y genera esquemas JSON. Se explicó como contrato de entrada y de salida.
- **`output_key`:** clave de `session.state` donde un agente guarda su salida para que otro la lea.
- **Interpolación:** poner esa clave dentro del system prompt del agente siguiente.
- **SequentialAgent, ParallelAgent y agente de bucle:** plantillas de ADK 1. Funcionan, pero se migra a workflows como grafos, similares a LangGraph.

## Demos y ejemplos mostrados

1. **`tools_agent`:** Gemini 2.5 Flash con dos tools: fecha y hora de la máquina, y una API de juguete que devuelve un usuario aleatorio. El grafo se iluminaba evento a evento.
2. **`structured_output`:** `problem_analyzer` emite JSON validado y `advice_generator` lo lee del estado. Ante "no sé qué hacer con mi vida" eligió el perfil Life Coach; ante un tema de finanzas, el de asesor financiero.
3. **`marketing_campaign_agent`:** un `root_agent` (exigido por `adk web`) con cinco subagentes secuenciales e instrucciones en un archivo aparte.

Los otros ejemplos de la carpeta no se mostraron. El docente aclaró que todos son juguetes, sin las garantías de robustez, seguridad y gobernanza de producción.

## Recomendaciones y advertencias del docente

- No confiar en la seguridad del alineamiento del modelo: es probabilística, se rompe con dos o tres preguntas o con ataques multi-turno, y no deja registro del intento.
- Una consulta indebida gasta inferencia cara (denegación económica).
- Poner guardrails deterministas antes y después del LLM, de las tools, de los servicios y entre agentes. Citó Model Armor (Google Cloud), NeMo Guardrails (NVIDIA, open source) y los callbacks de ADK antes y después del modelo. ADK no filtra nada por defecto.
- La implementación ingenua envía en cada llamada el system prompt, el historial y todas las tools; hay caching y compactación.
- Para dividir en subagentes: empezar con un agente, un LLM grande y pocas tools, de forma iterativa y midiendo. Más subagentes dan flexibilidad, pero suman costo y latencia (como monolito contra microservicios).

## Preguntas de la clase que vale la pena recordar

- **¿Las tools pueden ser asíncronas?** → Cualquier función sirve; en ciertas topologías tendrán que serlo.
- **¿Es redundante pedir JSON en el prompt si hay `output_schema`?** → No. El prompt es una sugerencia probabilística (conviene sumar ejemplos few-shot); el schema valida de forma determinista y lanza excepción si la salida no cumple.
- **¿Dónde se declara que los agentes se comunican?** → En la clave compartida del estado; el orden lo fija la plantilla secuencial.
- **¿Hace falta `input_schema` para pasar datos?** → No. Los schemas validan formato; las claves dicen dónde está el dato.
- **¿Un flujo secuencial puede saltear agentes?** → No: es una cadena fijada por quien diseña la topología. La alternativa es que el LLM elija el especialista (dinámico, probabilístico).

## Anuncios, tareas y material referenciado

- Revisar el `README.md` de cada ejemplo de `ADK_Tutorial0` (objetivo, funcionamiento, cómo correrlo).
- Repasar la sección de Python sobre funciones asíncronas.
- El docente subirá las slides al campus.
- Próximo encuentro (el martes siguiente, dicho con duda): tipos de tools, MCP, agentes como tools y búsqueda semántica en listas largas de tools.
- Más adelante: módulo de seguridad, ruteo dinámico y arquetipos (ReAct, Planner-Executor, Actor-Critic, Reflection, Deep Research).
- Plataformas citadas por alumnos: Copilot Studio, IBM watsonx Orchestrate y Dataiku. El docente aclaró que el curso forma criterio de arquitectos y no cubre la adopción con herramientas no-code.
