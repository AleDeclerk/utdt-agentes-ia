# Labs Módulo 6 — Conocimiento y memoria · Arquitectura de Agentes IA · UTDT 2026

Ejemplos del Módulo 6 para correr en tu máquina: **RAG**, **GraphRAG**, **Agentic RAG** y **memoria con ADK**.
Los de retrieval y GraphRAG en memoria no necesitan ninguna cuenta; los que llaman a Gemini usan una API key
gratuita de Google AI Studio.

## El caso

Un asistente de normativa interna para oficiales de cuentas de una entidad financiera. El corpus son 8
fragmentos de normas (`norm_001` a `norm_008`) y un grafo de 8 hechos sobre un grupo económico (Textil Norte S.A.).
**Todo es sintético**: normas, clientes y montos son inventados a propósito; no usar como referencia regulatoria.

## Qué hay

| Script | Tema | Qué muestra | API key |
|---|---|---|---|
| `rag_pipeline.py` | RAG | Embeddings locales + FAISS: el retrieval devuelve scores que engañan | no |
| `comparar_metodos.py` (+ `hybrid.py`) | RAG | BM25 vs. semántico vs. híbrido: pregunta por pregunta, agregado y barrido de `alpha` | no |
| `ejercicio_1e_rag_generacion.py` | RAG | RAG completo: recuperar, armar el prompt y generar con Gemini | sí |
| `ejercicio_1f_rag_vs_bm25.py` | RAG | RAG semántico vs. BM25 con una pregunta parafraseada | sí |
| `ejercicio_4a_self_note.py` | RAG | Self-note: el modelo anota el contexto antes de responder | sí |
| `graphrag.py` | GraphRAG | Recorrido por saltos (BFS) sobre un grafo de 8 tripletas, con 3 y 5 saltos | no |
| `graphrag_adk2.py` | GraphRAG | El mismo grafo como Workflow de ADK 2: router, traversal y validador | no |
| `ejercicio_4b_graphrag_gemini.py` | GraphRAG | El sub-grafo se le pasa a Gemini para que redacte la respuesta | sí |
| `agentic_rag.py` | Agentic RAG | El agente elige las herramientas; el código fija los topes | sí |
| `memoria_adk.py` | Memoria | Sesión, `session.state` y memoria de largo plazo entre sesiones (`PreloadMemoryTool`) | sí |
| `ejercicio_2d_estado_registrar_dato.py` | Memoria | El agente escribe en `session.state` con una tool: «lo dijo» no es «lo registró» | sí |
| `memoria_faiss.py` (+ `servicios_memoria.py`) | Memoria | Memoria de largo plazo propia (FAISS + SQLite) que sobrevive a un proceso nuevo | sí |
| `memory_bank.py` (+ `servicios_memoria.py`, `gemini_backend.py`) | Memoria | Réplica del patrón *Memory Bank*: extrae hechos, consolida correcciones, aísla por usuario y borra | sí |

Cada script tiene, en su propio encabezado, qué muestra y cómo leer su salida.

## Setup

### 1. Obtener una API key

Generá una API key gratuita en [Google AI Studio](https://aistudio.google.com/apikey).
Solo hace falta para los ejemplos marcados «sí».

### 2. Entorno y dependencias (una sola vez)

```bash
./setup.sh
```

Crea el `.venv`, instala `requirements.txt` y, si no existe `.env`, lo crea a partir de `.env.example`.
Necesita Python de 3.10 a 3.13 (se probó con 3.12) y bash (Linux, macOS o WSL).

- **Espacio:** el entorno ocupa alrededor de 1,6 GB. En Linux, `setup.sh` instala antes la versión CPU de
  PyTorch; la de PyPI trae CUDA y pesa varios GB.
- **Primera corrida:** se descarga el modelo de embeddings (alrededor de 450 MB). Hace falta conexión; después
  los ejemplos de retrieval corren sin red. Los avisos de Hugging Face sobre «unauthenticated requests» son inofensivos.

### 3. Completar `.env`

Editá `.env` y pegá tu key:

```
GOOGLE_API_KEY=tu-api-key
```

No compartas ni subas a ningún repo el archivo `.env`.

## Ejecutar

```bash
./run.sh 1            # retrieval con FAISS y scores engañosos
./run.sh 2            # BM25 vs. semántico vs. híbrido, y barrido de alpha
./run.sh graph        # GraphRAG: 3 vs. 5 saltos
./run.sh graph-adk2   # GraphRAG como Workflow de ADK 2
./run.sh offline      # los cuatro anteriores (sin API key)

./run.sh 1e           # RAG completo con Gemini
./run.sh 1f           # RAG semántico vs. BM25 con una paráfrasis
./run.sh 4a           # self-note
./run.sh 4b           # GraphRAG con síntesis de Gemini
./run.sh agentic      # Agentic RAG
./run.sh memoria      # memoria de sesión y de largo plazo
./run.sh 2d           # el agente escribe en session.state
./run.sh faiss        # memoria FAISS + SQLite (guarda y recuerda en dos procesos)
./run.sh bank         # Memory Bank: hechos y consolidación
./run.sh all          # todo, en ese orden
```

`run.sh` activa el `.venv` y carga `.env`, así que no hace falta activar el entorno ni exportar variables a mano.
Sin argumentos muestra la lista completa. `faiss` y `bank` aceptan un subcomando: `reset`, `guardar`, `recordar`
o `todo` (por defecto).

## Qué mirar

**Retrieval (sin API key).** Estas cifras son deterministas, así que tienen que dar igual en tu máquina:

- `./run.sh 1`: para *«¿Cuánto es el máximo que le puedo prestar a un cliente?»* el top-3 tiene scores
  `0.6113`, `0.3346` y `0.3313`. El primero es el correcto; el tercero es de otra norma y casi empata con el segundo:
  el score solo ordena, no dice si el fragmento sirve.
- `./run.sh 2`: con las 7 preguntas, los tres métodos dan `recall@3 = 0.857` y `mrr = 0.786`. El promedio los
  muestra iguales, pero la tabla por pregunta no: BM25 y el híbrido fallan con *«¿Qué pasa si el legajo está
  desactualizado?»* y el semántico falla con *«Cuándo vence el dictamen de riesgos»*. Después probá el barrido de `alpha`.
- `./run.sh 1f`: antes de generar, imprime el retrieval de cada método para la paráfrasis. BM25 trae
  `norm_004`, `norm_007`, `norm_002` y **no** `norm_003`, la norma que responde; el semántico sí la trae primera.
- `./run.sh graph`: con 3 saltos el recorrido alcanza 6 aristas; con 5, las 8. Con 3 saltos se pierde exposición
  (USD 4.6 M en vez de USD 5.4 M): el tope de saltos corta el grafo. `graph-adk2` muestra cómo un validador
  expande el recorrido cuando la frontera sigue abierta.

**Con Gemini.** Las respuestas **no son deterministas**: el texto cambia entre corridas. Lo que hay que mirar:

- `1e`: la línea `FUENTES` lista los fragmentos que *entraron* al prompt, no los que sustentan la respuesta.
  Hay una pregunta (*«¿Qué pasa si el legajo del cliente está vencido?»*) cuyo retrieval no trae la norma
  correcta: mirá qué contesta el modelo.
- `4a`: el retrieval da `norm_004`, `norm_005`, `norm_006`. Lo que hay que evaluar no es qué respuesta «suena mejor»,
  sino si alguna detecta el conflicto: el legajo tiene 14 meses y el umbral es 12.
- `4b`: con 5 saltos la exposición real es USD 5.4 M, pero el modelo decide qué relaciones cuentan como «grupo»
  y puede dar otra cifra. Por eso en `agentic_rag.py` las sumas las hace el código.
- `agentic`: tres preguntas, tres comportamientos (una herramienta, una cadena, ninguna). Cada una se repite para ver
  que la secuencia de herramientas puede variar; los topes (`MAX_SALTOS`, `MAX_K`, `max_llm_calls`) no.
- `memoria`: el agente tiene memoria pero ningún retriever de normativa, así que puede citar una norma que no existe.
- `2d`: el valor que queda en `session.state` es el que el modelo le pasó a la tool, no el texto literal del usuario.
  Y el modelo puede no llamarla: en alguna corrida un campo termina en `None` aunque el usuario lo haya confirmado.
  Por eso el control real es la validación dentro de la tool, no la instrucción.

## Memoria: `faiss` y `bank`

Las dos demos guardan en disco (SQLite) y corren en **dos procesos distintos**: eso es lo que prueba que la memoria
persiste. Las bases quedan en `datos_memoria_faiss/` y `datos_memory_bank/`; no se suben a git. `./run.sh faiss reset`
o `./run.sh bank reset` empiezan de cero.

| | Memoria FAISS + SQLite (`faiss`) | Memory Bank, réplica del patrón (`bank`) |
|---|---|---|
| Qué guarda | Cada turno, tal cual | **Hechos** extraídos por un LLM |
| Una corrección («no son 24 meses, son 18») | Quedan dos turnos que se contradicen | El hecho viejo pasa al historial y **queda uno vigente** |
| Alcance | `user_id` | `user_id` |
| Borrado de un usuario | — | Hechos y sesiones, y se comprueba que no queden rastros en los archivos |
| LLM | Solo el del agente | El del agente y el que extrae y consolida |

El servicio administrado «Memory Bank» de Google Cloud exige un Agent Engine y no se puede correr en tu máquina.
`bank` es una réplica del **patrón**, no del servicio: ADK define la interfaz (`BaseMemoryService`) y el agente no
cambia. No replica la escala, el control de acceso, la auditoría ni la residencia de datos de un servicio gestionado.
Además el resultado depende de lo que Gemini extraiga y decida al consolidar: si una verificación falla, es un
resultado de la demo, no un error del programa.

## Sobre la salida y los límites de la API

- La API key gratuita tiene un límite de *requests* por minuto y por día. Si ves un error de cuota (429), los
  scripts reintentan solos con espera; si persiste, esperá un minuto y volvé a correr.
- `./run.sh all` hace muchas llamadas. Con la capa gratuita conviene correr los ejemplos de a uno, y
  `python agentic_rag.py --repeticiones 1` (con el `.venv` activado) reduce las llamadas de Agentic RAG.
- Para probar otro modelo, descomentá `DEMO_MODEL` en `.env`.

## Problemas frecuentes

| Síntoma | Causa y remedio |
|---|---|
| `No existe .venv — corré ./setup.sh primero.` | Falta el entorno: `./setup.sh`. |
| `Este ejemplo llama a Gemini y falta la API key.` | `.env` no tiene `GOOGLE_API_KEY` (o sigue con `tu-api-key`). |
| `OSError: We couldn't connect to 'https://huggingface.co'` | El modelo de embeddings todavía no se descargó y no hay red: conectate y corré `./run.sh 1`. |
| `Hace falta Python entre 3.10 y 3.13` | Instalá Python 3.12 y volvé a correr `./setup.sh`. |
| `Permission denied` al correr `./setup.sh` | `chmod +x setup.sh run.sh`. |
| Un `Traceback` con `Failed to preload memory` en `./run.sh faiss` | Es lo esperado: la verificación [5] rompe `search_memory` a propósito para comprobar que `PreloadMemoryTool` no propaga el error, y ADK lo registra en el log. |
| `recordar` falla en `faiss` o `bank` | Necesita que `guardar` haya corrido antes y, en `bank`, que no se haya ejercido ya el derecho al olvido. `todo` (el valor por defecto) empieza con `reset` y no tiene ese problema. |

## Estructura

```
LABS/
├── setup.sh                              # crear .venv, instalar deps, armar .env
├── run.sh                                # correr un ejemplo con venv + .env cargados
├── requirements.txt
├── .env.example                          # plantilla: copiar a .env y completar
├── rag_corpus.py                         # las 8 normas sintéticas
├── rag_pipeline.py                       # embeddings + FAISS + retrieval
├── hybrid.py                             # buscador híbrido (BM25 + FAISS) y métricas
├── comparar_metodos.py                   # tabla por pregunta, agregado y barrido de alpha
├── ejercicio_1e_rag_generacion.py
├── ejercicio_1f_rag_vs_bm25.py
├── ejercicio_4a_self_note.py
├── graphrag.py                           # grafo de 8 tripletas + BFS
├── graphrag_adk2.py
├── ejercicio_4b_graphrag_gemini.py
├── agentic_rag.py
├── memoria_adk.py
├── ejercicio_2d_estado_registrar_dato.py
├── memoria_faiss.py
├── memory_bank.py
├── servicios_memoria.py                  # los dos servicios de memoria (subclases de BaseMemoryService)
├── gemini_backend.py                     # el LLM que extrae y consolida hechos en memory_bank.py
├── adk_util.py                           # ejecutar agentes y reintentar ante 429 o cortes de red
└── lab_util.py                           # una llamada a Gemini con reintentos
```
