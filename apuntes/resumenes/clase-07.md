# Clase 7 · 15/10 · GraphRAG con Neo4j: grafos de conocimiento para agentes

**Docente e invitados:** Matías Zabaljauregui. Sin invitados externos (no hubo nadie de Neo4j). La charla base es de un ingeniero cuyo nombre no aparece en la transcripción.
**Material del campus:** "Slides Intro KG - Demo: gestión de talento" (deck de Neo4j sobre GraphRAG; el docente dijo que tiene licencia permisiva).

## En una frase
Se retomó la idea de grafo de conocimiento y se la bajó a tierra con un grafo de talento en Neo4j (Cypher, algoritmos de grafos, embeddings), consumido por un agente de ADK 2 que responde preguntas multi salto que un RAG solo resuelve mal.

## Recorrido de la clase

**[00:00] Apertura y presentación del recurso**
- Invitó a los alumnos a mostrar sus proyectos personales en los 20 minutos posteriores a la clase.
- La clase se armó a partir de una charla didáctica con tres demos; eligió la más simple y la adaptó a ADK 2 (el original estaba en otro framework y en Jupyter).
- Dominio: talento de una organización. Unas 100 personas y 54 skills, datos sintéticos (por eso las comunidades salen con ruido).

**[00:06 a 00:22] RAG frente a grafo y arquitectura de referencia** (tramo largo sin marcas intermedias)
- Un alumno preguntó por qué elegir grafo: con un corpus volátil, insertar entidades sin romper el grafo es más complejo que re-embeber chunks, y ciertos algoritmos de grafos tienen más latencia. Conclusión: combinar ambos.
- Arquitectura de GraphRAG agéntico, leída de abajo hacia arriba: fuentes (no estructuradas y estructuradas; en la demo, CSV), extracción de entidades con un LLM, enriquecimiento con algoritmos, modelos (LLM y embeddings) y agente con tools.
- Tres recuperadores: local (vector más recorrido), de profundidad dinámica (multi salto) y global (temas generales).
- Tesis: si se conocen las preguntas, hasta un grafo simple expone la lógica del dominio y da control y explicabilidad (logs, trazas, auditoría, evals).

**[00:22] Cypher y algoritmos de grafos**
- Nodos son sustantivos del dominio, relaciones son verbos con tipo, y las propiedades pueden ser texto, números, listas o vectores. Las flechas no impiden recorrer en ambos sentidos.
- Cypher: lenguaje declarativo de pattern matching; paréntesis para nodos, corchetes para relaciones.
- Neo4j GDS trae más de 50 algoritmos en 6 familias; los resultados se guardan como propiedades. Se usó Leiden (modularidad) para detectar comunidades.
- Un alumno contó su experiencia con Neo4j en fraude bancario.

**[00:35] Búsqueda híbrida y primera demo**
- Neo4j incluye en el mismo motor búsqueda léxica (BM25) y vectorial: sin sincronizar datos ni vector store aparte.
- Demo en el visualizador (Neo4j en Docker local): 154 nodos, propiedades de cada persona, y una consulta multi salto: personas con las mismas skills de una persona dada y qué otras skills tienen.

**[00:47] Preguntas intermedias**
- Dudas sobre el rol de los embeddings, relación con ciencia de datos, ontologías y cómo convencer a directivos con un ejemplo concreto de negocio.

**[01:02] Enriquecer el grafo**
- Relación nueva entre personas por skills compartidas (overlap de 3 o más), guardada una vez en el grafo.
- Leiden: comunidades definidas por skill común.
- Embeddings (768 dimensiones, de nombre más descripción) y relación de skills semánticamente parecidas, también persistida.

**[01:14] Preparación previa y consulta híbrida**
- Un alumno notó que aquí hay mucho trabajo previo de modelado, a diferencia de la inferencia "mágica" de otros ejemplos. El docente coincidió y dijo que a cambio hay más determinismo.
- Consulta con puntaje léxico más semántico y máximo de saltos: halló un vínculo entre dos personas a través de una tercera skill (JavaScript), casi imposible con RAG.

**[01:24] Agente reclutador en ADK 2 [01:34 demo]**
- Tools son funciones Python que ejecutan consultas Cypher fijas; el modelo solo elige herramienta y argumentos.
- Siete preguntas en `adk web` (ver Demos).

**[01:42] Código y preguntas finales**
- Recorrido rápido del código (prompt de sistema, tope de llamadas, construcción del grafo, tools), y charla abierta sobre roles, gobernanza y herramientas de Google.

## Conceptos clave
- **Grafo de conocimiento:** patrón para organizar datos relacionados, con nodos (entidades), relaciones (verbos con tipo) y propiedades.
- **Pregunta multi salto (multi-hop):** exige encadenar entidades indirectas; cada salto crece de forma exponencial en costo.
- **Detección de comunidades (Leiden):** agrupa nodos por mayor densidad de relaciones y guarda el id como propiedad.
- **Similitud estructural, semántica y combinada:** por conexiones del grafo, por cercanía de embeddings, y ambas en una consulta.
- **Recuperadores local, de profundidad dinámica y global:** los tres tipos de retrieval de la arquitectura de referencia.
- **Ontología:** con la correcta, el grafo da garantías lógicas no probabilísticas; la demo usa solo constraints.

## Demos y ejemplos mostrados
- Visualizador de Neo4j: personas, skills y similitud por solapamiento.
- Siete preguntas al agente: skills de una persona; skills parecidas a Power BI y data visualization (Tableau, Data Analytics); personas parecidas a una dada; quién sabe Python y AWS; reemplazo de una persona que se va (con sus skills extra); armar equipo y quién sabe ciberseguridad (dos tools); conversación de tres turnos con memoria de la sesión.
- Se observó qué tool invocaba el agente en el stream de eventos.
- No se llegó a mostrar el agente que decide si el RAG alcanza y, si no, consulta el grafo.

## Recomendaciones y advertencias del docente
- El LLM no debería redactar Cypher (ni SQL): las queries van fijas dentro de las tools. Un alumno lo cuestionó, citando que los asistentes de código sí escriben código. El docente dijo que los agentes alucinan en estas consultas, que es un problema documentado, y quedó pendiente retomarlo.
- Cada vez que cambia el grafo hay que volver a correr algoritmos como Leiden.
- Los verbos de las relaciones los elige uno y pesan, porque el LLM los lee.
- Siempre poner un tope de llamadas al agente.
- Los datos de la demo son sintéticos: no leerlos como una organización real.
- Hace falta equipo interdisciplinario (gobernanza, negocio, seguridad) y un sponsor de negocio.

## Preguntas de la clase que vale la pena recordar
- ¿Por qué grafo y no solo RAG? → El grafo da determinismo y explicabilidad, pero cuesta más mantenerlo; lo ideal es combinar ambos.
- ¿Las tools son un wrapper de Cypher? → Sí.
- ¿Cómo se valida un grafo armado por extracción automática? → Con revisión de analistas de negocio; el docente no tiene respuesta cerrada y dijo que es experimental.
- ¿Los ejemplos de memoria de la clase anterior están en el repo? → No estaban; el docente los sube.

## Anuncios, tareas y material referenciado
- No hubo tareas ni fechas de entrega.
- El docente subirá lo que falta al repo (ejemplos de memoria de ADK 2 de la clase anterior), buscará ejemplos de grafos de contexto y procedimentales, y revisará si Elasticsearch tiene servidor MCP.
- Slides en el campus; código de la demo en el repo del curso (`MODULO_6/DemoTalent_Neo4j`, según el repo).
- Una iniciativa de Google Cloud que descubre la semántica del negocio y arma grafos (nombre dudoso en la transcripción).
- Próximo módulo: aprendizaje (qué recuerda, olvida y reutiliza un agente).
