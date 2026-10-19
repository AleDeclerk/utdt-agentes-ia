# Labs Módulo 7 — Aprendizaje sin tocar el modelo · Arquitectura de Agentes IA · UTDT 2026

Tres demos de las técnicas **no paramétricas** del módulo: el agente mejora sin reentrenar el modelo,
porque lo aprendido se guarda **afuera** (un archivo) y se le devuelve al prompt cuando hace falta.
Están armadas con ADK 2 (un grafo `Workflow`) y usan una API key gratuita de Google AI Studio.

Cada demo es **baseline contra una técnica**: se mide al agente sin memoria y al mismo agente con la
técnica, con la misma métrica. No se comparan las técnicas entre sí.

## Las tres demos

| Técnica | Script | Qué guarda (write path) | Cómo lo recupera (read path) | Persiste en | Tareas | Llamadas al modelo |
|---|---|---|---|---|---|---|
| **Few-shot dinámico** | `ejemplos_dinamicos_adk2.py` | **Casos resueltos**: enunciado, resolución y respuesta correcta | Por parecido (embeddings), los 3 más cercanos | `banco_casos.json` | `tareas_caso.py` (12) | ~60 |
| **Reflexion** | `reflexion_adk2.py` | **Lecciones**: la reflexión que el modelo escribe tras cada fallo | Por parecido del enunciado, las 2 más cercanas | `memoria_reflexiones.json` | `tareas.py` (15) | ~75 |
| **ExpeL** | `expel_caso_adk2.py` | **Reglas generales** destiladas de la experiencia, con votos | No busca: inyecta las reglas confirmadas (≥ 2 votos) | `reglas_expel_caso.json` | `tareas_caso.py` (12) | ~60 |

Reflexion guarda lecciones sueltas, atadas a casos concretos, y las recupera por parecido. Lo que ExpeL
agrega no es «transferir» (la memoria de Reflexion ya lo hace) sino **generalizar**: pasar de lecciones
sueltas a reglas, con las operaciones AGREE / ADD / EDIT / REMOVE y votos.

## Cómo se ve la salida

Las tres demos imprimen lo mismo, en este orden:

1. **Qué vas a ver**: tres líneas de presentación.
2. **Pasos**: el aprendizaje o la destilación, con una línea por tarea.
3. **«Qué pasó»**: una explicación breve **armada a partir de los resultados** (no es texto fijo: si la
   corrida sale mal, lo dice y señala dónde).
4. **Prueba en tareas nuevas**: una tabla por tarea y un ejemplo concreto de respuesta.
5. **`RESUMEN`**: baseline contra técnica, `aciertos/n`, acierto al **primer intento**.
6. **`COSTO MEDIDO`**: llamadas y tokens reales, y el costo que tendrían a precio de lista. Se acumula en
   `costo_acumulado.json`.

## Las tareas

Todas son sintéticas y tienen una **convención de la entidad que el enunciado no dice**. Las convenciones
están inventadas para el curso (no son políticas de ningún banco real).

- **`tareas.py` (Reflexion):** 15 tareas en tres categorías (comisión redondeada al alza, punitorio =
  150% de la compensatoria, comisión + IVA 21%): 3 de entrenamiento y 2 nuevas por categoría. Un modelo
  sin memoria no acierta casi ninguna. `python tareas.py` las lista sin llamar a ningún modelo.
- **`tareas_caso.py` (few-shot y ExpeL):** dos convenciones que se deducen comparando el número del agente
  con el correcto: un **cargo fijo de $1,800** a las transferencias al exterior (diferencia constante) y un
  **50% de descuento** a los clientes Premium (cociente constante). Hay 3 tareas de entrenamiento y 2 nuevas
  por convención, más **dos controles** en la prueba (transferencia nacional, cliente estándar) donde la
  convención no aplica y el agente ya acierta. Los controles son la prueba de que lo aprendido no se
  sobre-aplica. `python tareas_caso.py` las lista.

Son dos juegos de tareas porque cada técnica tiene un caso pensado para que se vea su mecanismo. Los casos
no son comparables entre sí.

## El grafo (`comun.py`)

```
START ─► [recuperar] ─► resolver ─► evaluar ──ok / sin intentos──► fin
                           ▲           │ fallo
                           │           ▼
                           └─ guardar ◄─ reflexionar
```

Un solo grafo sirve para todas las condiciones. `max_intentos=1` es «sin memoria». `recuperar` es un nodo
opcional que escribe en `session.state` lo que el agente recuerda (`ejemplos` del few-shot o `lecciones` de
Reflexion). El modelo no lee el estado directamente: lo ve a través de las plantillas `{ejemplos?}`,
`{lecciones?}`, `{reflexiones?}` y `{reglas?}` de la instrucción.

Para leer el código, conviene empezar por: la clase `MemoriaReflexiones` (en `comun.py`), la clase
`BancoCasos` (en `ejemplos_dinamicos_adk2.py`), la función `aplicar_operaciones` (en `expel_adk2.py`) y el
prompt `INSTRUCCION_DESTILADOR` (en `expel_caso_adk2.py`).

## Archivos

| Archivo | Qué hace |
|---|---|
| `tareas.py` | Las 15 tareas de Reflexion, el verificador y el parser del número |
| `tareas_caso.py` | Las 12 tareas del caso «cargo fijo / descuento Premium», con su resolución paso a paso |
| `comun.py` | El grafo, `MemoriaReflexiones`, embeddings, concurrencia y reintentos, costo medido, `narrar` y el bloque `RESUMEN` |
| `ejemplos_dinamicos_adk2.py` | **Few-shot dinámico.** Aprende un banco de casos sobre TRAIN y prueba zero-shot, fijo (los primeros 3) y dinámico k=3. `--variantes` agrega fijo diverso y k=1 |
| `reflexion_adk2.py` | **Reflexion.** Parte 1: aprende sobre TRAIN, una tarea por vez, y persiste las lecciones. Parte 2: prueba en TEST contra «sin memoria» |
| `expel_caso_adk2.py` | **ExpeL.** Experiencia → destilación → prueba, con 1 intento en ambas condiciones: solo cambian las reglas |
| `expel_adk2.py` | Biblioteca de ExpeL (`aplicar_operaciones`, `proponer_operaciones`, el banco de reglas) y una variante sobre las tareas de Reflexion. `expel_caso_adk2.py` la importa |

Al correr se generan los archivos de salida (`banco_casos.json`, `memoria_reflexiones.json`,
`reglas_expel_caso.json`, `*_resultados.json`, `costo_acumulado.json`). No se versionan: cada uno arma los
suyos, y **leer esos JSON es parte del ejercicio**.

## Setup

### 1. Obtener una API key

Generá una API key gratuita en [Google AI Studio](https://aistudio.google.com/apikey).

### 2. Entorno y dependencias

Necesitás Python 3.12 o superior (se probó con 3.14).

```bash
cd MODULO_7/LABS
python3 -m venv .venv && source .venv/bin/activate     # en Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # google-adk 2.11.0, google-genai 2.29.0
cp .env.example .env                                   # y pegá tu key en GOOGLE_API_KEY
```

`.env` no se versiona. Las variables opcionales (`DEMO_MODEL`, `DEMO_CONCURRENCIA`, `DEMO_TOPE_USD`) están
comentadas en `.env.example`.

Chequeo rápido de la key (imprime la forma del arreglo de embeddings, algo como `(1, N)`):

```bash
python -c "from comun import embeber; print(embeber(['hola']).shape)"
```

## Ejecución

| Comando | Qué hace |
|---|---|
| `python ejemplos_dinamicos_adk2.py` | Few-shot: arma el banco con las tareas de entrenamiento y prueba |
| `python ejemplos_dinamicos_adk2.py --solo-probar` | Solo la prueba, con el `banco_casos.json` existente |
| `python ejemplos_dinamicos_adk2.py --variantes` | Además: fijo diverso y k=1 |
| `python reflexion_adk2.py --solo-aprender` | Parte 1 de Reflexion: aprende sobre TRAIN |
| `python reflexion_adk2.py` | Parte 1 + Parte 2 (prueba en TEST) |
| `python reflexion_adk2.py --solo-probar` | Solo la Parte 2, con `memoria_reflexiones.json` |
| `python expel_caso_adk2.py` | ExpeL: experiencia, destilación y prueba |
| `python expel_caso_adk2.py --solo-probar` | Solo la prueba, con `reglas_expel_caso.json` |

Todos los scripts aceptan `--help` sin ejecutar nada. Cada demo tarda unos minutos: las llamadas se hacen de a
`DEMO_CONCURRENCIA` (2 por defecto) para cuidar la cuota.

## Cuota y modelo (leer antes de correr)

- **La cuota gratuita es limitada.** Los límites (solicitudes por minuto y por día) dependen de tu proyecto y
  de tu nivel de uso; Google los muestra en <https://aistudio.google.com/rate-limit>. Cada demo hace entre
  60 y 75 llamadas al modelo (y algunas más a embeddings). Si la cuota por minuto se agota, el script espera
  y reintenta solo (10, 30, 60 y 60 segundos). Si se agota la **diaria**, hay que esperar a que se renueve
  (medianoche de la hora del Pacífico) o habilitar facturación en tu proyecto.
- **El costo medido es una referencia.** Con la capa gratuita no se cobra nada. `COSTO MEDIDO` calcula cuánto
  costaría a los precios de lista de `gemini-2.5-flash` en el nivel de pago (entrada USD 0.30 y salida
  USD 2.50 por millón de tokens, el razonamiento se cobra como salida). En las corridas de referencia fue de
  USD 0.07 a 0.09 (few-shot), alrededor de 0.15 (Reflexion) y 0.09 a 0.14 (ExpeL).
- **Datos en la capa gratuita.** En el nivel gratuito Google puede usar lo que enviás para mejorar sus
  productos. Acá todo es sintético, pero no uses estas demos con datos reales.
- **Disponibilidad del modelo.** Estas demos usan `gemini-2.5-flash`, y Google informó que limita el acceso a
  los modelos 2.5 a quienes ya los usaron. Si tu key es nueva y la primera llamada falla porque el modelo no
  está disponible, probá otro con `DEMO_MODEL` (por ejemplo `gemini-3.8-flash`). Los resultados de abajo son
  de `gemini-2.5-flash` y con otro modelo van a ser distintos.

## Resultados de referencia

Son corridas del profesor con `gemini-2.5-flash`, en octubre de 2026, hechas con el mismo modelo pero
accedido a través de Vertex AI (todavía no hay una corrida de referencia con una key de AI Studio). Cada
corrida usa n = 18 por condición (6 tareas nuevas × 3 repeticiones) y 1 intento por tarea. La métrica es el
acierto al **primer intento** en tareas nuevas.

| Demo | Baseline → con la técnica, una fila por corrida |
|---|---|
| **Few-shot dinámico (k=3)** | 6/18 → 18/18 · 6/18 → 18/18 (el fijo, con los primeros 3, quedó en 11/18 y 12/18) |
| **Reflexion** | 0/18 → 15/18 · 1/18 → 15/18 · 2/18 → 16/18 |
| **ExpeL** | 6/18 → 18/18 · 6/18 → 11/18 · 6/18 → 8/18 |

Cómo leerlas:

- **Son pocas corridas con n chico.** Una diferencia de 10 o 15 puntos no es concluyente, y a Reflexion y
  few-shot les fue de manera parecida en cada corrida. **ExpeL varió mucho**: la destilación no es
  determinista, y la misma demo escribió reglas distintas cada vez. En la corrida de 8/18, por ejemplo, la
  regla de exterior quedó con un «mínimo de $6,300» tomado de un caso puntual y falló en todas las tareas de
  exterior. Una regla errónea se recupera y se aplica como si fuera conocimiento: por eso hay que leer
  `reglas_expel_caso.json`.
- **Las tareas son sintéticas y el verificador es generoso:** revela el número correcto. Con uno que solo
  dijera «mal», Reflexion y ExpeL rendirían bastante menos.
- **Los casos del few-shot incluyen la resolución paso a paso**, rotulada por atributos del caso. Sin la
  resolución, el modelo no dedujo el ×0.5 a partir de ejemplos que solo traían la respuesta.
- **El umbral de 2 votos en ExpeL es una decisión de diseño de esta demo.** Un voto es una experiencia que
  respalda la regla (un `EDIT` también cuenta). Con todas las reglas inyectadas, sin umbral, una regla
  espuria de un solo voto rompió las tareas de exterior en una corrida anterior.
- **La memoria es un archivo:** versionable, auditable y borrable.

### Dónde ExpeL se justifica (y la demo no lo prueba)

Cuando la experiencia crece tanto que no se puede recuperar ni inyectar toda, cuando hace falta un artefacto
compacto y auditable (una lista corta de reglas en lugar de cientos de reflexiones) o cuando interesa lo
general entre tareas distintas.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `Falta GOOGLE_API_KEY` | No existe `.env` (copiá `.env.example`) o la variable está vacía |
| `API_KEY_INVALID` / 400 | La key está mal copiada o fue revocada; generá otra en AI Studio |
| 404 o 403 diciendo que el modelo no existe o no está disponible | Tu key es nueva y no tiene acceso a los modelos 2.5: probá `DEMO_MODEL` con otro (ver «Cuota y modelo») |
| Línea «… cuota de la API agotada o corte de red; reintento en N s» | **No es fatal**: `comun.con_reintentos` espera y reintenta. Si se repite mucho, bajá `DEMO_CONCURRENCIA` a 1. Si falla igual al final, puede ser la cuota **diaria** |
| `TopeDeCostoExcedido` | La corrida superó `DEMO_TOPE_USD`. Subí el tope o revisá por qué gasta de más |
| `ModuleNotFoundError: google.adk` | Falta `pip install -r requirements.txt` en el entorno activo |
| Error al instalar `numpy==2.5.4` | Tu Python es anterior a 3.12 |
| `--solo-probar` dice «Falta banco_casos.json» (o memoria / reglas) | Corré antes el script sin `--solo-probar` |
