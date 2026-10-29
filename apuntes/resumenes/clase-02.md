# Clase 2 · 29/09 · Diseño de sistemas agénticos: primer agente en ADK

**Docente e invitados:** Matías Zabaljauregui. Sin invitados; hubo mucha participación de alumnos.
**Material del campus:** "Slides Módulo 2" (más los labs de `MODULO_2` en el repo del curso).

*Los [hh:mm] son aproximados: la transcripción solo marca el inicio de sus tramos (00:05 y 01:25) y el resto se estimó por posición.*

## En una frase
Se recorrieron los componentes de un agente (modelo, tools, memoria, RAG, orquestación), los criterios para elegir modelo y los trade-offs de arquitectura, y se cerró con tres labs en Google ADK sobre una mesa de reclamos: tools, costo y routing dinámico.

## Recorrido de la clase

**[00:05] Cierre del tema anterior y mapa del curso**
- La psicofancia (complacencia del modelo) viene del reinforcement learning de la última etapa de entrenamiento, orientado a calibración: el modelo da un nivel de confianza, que es la probabilidad normalizada. Un alumno lo usa para derivar a un revisor humano bajo un umbral.
- Alcance: no es un curso de ingeniería. No se ve la matemática de los embeddings; se estudia qué problema resuelve cada componente, cómo se combina y qué trade-offs trae (latencia, seguridad, robustez, costo, precisión).
- Los módulos mapean a un diagrama del curso; hoy se arma el primer agente sin exigir entenderlo todo.

**[00:13] Logística y labs**
- Slides en el campus y en el repo de GitHub; los labs son opcionales para perfiles no técnicos.
- Se recomienda la API key gratuita de Google AI Studio. Su cuota diaria es baja y varios alumnos vieron errores o cortes en el lab 3. Alternativa: OpenRouter, agregador con algunos modelos gratuitos.

**[00:19] Principios y componentes**
- Diseñar sistemas agénticos retoma la ingeniería de software distribuido (composición, tolerancia a fallos, escalabilidad), ahora con un componente probabilístico.
- El orden es deliberado: fundamentos antes que diseño y producción, para no optimizar lo que no se entiende.
- Los alumnos ayudaron a definir modelo, tools, memoria, RAG y orquestación.

**[00:34] El LLM y lo que lo rodea**
- Llamar a la API de OpenAI o Claude no es acceder solo al LLM: hay un sistema alrededor. El modelo se basa en transformers (paper de Google de 2017).
- Flujo predefinido contra agente que razona, actúa y vuelve a razonar (arquetipo ReAct).

**[00:41] Cómo empezar y elegir modelo**
- Agente acotado, prueba de concepto chica, iteraciones con datos reales y KPIs medibles desde el día 1. Sin objetivo claro aparece reward hacking (se verá luego).
- Criterios: entropía de salida, modalidad, abierto o cerrado, fine-tuning o preentrenado, routing dinámico.
- Modalidad: los modelos nativos multimodales meten audio e imagen como tokens en el mismo espacio vectorial, sin speech-to-text previo.

**[00:56] Routing y on-premise**
- El routing dinámico es práctica estándar: las arquitecturas serán multimodelo.
- Un alumno preguntó si es común adaptar un harness (como el SDK de agentes de OpenAI) on-premise. Respuesta: es buena opción; en bancos los intentos chocaron con normativa, gobernanza y gestión del cambio.

**[01:07] Benchmarks y trade-offs**
- Más billones de parámetros suele dar más capacidad, pero exige más VRAM.
- Cuatro ejes correlacionados: precisión/latencia, escalabilidad (infraestructura elástica), robustez/redundancia (fallan APIs, modelos y tools; hacen falta feedback loops y monitoreo) y costo (lo dará un colega economista).

**[01:12] Primitivas de ADK, tools y memoria**
- `timeout`: si el agente no responde a tiempo, lanza excepción.
- Callbacks (por ejemplo `on_model_error_callback`): funciones que corren antes o después de llamar a un modelo, tool o agente; sirven para fallbacks.
- Reintentos: intentos máximos, delay inicial y factor de backoff (1 s, 2 s, 4 s).
- Tools: MCP ("interoperabilidad vertical"), funciones Python, comandos locales, bases de datos y APIs.
- Memoria corta: sesión en RAM con el historial de eventos, acotada por la ventana de contexto (de 4096 tokens a 1 o 2 millones).

**[01:27] Orquestación y labs**
- `SequentialAgent`: nombre y lista de subagentes; la salida de uno es la entrada del siguiente. También `ParallelAgent` y `LoopAgent`, en transición hacia un modelo de grafos.
- Cada lab trae su consigna arriba; probado en Linux y Mac, no en Windows.
- Siguieron el lab 1, la demo de dos modelos y el lab 3 (ver demos).

## Conceptos clave
- **Foundation model:** el "cerebro" que entiende lenguaje natural. Definirlo como predictor del próximo token ya es obsoleto: genera pasos intermedios. Hay que acotarlo con determinismo y límites.
- **Tool:** capacidad de actuar sobre el mundo; separa IA generativa de agéntica.
- **Agentic RAG:** el RAG es ya un agente que combina técnicas de recuperación; actualiza al agente sin reentrenar.
- **Orquestación:** quién decide el próximo paso, qué contexto se comparte y cuándo parar o pedir human-in-the-loop.
- **Entropía de salida:** cuanto menos predecible la respuesta correcta, más modelo hace falta; en clasificación binaria alcanza uno chico, o ni LLM.
- **`output_key`:** guarda la respuesta del agente en la sesión (un diccionario) para que otro agente la lea.
- **Lost in the middle:** el modelo pierde precisión con lo que está en el centro del contexto.
- **Traffic mix:** el ahorro del routing depende de la distribución de complejidad y del share de tokens.

## Demos y ejemplos mostrados
- **Lab 1 (`ejercicio_1_agente_reclamos.py`):** tres funciones de negocio deterministas como tools, system prompt preciso y un set de casos con clientes enojados. El LLM elige qué tool llamar; los reclamos sobre cierto monto van a un humano.
- **Dos modelos:** misma query en `gemini-2.5-flash-lite` y `gemini-2.5-pro`: casi 14 veces más costo. En la simple responden igual; en la compleja solo el caro acierta en contenido y tono.
- **Lab 3:** un agente clasificador devuelve JSON (salida estructurada) con la complejidad y se invoca el modelo correspondiente. Acertó 100 % porque el dataset es sintético y con etiquetas conocidas.

## Recomendaciones y advertencias del docente
- Empezar con un modelo grande como techo de calidad y optimizar después.
- Medir si el costo fijo del clasificador se justifica y cuánto cuesta un falso positivo o negativo del router.
- El costo en tokens puede bloquear un proyecto: 800 personas con 10 mensajes suman cientos de dólares.
- Si el agente itera, su contexto crece sin límite: hay que gestionarlo.
- Los modelos chicos suelen llamar mal a las tools; los guardrails validan parámetros antes de ejecutarlas.
- No escribir este código a mano: se lo pide a un asistente de código.

## Preguntas de la clase que vale la pena recordar
- ¿Conviene optimizar el modelo ya en el MVP? → No: arrancar con uno potente y bajar después.
- ¿Los agentes comparten sesión? → Depende: a veces sí y a veces se aísla (gestión de contexto).
- ¿Qué dispara al agente de reclamos? → Es un único turno con datos fijos; solo ilustra que el LLM elige una función.
- ¿Cómo detectar fugas de tokens? → Context engineering, modelo juez, evals, routing y caching.
- ¿Cómo se midió el 100 % del router? → Con datos sintéticos etiquetados; precision y recall se ven más adelante.

## Anuncios, tareas y material referenciado
- Sin entregas ni fechas.
- Labs opcionales en `MODULO_2/labs` (`setup.sh`, `check.sh`, `run.sh`).
- OpenRouter (openrouter.ai), servicio de memoria Honcho, paper de transformers (2017).
- El docente ofreció sumar al módulo de orquestación el tema de routers abiertos que mencionaron alumnos.
