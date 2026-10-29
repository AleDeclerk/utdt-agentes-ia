# Clase 6 · 13/10 · Memoria y conocimiento: memoria del agente, RAG moderno y grafos de conocimiento

**Docente e invitados:** Matías Zabaljauregui. Sin invitados; varios alumnos aportaron preguntas y experiencias.
**Material del campus:** "Slides Memoria y Conocimiento" (Módulo 6). Repo del curso, carpeta `MODULO_6/LABS` (las demos casi no se mostraron).

## En una frase
Clase conceptual que separa memoria (historial del agente) de conocimiento (hechos externos), sigue la evolución de RAG hasta el RAG agéntico y presenta los grafos de conocimiento como la capa que cubre lo que RAG no resuelve.

## Recorrido de la clase

**[00:00] Apertura y cómo mantenerse actualizado**
- Matías preguntó por los modelos nuevos: seguir la disciplina es responsabilidad del arquitecto.
- Pidió traer novedades al curso para verificarlas juntos y separar señal de ruido.
- Fuentes: LinkedIn (con el sesgo del algoritmo) y blogs en Substack con síntesis semanales; compartirá listas curadas. Propuso anotar 2 o 3 novedades por semana.

**[00:04] Por qué importa la memoria y qué tipos hay**
- La inteligencia se vuelve commodity, pero contexto y memoria siguen siendo el punto crítico: con memoria mal diseñada el agente falla aunque el modelo sea bueno.
- Un LLM solo tiene pesos congelados y la ventana de contexto de esa consulta; la memoria es un "sustrato externo persistente".
- Cuatro tipos: working, episódica, semántica y procedural. La memoria compartida entre agentes ya se vio con el estado de sesión (clave-valor); Kafka, Redis Streams o Pub/Sub vendrán en coordinación.
- Anunció un reporte en el repo sobre cómo ADK 2 implementa las primitivas de memoria.

**[00:26] AgentOps, contexto e ingeniería de memoria**
- Al bucle percibir, razonar, actuar se suma recordar/olvidar. La memoria, junto con evaluaciones y monitoreo, alimenta AgentOps: decidir automáticamente si una versión nueva del agente pasa a producción.
- Un agente sin memoria arranca de cero, repite errores y no acumula confianza (reputación), variable clave también al coordinar agentes.
- Pasado el 50 % de la ventana, el modelo se degrada. De ahí la ingeniería de memoria: cómo se almacena, recupera, consolida y olvida información (hay una arquitectura de referencia de tres capas; no hace falta implementarla entera).
- Próximo módulo, escritura de memoria: few-shot dinámicos (episódica), reflection (working y episódica) y ExpeL (reglas de alto nivel; nombre dudoso en la transcripción).

**[00:26, mismo turno] Memoria vs conocimiento**
- Conocimiento: hechos externos recuperados al generar (documentos, registros, APIs). Memoria: intercambios previos, entradas y salidas de herramientas, cambios de estado.
- Ciclo de vida: escribir (consolidar, no guardar transcripciones completas), leer, actualizar (una política nueva no debe contradecir la vieja) y olvidar (vida útil, decaimiento por desuso, derecho al olvido).
- Cuatro niveles de lectura: FIFO, BM25, vectores y memoria entre sesiones.

**[00:44] RAG: dudas básicas, BM25 y embeddings**
- BM25 evoluciona TF-IDF (frecuencia en el documento por rareza en el corpus). Sirve con códigos, siglas y nombres propios; falla con paráfrasis (vencido vs caducado). Es el ranking por defecto de Elasticsearch y OpenSearch.
- Embeddings: proyectan texto, audio o imágenes a un espacio vectorial donde la cercanía (distancia de coseno) indica similitud semántica.
- Indexación offline (chunking, modelo de embedding, base vectorial). En consulta se usa el mismo modelo, se traen los k vecinos y se inyectan en el prompt.

**[01:06] FAISS y bases vectoriales**
- FAISS es una biblioteca útil para prototipos. Para producción, consultar a infraestructura (concurrencia, recuperación, replicación).

**[01:14] Qué se guarda y RAG avanzado**
- Cada registro guarda texto del chunk, fuente (auditoría), fecha, metadata y ACL. Según el docente, cerca de la mitad de los ataques a sistemas agénticos pasan por la recuperación (inyección indirecta de prompts).
- La búsqueda plana no escala; el índice de Google cuantiza los vectores (nombre no claro en la transcripción).
- Etapas del RAG avanzado: antes de recuperar (reescritura, descomposición, HyDE, ruteo), al recuperar (híbrida, filtros, ACL) y después (reranking).

**[01:23] Fusión y reranking**
- Los scores de coseno y BM25 no se suman: se fusionan por posición con RRF.
- El cross-encoder reordena los candidatos de la primera pasada. Todo cuesta latencia, dinero y tokens.

**[01:29] RAG agéntico**
- El RAG clásico es predecible pero rígido: recupera siempre y no corrige una mala recuperación. El agéntico decide si recuperar, elige herramientas, evalúa la evidencia y reformula en bucle, con menos reproducibilidad y más costo.
- Hay demos con FAISS y con componentes de Vertex, en versión workflow y versión agente.

**[01:37] Experiencias de alumnos**
- Un alumno contó un agente en LangGraph que traduce lenguaje natural a SQL sobre historias clínicas y busca en internet si falla. El docente desaconsejó que el LLM redacte las consultas: mejor tools con consultas fijas.

**[01:45] Grafos de conocimiento**
- Nodos (personas, empresas, cuentas, normas) y relaciones nombradas con verbos, que el LLM lee.
- Resuelven preguntas multi-salto y globales; habilitan algoritmos de grafos y ontologías.
- Neo4j y Cypher; tres capas emergentes: grafo de conocimiento (hechos), de contexto y procedural.

## Conceptos clave
- **Ingeniería de memoria:** diseño de cómo el agente almacena, recupera, consolida y olvida.
- **Ejes de la memoria:** tipo, mecanismo de recuperación y alcance (una sesión o persistente).
- **ACL en RAG:** control de acceso por fragmento, incluso por horario.
- **HyDE:** generar una respuesta hipotética, embeberla y buscar vecinos con ella.
- **Grafo procedural:** pasos a seguir en forma de grafo, alternativa a las Skills.

## Demos y ejemplos mostrados
- Casi no hubo demos. Ejemplo de grafo: armar equipos desde un grafo de personas y habilidades. Neo4j corre con un solo Docker.

## Recomendaciones y advertencias del docente
- Compactar el contexto al llegar al 50 % de la ventana.
- No dejar crecer la memoria episódica sin control.
- Modelar bien el grafo, como un esquema SQL, y etiquetar con cuidado las relaciones.
- Reranking e híbrida son decisiones con costo: evaluarlas con métricas.

## Preguntas de la clase que vale la pena recordar
- ¿RAG enriquece el prompt de entrada o de salida? → De entrada; el modelo no recuerda nada entre llamadas.
- ¿FAISS o una base vectorial? → FAISS para prototipo; en producción faltan replicación, sharding y tolerancia a fallos.
- ¿Se trae el documento entero? → El chunk con metadata, que puede apuntar al original.
- ¿Para qué RAG con 2 millones de tokens? → Un contexto lleno degrada, mete ruido y sale más caro.
- ¿Agente o MCP para ingerir agendas en Word, PDF o PowerPoint a tablas? → Es un flujo conocido: ruteo por tipo de archivo, extracción y validación; LlamaIndex (LlamaParse, LlamaExtract) trae plantillas.

## Anuncios, tareas y material referenciado
- Repo del curso: reporte de memoria en ADK 2 (local y servicios de Google Cloud) y demos, disponibles a pedido.
- Próxima clase: demos de todos los tipos de RAG, Neo4j como grafo y un agente con varias herramientas de recuperación; luego, aprendizaje.
- Un alumno mostrará su búsqueda de sesiones de un congreso (BM25, expansión de términos).
- Herramientas citadas: FAISS, Elasticsearch, OpenSearch, Neo4j, Cypher, Vertex, LlamaIndex, LangGraph, Letta.
- Ninguna tarea formal.
