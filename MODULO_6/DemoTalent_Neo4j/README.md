# Demo de talento: GraphRAG con Neo4j y un agente de ADK 2 · Módulo 6 · Arquitectura de Agentes IA · UTDT 2026

La demo que vimos en clase, para correr en tu máquina: un **grafo de conocimiento de talento** en Neo4j (personas, skills,
similitudes, embeddings y comunidades) y un **agente de ADK 2** que lo consulta con herramientas. Usa Gemini con una
**API key gratuita de Google AI Studio** y un Neo4j local en Docker.

- **Módulo 1:** del CSV al grafo. `Person`/`Skill`/`KNOWS`, skills compartidas (`SIMILAR_SKILLSET`), embeddings de las skills con un
  índice vectorial, skills parecidas por significado (`SIMILAR_SEMANTIC`) y comunidades con el algoritmo de Leiden.
- **Módulo 2:** un agente ReAct con cuatro herramientas de lectura sobre el grafo.

**Para seguir el recorrido de la clase paso a paso, usá [`guia_demo_KG.md`](guia_demo_KG.md)** (19 pasos, con las consultas para copiar al visualizador de Neo4j).

## Qué necesitás

| | |
|---|---|
| **Docker** | Corre el Neo4j de la demo. La imagen oficial pesa ~1,1 GB y el contenedor usa ~1,2 GB de RAM. |
| **Python 3.10 a 3.13** y bash | Se probó con 3.12 en Linux (en 3.10, 3.11 y 3.13 las dependencias se instalan e importan, pero no se corrió la demo completa). El venv ocupa ~430 MB. |
| **API key de Google AI Studio** | Gratis en <https://aistudio.google.com/apikey>. Se usa para los embeddings y para el modelo del agente. |
| **Conexión a internet** | Para bajar la imagen de Docker, las dependencias, los datos (una vez) y para llamar a Gemini. |

## Puesta en marcha

```bash
cd MODULO_6/DemoTalent_Neo4j
./setup.sh          # crea .venv, instala dependencias y arma .env a partir de .env.example
# abrí .env y pegá tu GOOGLE_API_KEY
./run.sh up         # levanta el Neo4j de la demo (navegador: http://localhost:7475, bolt: 7688)
./run.sh check      # verifica todo, incluida tu clave (2 llamadas mínimas a Gemini)
./run.sh 01         # módulo 1: baja los datos y construye el grafo (unos segundos)
./run.sh 02         # módulo 2: corre las 7 preguntas del agente por consola
./run.sh 03         # (opcional) apéndice: extrae 2 personas de biografías con Gemini y las suma al grafo
./run.sh web        # el agente en el navegador: http://localhost:8000 (elegí «reclutador»; otro puerto: TALENT_WEB_PORT=8010 ./run.sh web)
```

Otros comandos: `./run.sh down` (apaga Neo4j y conserva el grafo), `./run.sh reset` (lo apaga y **borra** el grafo),
`./run.sh calibrar` (imprime los puntajes de similitud con los que se eligieron los umbrales), `./run.sh all` (01 y 02).
`./run.sh 02 --repeticiones 3` repite cada pregunta 3 veces para ver cuánto varía el agente (son 21 corridas: con la capa gratuita
puede chocar con el límite por minuto; el script espera y reintenta).

## Qué se instala en tu máquina y qué no está en este repositorio

Este repositorio tiene solo el **código**. Nada de lo siguiente se publica; todo se genera en tu máquina a partir de él:

- **La imagen de Docker.** No hay ninguna imagen propia: `docker-compose.yml` usa la imagen oficial `neo4j:2026.09.0-community`, que Docker baja
  de Docker Hub la primera vez. Los plugins GDS (algoritmos de grafos) y APOC vienen incluidos y se activan con `NEO4J_PLUGINS`.
- **El grafo.** `./run.sh 01` lo construye desde cero en un volumen de Docker propio de esta demo (`demotalent_neo4j_neo4j_demotalent_data`).
  Es idempotente: podés repetirlo. `./run.sh reset` borra el volumen.
- **Los datos.** `./run.sh datos` (lo llama `./run.sh 01`) baja a `datos/` las personas y las descripciones de las skills desde el repositorio de
  origen, de una versión fija y verificando su hash. Ver *Créditos y datos* más abajo.
- **Los embeddings.** Se calculan con la API de Gemini y se guardan en `.cache/`; si repetís la corrida no vuelven a pagarse.
- **El entorno de Python** (`.venv/`) y tu `.env` (con tu clave): están en `.gitignore`.

## Qué hay en la carpeta

| Archivo | Qué hace |
|---|---|
| `guia_demo_KG.md` | La guía del recorrido completo, paso a paso |
| `setup.sh`, `run.sh`, `verificar.py` | Instalación, comandos de la demo y verificación |
| `docker-compose.yml` | El Neo4j de la demo (imagen oficial, solo accesible desde tu máquina) |
| `descargar_datos.py` | Baja los datos de origen a `datos/` |
| `01_grafo.py`, `grafo_talento.py` | Módulo 1: CSV → grafo, similitudes, embeddings, índice vectorial, Leiden. Idempotente |
| `herramientas.py`, `agente.py`, `agentes/reclutador/` | Módulo 2: las 4 herramientas y el agente de ADK 2 (`adk web` carga `agentes/reclutador/agent.py`) |
| `02_agente.py` | Módulo 2 en modo script: 7 preguntas, verificación de las herramientas usadas y auditoría de nombres |
| `03_extraccion.py` | **Apéndice opcional** (no forma parte del recorrido de la guía): de texto libre a grafo. 2 biografías → Gemini con salida estructurada (Pydantic) → grafo. Suma 2 personas (102); para volver a las 100 de la guía: `./run.sh reset`, `./run.sh up`, `./run.sh 01` |
| `comun.py`, `adk_util.py` | Conexión a Neo4j, embeddings con caché, umbrales; y el ejecutor de agentes del script |

## El agente (arquetipo ReAct)

Un `Agent` con cuatro function tools: `habilidades_de_persona`, `habilidades_similares`, `personas_similares`,
`personas_con_habilidades`. **El modelo elige herramienta y argumentos; el código fija todo lo demás:**

- el Cypher son plantillas fijas con parámetros: el modelo nunca escribe Cypher;
- todas las herramientas son de solo lectura (sesión `READ_ACCESS`);
- topes en las herramientas: 5 skills por consulta, 10 resultados;
- tope de **6 llamadas al modelo** como `before_model_callback`: al agotarse el usuario recibe un mensaje, no una excepción
  (con `RunConfig.max_llm_calls` sería una excepción, y por defecto vale 500);
- un fallo de herramienta se devuelve como `{"error": ...}` en vez de lanzar una excepción;
- los nombres de persona se comparan sin distinguir mayúsculas y, si no existe, la herramienta devuelve sugerencias.

## Decisiones de diseño que se pueden corregir

1. **Índice vectorial nativo de Neo4j, no FAISS.** La búsqueda vectorial y el recorrido del grafo se hacen en la misma consulta, que es el punto de GraphRAG.
2. **Leiden con GDS y relaciones semánticas con APOC.** `gds.graph.project` + `gds.leiden.write` (`gamma` 1,5, `theta` 0,001, `maxLevels` 100,
   `concurrency` 1, semilla 42, pesos = `overlap`) y `apoc.periodic.iterate` para `SIMILAR_SEMANTIC`. Los ids de comunidad que escribe GDS son arbitrarios;
   después se **renumeran 0 a n-1** (la más grande primero) para que las consultas y la guía sean legibles. El cliente es `graphdatascience==1.22` (la 2.x cambió la API).
3. **Sin nodos `Community`.** La comunidad es solo la propiedad `Person.leiden_community`. (El visualizador colorea por etiqueta, no por el valor de una propiedad,
   así que las comunidades se miran de a una.)
4. **Embeddings de Gemini (`gemini-embedding-001`, 768 dimensiones, tipo de tarea `SEMANTIC_SIMILARITY`)**, calculados sobre `"<skill>. <descripción>"`.
   El texto incluye el nombre de la skill: con nombres cortos como `R` o `AWS` la descripción sola da muy poca información.
5. **Constraints `IS UNIQUE`**, no `NODE KEY` (esta última es de la edición Enterprise).
6. **Sin comparación contra una línea base solo-vectorial** y sin Text2Cypher: el agente usa herramientas con recorridos fijos.

### Umbrales de similitud (elegidos a ojo, sin métrica)

El score de Neo4j es `(1 + coseno) / 2`, y con `gemini-embedding-001` los scores entre skills quedan concentrados entre 0,86 y 0,96, por eso los umbrales son altos:

- **Skill ↔ skill (`SIMILAR_SEMANTIC`): 0,94.** Da unas 25 relaciones, como `Agile~Scrum`, `AWS~Azure`, `Docker~Kubernetes`, `Power BI~Tableau`. Siguen apareciendo relaciones discutibles
  (`Python~Ruby`, `Express.js~Flask`).
- **Texto libre → skill: 0,895**, hasta 3 skills por término. `API coding` trae API Design; un saludo no trae ninguna skill.

Se compararon dos configuraciones sobre ~25 pares que elegimos a mano (16 «sensatos», como `Agile~Scrum` o `Docker~Kubernetes`, y 9 «dudosos», como `Security~Testing`). Con `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`,
`Security~Linux` y `Security~Testing` puntuaban más alto que varios pares sensatos (por ejemplo `HTML5~JavaScript` o `PyTorch~TensorFlow`); con `SEMANTIC_SIMILARITY` en ambos lados los cuatro pares de `Security` que probamos
(con `Linux`, `Testing`, `Big Data` y `Project Management`) quedaron por debajo de los 16 sensatos, y por eso se eligió esa. Es un criterio a ojo sobre una muestra chica, no una evaluación. No hay un conjunto de evaluación:
**si cambiás el modelo o el tipo de tarea de los embeddings, hay que repetir la calibración** (`./run.sh calibrar`) y reconstruir el grafo (`./run.sh reset`, `./run.sh up`, `./run.sh 01`).

## Qué se verificó y qué no

**Verificado (2026-10-19, Linux, Python 3.12, Docker 29, ADK 2.10.0, Neo4j 2026.09.0 Community):**
- Reconstrucción **desde un volumen vacío**: 100 personas, 54 skills, 400 `KNOWS`, 1319 `SIMILAR_SKILLSET`, 25 `SIMILAR_SEMANTIC`, 9 comunidades con GDS (16, 15, 13, 11, 11, 9, 9, 9, 7), índice `ONLINE`.
  Correr el módulo 1 dos veces da los mismos conteos. Las 1319 relaciones y las 9 comunidades no dependen de los embeddings: son las mismas en cada reconstrucción.
- Los datos que baja `descargar_datos.py` son idénticos (contenido) a los usados en clase.
- Agente: **21 de 21 corridas** (7 preguntas × 3) usaron las herramientas esperadas y 0 de 21 nombraron personas sin respaldo en las herramientas, con `gemini-2.5-flash` y también con `gemini-3.8-flash`.
  La conversación de tres turnos de la guía (skills relacionadas → quién las sabe → parecidos de esas personas) encadenó las herramientas esperadas en 5 de 5 corridas.
- `03_extraccion.py` (apéndice) es la versión adaptada a AI Studio del script que se probó en clase; **la versión adaptada no se corrió**, solo se revisó de forma estática.
- Las 45 consultas de `guia_demo_KG.md` se ejecutaron contra la base y devuelven filas, y 22 cifras citadas en la guía se verificaron contra la base. **No se abrió el visualizador de Neo4j** para comprobar cómo se dibuja cada consulta.

**No verificado / límites:**
- **No se probó con una clave de AI Studio recién creada.** Las corridas usaron los mismos modelos de Gemini (`gemini-embedding-001`, `gemini-2.5-flash`, `gemini-3.8-flash`) a través de otro endpoint de Google. Con una clave
  gratuita nueva, Google puede restringir el acceso a algunos modelos 2.5 (y la capa gratuita tiene límite de pedidos por minuto y por día): si pasa, `./run.sh check` te lo dice y podés poner otro modelo en `DEMO_MODEL` (ver `.env.example`).
- Solo se probó en **Linux** con Python 3.12. No se probó en macOS ni en Windows/WSL.
- Son **3 repeticiones por pregunta**: no es una tasa de aciertos. Gemini puede variar entre corridas, y a veces el agente responde distinto a lo que muestra la guía.
- La auditoría de `02_agente.py` **solo mira nombres de personas**, no nombres de skills ni afirmaciones («tiene 3 skills en común»).
- Las comunidades de Leiden agrupan por **una skill compartida**, no por perfil profesional (System Design, Agile, Security, Testing, Scrum, Blockchain, Project Management, API Design y HTML5; ver el paso 1.9 de la guía).
  Con estos datos aleatorios no hay perfiles que recuperar. No se hizo un control contra el azar de la modularidad.
- Los puntajes semánticos pueden variar en la tercera cifra decimal; una relación que cae justo en el umbral puede aparecer o no.
- No se midió el costo en tokens. Es pequeño (54 descripciones, unas pocas consultas de embeddings con caché, y unos miles de tokens de Gemini por pregunta).

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `Docker no está instalado o no está corriendo` | Instalá/iniciá Docker y repetí `./run.sh up`. |
| `port is already allocated` | Otro programa usa 7475 o 7688. Poné `TALENT_HTTP_PORT` y/o `TALENT_BOLT_PORT` en `.env` y repetí `./run.sh up` (la guía y el visualizador usan esos puertos). |
| `address already in use` al correr `./run.sh web` | El puerto 8000 está ocupado: `TALENT_WEB_PORT=8010 ./run.sh web`. |
| `La API key no es válida` | Revisá `GOOGLE_API_KEY` en `.env` (sin comillas ni espacios). |
| `Tu clave no pudo usar el modelo …` | Probá otro modelo de Gemini con `DEMO_MODEL=...` en `.env`. |
| `[429] …: reintento en Ns` | Límite de pedidos por minuto de la capa gratuita: el script espera y reintenta. Si se acaba la cuota diaria, probá más tarde. |
| `Neo4j responde pero faltan los plugins GDS/APOC` | `./run.sh reset`, `./run.sh up`: el contenedor tiene que arrancar con `NEO4J_PLUGINS` del compose. |
| Cambiaste `TALENT_NEO4J_PASSWORD` y no conecta | La clave solo se aplica al crear el volumen: `./run.sh reset` y de nuevo `./run.sh up`. |
| No se pueden bajar los datos | Revisá tu conexión y repetí `./run.sh datos`. |

## Créditos y datos

La demo es una adaptación a ADK 2, Gemini y un Neo4j local del workshop *Talent GraphRAG* de Neo4j
(<https://github.com/neo4j-product-examples/genai-workshop/tree/main/talent>, charla *Intro to GraphRAG* en
<https://ai.engineer/talks/J-9EbJBxcbg-intro-graphrag>). El original usa OpenAI, LangGraph y Neo4j Aura.

**Los datos (personas y descripciones de las skills, sintéticos) son de ese repositorio, que no declara una licencia.** Por eso este repositorio **no los redistribuye**:
`descargar_datos.py` los baja a tu máquina, de un commit fijo (`e9ecdf3`) y comprobando su sha256, para que los uses en el curso. Si querés reutilizarlos fuera del curso, consultá primero con sus autores.
