# Clase 5 · 08/10 · Orquestación y los 6 arquetipos agénticos

**Docente e invitados:** Matías Zabaljauregui (docente).
**Material del campus:** "Slides Orquestación - 6 Arquetipos Agénticos", "Slides - 3 casos que combinan arquetipos" y "Slides - Jev y posibles usos (borrador)". En el repo: `MODULO_5/LABS` (`01_onboarding_crediticio`, `02_incidencias_soc`, `03_auditoria_licitaciones`, `run_ejemplo.sh`).

## En una frase

Se presentaron seis arquetipos de orquestación (Reflex, ReAct, Planner-Executor, Query Decomposition, Reflection, Deep Research) como patrones ideales, ordenados por autonomía, que se comparan con tres preguntas: quién decide el siguiente paso, qué contexto se comparte y cuándo termina la ejecución.

## Recorrido de la clase

**[00:00] Apertura y las tres preguntas**
- Arranca el módulo 5, que integra los componentes vistos antes. Los slides de Jev no se alcanzaron a ver.
- Control de ejecución: en código es determinista, auditable y testeable, pero solo cubre lo que una persona previó. En el modelo el flujo emerge, es flexible y difícil de auditar.
- Condición de stop: evitar bucles infinitos y saber cuándo hay información suficiente no es trivial.

**[00:22] Contexto compartido**
- El modelo no guarda estado: lo que no está en la ventana no existe. Cuatro formas de compartir contexto: historial completo, artefacto explícito, resúmenes o notas, y contexto aislado.
- El historial completo da coherencia, pero crece, encarece y degrada la precisión.
- Un artefacto explícito (plan, borrador, JSON, imagen) se puede inspeccionar, útil para auditoría.

**[00:34] Mapa de los arquetipos**
- Cada arquetipo combina de otra forma razonar, planificar y actuar; el framework, no el LLM, ejecuta la herramienta.
- [00:42] Ordenados de izquierda a derecha hay más autonomía y adaptabilidad, pero también más latencia, menos previsibilidad y más costo.

**[00:46] Reflex, ReAct, Planner-Executor y Query Decomposition**
- Reflex: una sola pasada, sin bucle ni estado (regla, tabla o una llamada a un modelo). Ejemplo: un banco que enruta mensajes a tarjetas, préstamos o fraude. Falla en silencio si la entrada no trae la información.
- ReAct: ciclo razonar, actuar y observar con un contexto único que crece; el LLM decide cuándo terminar. Es el más flexible y el más caro. Si el grafo ya se puede dibujar, no conviene dejarlo al LLM.
- Planner-Executor: un LLM arma un plan (artefacto con pasos y dependencias, revisable por un validador o una persona) y un ejecutor determinista lo corre, con fan-out si los pasos son independientes. En su versión básica no replanifica.
- Query Decomposition: divide una consigna compuesta en subpreguntas, en paralelo o en secuencia (Self-Ask), con contexto aislado por subpregunta y una síntesis final.

**[01:15] Reflection**
- Un generador y un crítico: el borrador pasa por un lazo de verificación, y las críticas se conservan entre rondas.
- El crítico usa rúbrica y señales externas para no ser complaciente ni estricto de más. El código fija el tope de rondas.
- Es muy usado en RAG, que se verá en el módulo siguiente.

**[01:25] Deep Research**
- Plan de investigación, investigadores en paralelo con contexto aislado, hallazgos en un bloc de notas, evaluación de brechas y nuevas rondas hasta un límite de rondas, tokens o tiempo.
- El modelo decide la profundidad de recursión; los investigadores devuelven hallazgos condensados, no el detalle completo. Es el más ambicioso y el más costoso.

**[01:35] Composición y criterios de elección**
- Escalamiento: Reflex enruta, lo ambiguo va a ReAct y lo riesgoso pasa por Reflection.
- Anidamiento: un Deep Research propio, armado con Planner-Executor, subpreguntas en paralelo, ReAct y Reflection.
- Criterios: ¿alcanza una pasada? Reflex. ¿Se parte en subpreguntas? Query Decomposition. ¿Se conocen los pasos y conviene aprobarlos? Planner-Executor. ¿Pregunta abierta que justifica el costo? Deep Research o ReAct.

**[01:44] ADK 2 y casos de negocio**
- Primitivas nuevas de ADK 2: workflow en grafo, workflow dinámico y workflow colaborativo. Las plantillas Sequential, Parallel y Loop siguen andando pero están deprecadas (nombres con transcripción dudosa).
- [01:54] Tres casos creados para el curso; no se llegó a mostrar el código.

## Conceptos clave

- **Arquetipo:** modelo ideal de orquestación, como un patrón de diseño. Sirve para compartir terminología; en la práctica se adapta y se compone.
- **Contexto aislado:** dividir el contexto del orquestador entre especialistas. Evita contaminación entre subagentes, ruido y gasto de tokens.
- **Jev:** tipo de modelo (nombre según el campus; en la transcripción aparece de varias formas) con salidas tipadas y probabilidad calibrada. Reemplaza llamadas a LLMs pequeños con fine-tuning en ruteo y selección de herramientas. Hay alternativas open source.

## Demos y ejemplos mostrados

- **Ejemplo 1, onboarding crediticio:** requisitos de respuesta rápida, reglas de rechazo uniformes y explicabilidad. Un Reflex hace la validación rápida, se lanzan tres herramientas en paralelo y un router, según la complejidad, dispara un Planner-Executor.
- **Ejemplo 2, incidencias de seguridad (SOC):** ReAct, human-in-the-loop y un enjambre (workflow colaborativo de ADK) con especialistas invocados dinámicamente, sin aristas previas.
- **Ejemplo 3, auditoría de licitaciones:** un Deep Research propio. Corrió en vivo con un script (se le pasa el número de ejemplo): investigadores de dos niveles en paralelo y un sintetizador final.

## Recomendaciones y advertencias del docente

- Empezar por el arquetipo más simple y moverse a la derecha solo si hace falta (si el grafo ya se puede dibujar, no usar ReAct).
- Seguir de cerca a Jev, la gran novedad de 2026 según el docente.
- Los ejemplos son pedagógicos, no las soluciones más eficientes.

## Preguntas de la clase que vale la pena recordar

- Un alumno preguntó si se puede evitar que el asistente busque en Google cuando no encuentra una tabla interna. → Sí. En el módulo de memoria y conocimiento (RAG) se define el fallback: corpus, búsqueda semántica, grafo y recién después internet. Es control híbrido: el modelo decide en tramos acotados y el código pone límites.
- ¿Cómo evitar el acoplamiento entre agentes y testearlos por separado? → Arrancar con un solo agente. En Deep Research los subagentes son llamadas recursivas al mismo agente, con tope de profundidad, y se testean inyectando un contexto.
- Un alumno planteó que Reflection debería ser razonar, actuar y evaluar. → Hay solapamientos; los arquetipos son terminología compartida, no piezas puras.
- Un alumno notó que faltaba human-in-the-loop en el diagrama de Deep Research. → Falta en todos los diagramas por simplificación; tiene su propio módulo.
- ¿Cuánto cuesta Deep Research? → Depende de la implementación; es probablemente de los más caros. Un mal diseño dispara el gasto. El docente intenta conseguir que un colega dé una clase de FinOps.

## Anuncios, tareas y material referenciado

- **Tarea:** explorar el ejemplo 1 antes del próximo encuentro (problema, solución, por qué esas palabras clave llevan a esa arquitectura) y consultar dudas.
- Leer en los slides las secciones "fallas típicas" y "cuándo elegirlo".
- El docente subirá al repo todo el material pendiente al día siguiente.
- Skill de Claude Code en construcción que genera arquetipos con ADK 2; se aceptan contribuciones.
- Paper de ReAct (Yao et al., 2022); reporte del docente sobre las primitivas de ADK 2.
- Módulos que vienen: evaluaciones, memoria y conocimiento (RAG), aprendizaje y human-in-the-loop.
- Un alumno ofreció compartir libros (uno de O'Reilly, transcripción dudosa) en una carpeta de Drive.
