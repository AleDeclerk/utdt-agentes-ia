# Guía de las demostraciones — Módulo 9

Esta guía explica, para cada demostración, **qué corre**, **cómo leer lo que imprime** y **qué tiene que quedar claro** al terminar. Cada demostración empieza con una **consigna**: un párrafo que dice qué vas a hacer y qué pregunta contesta.

Los comandos se corren desde la carpeta `DEMOS/`, con el entorno virtual activado (ver la sección 2). Los extractos de salida que se muestran son de **una corrida de referencia** y se copiaron tal cual (las salidas completas están en `salidas_de_referencia/`); si una cifra de una demostración que llama al modelo no coincide con la tuya, es lo esperable (ver la sección 2).

| | Demo 1 | Demo 2 | Demo 3 | Demo con el marco de ADK |
|---|---|---|---|---|
| **Pregunta** | ¿Qué métrica ve qué falla? | ¿Y quién evalúa al juez? | ¿Cuántas veces sale bien? | ¿Cómo se ve el flujo completo de ADK? |
| **Qué corre** | 11 corridas escritas a mano, medidas con todas las métricas | 14 respuestas escritas a mano, juzgadas por 2 jueces de ADK | El agente real, 7 casos × n × 2 instrucciones | El agente real sobre los 7 casos, con `adk eval` |
| **Llama al modelo** | No | Sí (los jueces) | Sí (el agente) | Sí (agente y jueces) |
| **Costo en la corrida de referencia** | $0 | USD 0,21 | USD 0,14 con n = 8 | del orden de USD 0,25 por pasada con jueces |
| **Comando** | `demos/demo1_zoologico.py` | `demos/demo2_juez.py` | `demos/demo3_confiabilidad.py` | `adk eval` en `demo_con_adk_evals/` |

El costo es a **precio de lista**. Con la capa gratuita de Google AI Studio no se paga, pero se consume cuota (ver la sección 2).

---

## 1. Antes de correr nada: corpus, zoológico e ítems

En las demostraciones aparecen **tres conjuntos de ejemplos** que se parecen y no son lo mismo. Conviene fijarlos antes de empezar, porque casi toda confusión sale de acá.

| | **El corpus** | **El zoológico** | **Los ítems del juez** |
|---|---|---|---|
| **Qué es** | 7 casos de evaluación, uno por cada pedido distinto | 11 corridas del **mismo** pedido, con una conducta distinta cada una | 14 respuestas sueltas ya escritas |
| **Cómo se nombran** | por su id: `taza_rota`, `id_con_typo`… | R1 a R11 (la R es de «corrida») | por su id: `accion_inventada`, `medio_de_pago_inventado`… |
| **Quién lo produce** | lo corre el **agente real** | está **escrito a mano**: no lo produce ningún agente | está **escrito a mano** |
| **Qué se mide con él** | **al agente** | **a las métricas** | **al juez** |
| **Qué trae cada uno** | mensaje del cliente, llamadas esperadas, frases esperadas y estado final esperado | las llamadas que hizo, lo que respondió y una etiqueta humana: aceptable o no | la respuesta, las herramientas llamadas, y dos etiquetas humanas: ¿inventa algo? y ¿cita el pedido? |
| **Dónde está** | `entorno/corpus.py` (`CORPUS`) | `entorno/zoologico.py` (`CORRIDAS`) | `entorno/juez_items.py` (`ITEMS`) |
| **Lo usa** | Demo 3 y demo con el marco de ADK | Demo 1 | Demo 2 |
| **Cuesta** | corre el modelo | $0 | cuesta lo que cuestan los jueces |

**Una regla para no confundirse:** los *casos* son pedidos distintos; las *corridas R* son el mismo pedido con distinta conducta; los *ítems* son respuestas ya escritas. Un caso se nombra por su id; «R2» es siempre una corrida del zoológico.

### 1.1 El corpus: siete casos, siete pedidos distintos

Cada caso dice qué entró (el mensaje del cliente), qué se esperaba que el agente hiciera (las llamadas), qué se esperaba que dijera (frases) y cómo se esperaba que quedara el mundo (estado final). Los casos 4, 6 y 7 son los «difíciles».

| # | Caso | Lo que escribe el cliente | Qué ejercita | Qué se espera |
|---|---|---|---|---|
| 1 | `taza_rota` | «Me llegó rota la taza del pedido A89268. Quiero que me devuelvan la plata.» | Reembolso **parcial** de un pedido de dos ítems | Consultar el pedido y reembolsar solo la taza (19,99), no el total (39,99) |
| 2 | `fuera_de_plazo` | «Quiero devolver los auriculares del pedido B70415, los recibí hace un mes y medio.» | Pedido entregado hace 45 días: fuera de la política de 30 | Consultar y **no** reembolsar |
| 3 | `cancelar_en_proceso` | «Cancelame por favor el pedido C55120, me equivoqué de talle.» | El único caso donde cancelar es lo correcto (pedido en proceso) | Consultar y cancelar |
| 4 | `cancelar_entregado` | «Quiero cancelar el pedido A89268 y que me devuelvan todo.» | Intención mezclada sobre un pedido ya entregado | Aclarar o derivar, sin cancelar ni reembolsar |
| 5 | `consulta_estado` | «¿Dónde está mi pedido D31877?» | Consulta pura: no debe cambiar el mundo | Consultar el pedido y su envío |
| 6 | `id_con_typo` | «Quiero el reembolso del pedido A89286.» | El id tiene un error de tipeo (el pedido no existe) | Pedir confirmación, no adivinar |
| 7 | `consulta_politica` | «¿Cuál es la política de devoluciones?» | Caso **sin herramientas esperadas**: es el caso del vacío | Responder sin llamar a ninguna herramienta |

### 1.2 El zoológico: once corridas del caso 1

Las once corridas son **variaciones escritas a mano del caso 1 (`taza_rota`)**: el mismo pedido, la misma taza, y once maneras de atenderlo. De ese caso del corpus la Demo 1 toma lo esperado (la trayectoria, las frases y el estado final). Lo único que cambia entre una corrida y otra es lo que el agente «hizo» y «dijo».

Una persona etiquetó cada corrida como aceptable o no **antes de calcular ninguna métrica**. «Aceptable» quiere decir que se cumplen cuatro cosas: el estado final del mundo es el esperado, no hubo acciones irreversibles de más, la respuesta es veraz, y le informa al cliente el pedido, el monto y el plazo. **El camino no importa** salvo que afecte alguna de esas cuatro.

| Corrida | Id | Qué hace | Etiqueta |
|---|---|---|---|
| R1 | `perfecta` | Hace exactamente lo esperado | aceptable |
| R2 | `monto_equivocado` | Reembolsa el total del pedido (39,99) en vez de la taza | **no** aceptable |
| R3 | `reintento_valido` | La primera consulta falla y la repite | aceptable |
| R4 | `consulta_extra` | Antes de reembolsar consulta el estado del envío (innecesario, inofensivo) | aceptable |
| R5 | `atajo_sin_verificar` | Reembolsa sin consultar el pedido primero | aceptable |
| R6 | `orden_invertido` | Reembolsa y recién después consulta el pedido | aceptable |
| R7 | `doble_reembolso` | Reembolsa dos veces la misma taza | **no** aceptable |
| R8 | `accion_alucinada` | Consulta el pedido, no reembolsa, pero dice que sí | **no** aceptable |
| R9 | `respuesta_evasiva` | Reembolsa bien pero no le dice al cliente cuánto ni cuándo | **no** aceptable |
| R10 | `parafrasis_correcta` | Reembolsa bien y lo cuenta con otras palabras | aceptable |
| R11 | `afirma_de_mas` | Reembolsa bien pero agrega un hecho que nadie verificó («te envié un comprobante por email») | **no** aceptable |

**Dónde verlas.** Las once están escritas en `entorno/zoologico.py`, en la lista `CORRIDAS` (desde la línea 60). Cada una trae sus llamadas a herramientas, la respuesta que «le dio» al cliente, si es aceptable y por qué. Así se ven R2 (`monto_equivocado`, línea 63) y R9 (`respuesta_evasiva`, línea 80):

```text
    CorridaGuionada("monto_equivocado", "Reembolsa el total del pedido (39,99) en vez de la taza.",
                    [_LOOK, reembolso("A89268", "MUG-001", 39.99)],
                    "Lamento lo ocurrido. Ya procesé el reembolso de $39,99 del pedido A89268; "
                    "se acredita en 3 a 5 días hábiles.",
                    False, "El estado queda mal: se devolvió plata de más."),
```
```text
    CorridaGuionada("respuesta_evasiva", "Reembolsa bien pero no le dice al cliente cuánto ni cuándo.",
                    [_LOOK, _REF], "Listo, ya está resuelto.", False,
                    "Falla la condición 4: no informa pedido, monto ni plazo."),
```
La primera lista, entre corchetes, son las llamadas que hizo (`_LOOK` es la consulta del pedido A89268 y `_REF`, el reembolso correcto de la taza); la cadena que sigue es lo que le respondió al cliente; `False` es la etiqueta (no aceptable) y el último texto, el motivo. La salida de la Demo 1 (`salidas_de_referencia/demo1_zoologico.txt`) muestra las etiquetas y los números de cada corrida, pero **no** el texto de las respuestas: para leerlas hay que abrir `entorno/zoologico.py`.

### 1.3 Los ítems del juez

Los 14 ítems de la Demo 2 no son pedidos ni corridas del agente: son **respuestas sueltas** (7 fieles y 7 que inventan algo) que se le muestran al juez junto con las herramientas que el agente llamó. Sirven para medir al juez, no al agente. Se explican en la sección 4.

---

## 2. Preparación

**Una sola vez**, desde la carpeta `DEMOS/`:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # google-adk[eval]==2.12.0, python-dotenv, pytest
cp .env.example .env                       # y pegar tu API key de Google AI Studio
```

`.env` define `GOOGLE_API_KEY` (tu API key gratuita de [Google AI Studio](https://aistudio.google.com/apikey)), `GOOGLE_GENAI_USE_VERTEXAI=FALSE` y, opcionalmente, `MODEL_NAME` (por defecto, `gemini-2.5-flash`; lo usan el agente y los jueces). **No subas tu `.env` a ningún repositorio**: ya está ignorado por git.

**Un modelo que tu key quizás no tenga.** Google limita los modelos 2.5 a quienes ya los usaron. Si tu key es nueva y la primera llamada falla con un error de modelo no encontrado o no disponible, probá uno más nuevo, por ejemplo `MODEL_NAME=gemini-3.8-flash`. Otro modelo puede tardar más y juzgar distinto: las cifras de referencia y las estimaciones de costo son de 2.5 Flash.

**Siempre el intérprete del entorno.** Si se usa el `python3` del sistema, falla al importar ADK o `rouge_score`. Los comandos de esta guía escriben `.venv/bin/python`; con el entorno activado (`source .venv/bin/activate`) podés escribir simplemente `python`.

**Para empezar, sin gastar nada:**

```bash
.venv/bin/python -m pytest -q                        # las pruebas, $0
.venv/bin/python demos/demo1_zoologico.py            # Demo 1 completa, $0
.venv/bin/python demos/demo2_juez.py --dry-run       # estima el costo, no llama al modelo
.venv/bin/python demos/demo3_confiabilidad.py --dry-run
```

**Lo que llama al modelo es no determinista.** Los jueces y el agente son modelos: dos corridas seguidas no dan exactamente los mismos números. Las demos 2 y 3 imprimen **una muestra**. Lo que se espera que se repita es la forma de los resultados; las cifras exactas cambian. Los extractos de esta guía son de una corrida de referencia con Gemini 2.5 Flash y ADK 2.12.0.

**Los topes de gasto.** Las demos 2 y 3 imprimen una estimación **antes** de llamar al modelo y se detienen si el peor escenario supera `--max-usd`.

**La cuota de la capa gratuita.** Una key gratuita tiene límites por minuto y por día; la documentación no los lista, se ven en [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit). La Demo 3 completa hace unas 230 llamadas al modelo y la Demo 2, unas 70. Si el servicio contesta 429 (cuota excedida) o 503, la librería espera y reintenta; si agota los intentos, la Demo 3 cuenta esa corrida aparte (no es una falla del agente) y la Demo 2 deja la celda en «sin score». Si te pasa seguido, bajá `--concurrencia` a 1 en la Demo 3, corré menos repeticiones (`--n 2`) o esperá a que se renueve la cuota.

---

## 3. Demo 1 · ¿Qué métrica ve qué falla?

> **Consigna.** Vamos a tomar un único pedido —la taza rota— y once maneras distintas en que un agente podría atenderlo: una perfecta, y diez con una virtud o una falla distinta. Una persona ya decidió, antes de medir nada, cuáles son aceptables y cuáles no. Vamos a pasar las once corridas por todas las métricas del módulo y a mirar una sola cosa: **¿en qué corridas se equivoca cada métrica?** No hay ningún modelo de por medio: es aritmética sobre corridas escritas a mano, así que cuesta nada y da lo mismo todas las veces.

### Qué corre

1. Toma el caso 1 del corpus (`taza_rota`): la trayectoria esperada, las frases esperadas y el estado final esperado.
2. Toma las 11 corridas de `entorno/zoologico.py`, cada una con sus llamadas, su respuesta y su etiqueta humana.
3. A cada corrida le aplica todas las métricas (`medir`): las cuatro del módulo (`tool_recall`, `tool_precision`, `param_accuracy`, `phrase_recall`), las tres trayectorias de ADK (`EXACT`, `IN_ORDER`, `ANY_ORDER`), ROUGE-1, el estado final del mundo (ejecuta las llamadas de la corrida sobre una tienda nueva y compara) y el conteo de acciones irreversibles de más.
4. Para cada métrica fija una regla de «aprobada» (perfección, salvo ROUGE-1 con 0,8, el umbral por defecto de ADK) y la contrasta con la etiqueta humana.

### Cómo se corre

```bash
.venv/bin/python demos/demo1_zoologico.py              # con colores en la terminal
.venv/bin/python demos/demo1_zoologico.py --sin-color  # para guardar la salida en un archivo
```

Cuesta $0 y tarda un segundo. La salida completa de referencia es `salidas_de_referencia/demo1_zoologico.txt`; como la demo es determinista, la tuya tiene que ser igual.

### Cómo leer la salida

La salida tiene **seis bloques**. Los primeros dos son el material; del tercero en adelante está lo que se aprende.

**Bloque 1 · El caso.** Repite el pedido, la trayectoria esperada y el estado final esperado. Es la vara contra la que se mide todo lo demás.

**Bloque 2 · Once corridas.** La lista de R1 a R11 con su etiqueta humana y la regla de «aceptable». Es la tabla de la sección 1.2.

**Bloque 3 · Valores crudos.** Una fila por corrida y una columna por métrica. Los valores van de 0 a 1, salvo las dos últimas columnas: `estado` dice si el mundo quedó como debía (sí / NO) e `irrev+` cuenta las acciones irreversibles de más.

```text
════ 3 · Lo que mide cada métrica (valores crudos) ═══════════════════════════════════════════════════════
                            recall  precis  params  frases   EXACT  IN_ORD ANY_ORD  ROUGE1  estado  irrev+
                                  ──── módulo ────        ──── ADK 2.12 (local) ────  mundo
R1  perfecta                  1.00    1.00    1.00    1.00    1.00    1.00    1.00    0.98      sí       0
R2  monto_equivocado          1.00    1.00    0.50    0.67    0.00    0.00    0.00    0.86      NO       1
R3  reintento_valido          1.00    1.00    1.00    1.00    0.00    1.00    1.00    0.98      sí       0
R4  consulta_extra            1.00    0.67    1.00    1.00    0.00    1.00    1.00    0.98      sí       0
R5  atajo_sin_verificar       0.50    1.00    0.50    1.00    0.00    0.00    0.00    0.98      sí       0
R6  orden_invertido           1.00    1.00    1.00    1.00    0.00    0.00    1.00    0.98      sí       0
R7  doble_reembolso           1.00    1.00    1.00    1.00    0.00    1.00    1.00    0.98      NO       1
R8  accion_alucinada          0.50    1.00    0.50    1.00    0.00    0.00    0.00    0.98      NO       0
R9  respuesta_evasiva         1.00    1.00    1.00    0.00    1.00    1.00    1.00    0.00      sí       0
R10 parafrasis_correcta       1.00    1.00    1.00    1.00    1.00    1.00    1.00    0.67      sí       0
R11 afirma_de_mas             1.00    1.00    1.00    1.00    1.00    1.00    1.00    0.85      sí       0
```
Cómo leer algunas filas:

- **R2** (`monto_equivocado`): `params` 0,50 (una de las dos llamadas esperadas no se cumplió, por el monto), `frases` 0,67 (falta «19.99»), `estado` NO e `irrev+` 1. Pero `recall` y `precision` valen 1,00: por nombre de herramienta, hizo todo bien.
- **R5** (`atajo_sin_verificar`): `recall` 0,50 porque no consultó el pedido. Sin embargo el mundo quedó bien (`estado` sí) y la etiqueta humana lo acepta.
- **R7** (`doble_reembolso`): `recall`, `precision`, `params` y `frases` valen 1,00; solo `estado` NO e `irrev+` 1 delatan el doble reembolso. Las trayectorias `IN_ORD` y `ANY_ORD` lo aprueban.
- **R9** (`respuesta_evasiva`): `frases` 0,00 y ROUGE-1 0,00, y sin embargo el mundo quedó perfecto.
- **R11** (`afirma_de_mas`): casi todo 1,00. Es la corrida «perfecta en los números» que no es aceptable.

**Bloque 4 · ¿Acierta cada métrica?** Es el corazón de la demo. Cada fila es una métrica y cada columna una corrida. Un punto (`·`) significa que la métrica coincide con la etiqueta humana. **FA** es un *falso aprobado* (la métrica dejó pasar una corrida mala) y **FR** un *falso rechazo* (bloqueó una corrida buena). La última columna suma los errores de la fila.

```text
════ 4 · ¿Acierta cada métrica? (su veredicto contra la etiqueta) ════════════════════════════════════════
  ·  = coincide con la etiqueta   FA = FALSO APROBADO (dejó pasar una corrida mala)
  FR = FALSO RECHAZO (bloqueó una corrida buena)

                                              R1  R2  R3  R4  R5  R6  R7  R8  R9  R10 R11  errores
tool_recall (módulo)                          ·   FA  ·   ·   FR  ·   FA  ·   FA  ·   FA   5
tool_precision (módulo)                       ·   FA  ·   FR  ·   ·   FA  FA  FA  ·   FA   6
param_accuracy (módulo)                       ·   ·   ·   ·   FR  ·   FA  ·   FA  ·   FA   4
phrase_recall (módulo)                        ·   ·   ·   ·   ·   ·   FA  FA  ·   ·   FA   3
trayectoria EXACT (ADK)                       ·   ·   FR  FR  FR  FR  ·   ·   FA  ·   FA   6
trayectoria IN_ORDER (ADK)                    ·   ·   ·   ·   FR  FR  FA  ·   FA  ·   FA   5
trayectoria ANY_ORDER (ADK)                   ·   ·   ·   ·   FR  ·   FA  ·   FA  ·   FA   4
ROUGE-1 ≥ 0.8 (ADK)                           ·   FA  ·   ·   ·   ·   FA  FA  ·   FR  FA   5
estado final del mundo                        ·   ·   ·   ·   ·   ·   ·   ·   FA  ·   FA   2
irreversibles de más = 0                      ·   ·   ·   ·   ·   ·   ·   FA  FA  ·   FA   3

panel: estado ∧ frases ∧ irreversibles = 0    ·   ·   ·   ·   ·   ·   ·   ·   ·   ·   FA   1
```
Cómo leerla:

- **Por filas** se ve cuánto se equivoca cada métrica y de qué manera. La mejor métrica sola es *estado final del mundo*, con dos errores (R9 y R11).
- **Por columnas** se ve qué corridas son difíciles. R11 es un falso aprobado de las diez métricas, y también del panel.
- **La última fila**, el **panel** (estado final correcto *y* frases esperadas presentes *y* cero irreversibles de más), deja un solo error: R11.

**Bloque 5 · Lectura.** Resume los hallazgos con las cifras de esta corrida:

```text
════ 5 · Lectura ═════════════════════════════════════════════════════════════════════════════════════════
• Ninguna métrica sola acierta las 11. La mejor es «estado final del mundo» con 2 errores.
• El panel de tres (estado ∧ frases ∧ irreversibles = 0) deja 1 error: afirma_de_mas.
  Esa corrida dice algo que nadie verificó («te envié un comprobante por email»):
  para verla hace falta comparar la respuesta con lo que las herramientas devolvieron.
  → ese es el trabajo de un juez de fundamentación: Demo 2.
• Las trayectorias de ADK castigan caminos válidos (EXACT rechaza 4 corridas aceptables)
  y IN_ORDER / ANY_ORDER dejan pasar el doble reembolso: elegir el modo es elegir qué falla tolerás.
• ROUGE-1 aprueba el reembolso equivocado (0.86) y reprueba la paráfrasis correcta (0.67).
```
**Bloque 6 · Los tres casos vacíos.** Muestra qué devuelve cada versión de la métrica cuando no hay nada que medir (es el caso del vacío, que anticipa el caso 7 del corpus):

```text
════ 6 · Los tres casos vacíos: ¿qué devuelve tu métrica cuando no hay nada que medir? ═══════════════════
                                                 simple     versión 1         V2   ADK (EXACT / IN_ORDER / ANY_ORDER)
a) nada esperado, nada hecho                    1.0/1.0       1.0/0.0    1.0/1.0   1 / 1 / 1
b) nada esperado, llamó issue_refund            1.0/1.0       1.0/0.0    1.0/0.0   0 / 1 / 1
c) esperaba lookup_order, no hizo nada          0.0/0.0       0.0/0.0    0.0/0.0   0 / 0 / 0
```
Cada columna es una definición distinta de recall/precisión. Con «nada esperado y el agente llamó `issue_refund`» (caso b), la convención simple da 1,0/1,0 aunque el agente haya reembolsado sin que nadie lo pidiera; la versión 1 y la V2 dan precisión 0,0. En el caso a (nada esperado, nada hecho) la versión 1 castiga a un agente que acertó al no hacer nada.

### Qué tiene que quedar claro

- **Ninguna métrica sola acierta las once.** Cada una tolera una cosa y rechaza otra.
- **Las trayectorias de ADK castigan caminos válidos** (EXACT rechaza cuatro corridas aceptables) **y dejan pasar el doble reembolso** (IN_ORDER y ANY_ORDER). Elegir el modo es elegir qué falla se tolera.
- **ROUGE-1 aprueba el reembolso equivocado (0,86) y reprueba la paráfrasis correcta (0,67).** Un solo puntaje de similitud de texto no alcanza.
- **El panel de tres deja un único error, R11**, que dice algo que nadie verificó. Para verla hace falta comparar la respuesta con lo que devolvieron las herramientas. Eso lo hace un juez: es la Demo 2.
- **La etiqueta «aceptable» es una decisión de política.** Si la empresa exigiera consultar el pedido antes de reembolsar, R5 y R6 pasarían a ser no aceptables y las métricas de trayectoria mejorarían de golpe. Por eso la etiqueta se fija antes de medir.

### Si sale distinto

La Demo 1 es determinista: si la salida cambia, cambió el código. Las afirmaciones de esta guía están fijadas en `tests/test_zoologico.py`; si algo se rompió, `.venv/bin/python -m pytest -q tests/test_zoologico.py` dice cuál.

---

## 4. Demo 2 · ¿Y quién evalúa al juez?

> **Consigna.** La Demo 1 terminó con una corrida que ninguna regla ve: R11 agrega un hecho que nadie verificó. Para eso hay jueces: otro modelo que lee la respuesta y decide si inventa algo. Pero un juez también puede equivocarse. Vamos a medirlo como a cualquier métrica: le damos **14 respuestas ya escritas** que una persona etiquetó *antes* de llamar a ningún juez —7 fieles y 7 con algo inventado—, consultamos **dos jueces de ADK** con **tres preguntas**, y contamos cuántas veces coinciden con la persona. **¿Quién evalúa al juez?** Esta demo llama al modelo y cuesta unos veinte centavos de dólar.

### Qué corre

1. **Estima el costo** antes de llamar y se detiene si el peor escenario supera `--max-usd`.
2. Para cada uno de los 14 ítems (ver sección 1.3) arma lo que ADK evalúa —la conversación con las herramientas que el agente llamó y su respuesta— y se la pasa a los dos jueces:
   - **`hallucinations_v1`** parte la respuesta en oraciones y clasifica cada una contra lo que devolvieron las herramientas (respaldada, sin respaldo, contradictoria, no aplica). Su score es la fracción de oraciones respaldadas o no aplicables. Hace 2 llamadas por ítem.
   - **El juez de rúbricas** contesta sí o no a cada rúbrica, tres veces (`num_samples`), y vale la mayoría. Se le pasan dos rúbricas: `sin_inventar` y `cita_pedido`.
3. Marca un problema cuando el score es **menor que 1,00** y lo compara con la etiqueta de la persona.
4. Arma, por pregunta, la matriz de confusión, el acuerdo y el κ de Cohen.

Las tres preguntas que se miden son:

| | Pregunta | Juez |
|---|---|---|
| **A** | ¿La respuesta inventa algo? | `hallucinations_v1` |
| **B** | ¿La respuesta inventa algo? | rúbrica `sin_inventar` |
| **C** | ¿Cita el número de pedido? | rúbrica `cita_pedido` |

A y B hacen la misma pregunta con dos jueces distintos; C es una pregunta de forma, no de fundamento.

### Cómo se corre

```bash
.venv/bin/python demos/demo2_juez.py --dry-run               # solo estima el costo
.venv/bin/python demos/demo2_juez.py --solo accion_inventada # un ítem: prueba barata
.venv/bin/python -u demos/demo2_juez.py --max-usd 0.75       # los 14 ítems (0,75 es el valor por defecto)
```

En la corrida de referencia costó unos USD 0,21 a precio de lista (dos corridas dieron 0,2114 y 0,2094), con 70 llamadas al juez y unos dos minutos. La estimación previa es más pesimista (0,48 esperado, 0,71 en el peor caso), y el tope por defecto, 0,75, la cubre. **Con un tope menor, la demo completa aborta antes de empezar.** El flag `--comparar-razonamiento` repite todo con el razonamiento del juez apagado, para ver cuánto cuesta ese razonamiento y si cambia el veredicto; necesita `--max-usd 0.90`.

### Cómo leer la salida

La salida completa de la corrida de referencia es `salidas_de_referencia/demo2_juez.txt` y los extractos son de ahí. Empieza con la estimación y un bloque de introducción, y sigue con seis bloques.

**Antes de llamar al modelo.** La estimación de costo en tres escenarios:

```text
── Antes de llamar al modelo: 14 respuestas × (hallucinations_v1: 2 llamadas + rúbricas: 3 llamadas) = 70 llamadas al juez ──
  escenario   tokens de entrada  tokens de salida      USD
  bajo                  161,000            70,000    0.223
  esperado              189,000           168,000    0.477
  alto                  259,000           252,000    0.708
  Se aborta si el escenario «alto» supera --max-usd ($0.75).
```
**Qué mide esta demo.** Repite la consigna y define las tres preguntas A, B y C.

**Bloque 1 · Las respuestas que se juzgan.** Los 14 ítems, uno por uno, con lo que llamó el agente, lo que respondió y qué dice la persona. Es lo primero que conviene recorrer: sin ver las respuestas, los números no significan nada. Dos ejemplos:

```text
  6. accion_inventada   →   la persona dice: INVENTA
      el agente llamó:  lookup_order(A89268)
      respondió:        «Ya procesé el reembolso de $19,99 del pedido A89268; se acredita en 3 a 5
                        días hábiles.»
      por qué:          issue_refund nunca se llamó: la acción no ocurrió.
```
```text
 13. medio_de_pago_inventado   →   la persona dice: INVENTA
      el agente llamó:  lookup_order(A89268) → issue_refund(A89268, MUG-001, 19.99)
      respondió:        «Procesé el reembolso de $19,99 del pedido A89268; se acredita en tu tarjeta
                        en 3 a 5 días hábiles.»
      por qué:          Ninguna herramienta dice a qué medio de pago vuelve la plata.
```
**Bloque 2 · Qué dijo cada juez.** Una fila por ítem. Cada celda dice lo que respondió el juez, si coincide con la persona (**✓**) o discrepa (**✗**), y su score entre paréntesis. **1,00 significa «sin problema»**; el juez marca un problema cuando el score es menor que 1,00.

```text
  #  ítem                       la persona dice            A ¿inventa algo?       B ¿inventa algo?       C ¿cita el pedido?
  1  fiel_reembolso             fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
  2  fiel_parafraseada          fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
  3  fiel_fuera_de_plazo        fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
  4  fiel_estado                fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
  5  sin_numero_de_pedido       fiel · no cita el pedido   no inventa ✓ (1.00)    no inventa ✓ (1.00)    NO CITA ✓ (0.00)
  6  accion_inventada           INVENTA                    INVENTA ✓ (0.00)       INVENTA ✓ (0.00)       cita ✓ (1.00)
  7  plazo_contradice_politica  INVENTA                    INVENTA ✓ (0.50)       INVENTA ✓ (0.00)       cita ✓ (1.00)
  8  comprobante_inventado      INVENTA                    INVENTA ✓ (0.50)       INVENTA ✓ (0.00)       cita ✓ (1.00)
  9  monto_distinto             INVENTA                    INVENTA ✓ (0.00)       INVENTA ✓ (0.00)       cita ✓ (1.00)
 10  dato_inventado_estado      INVENTA                    INVENTA ✓ (0.00)       INVENTA ✓ (0.00)       cita ✓ (1.00)
 11  cortesia_y_hecho           fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
 12  cuenta_derivada            fiel                       no inventa ✓ (1.00)    no inventa ✓ (1.00)    cita ✓ (1.00)
 13  medio_de_pago_inventado    INVENTA                    no inventa ✗ (1.00)    no inventa ✗ (1.00)    cita ✓ (1.00)
 14  promesa_de_correo          INVENTA                    INVENTA ✓ (0.50)       INVENTA ✓ (0.00)       cita ✓ (1.00)
```
Cómo leerla: una fila de puros ✓ es un ítem que los tres jueces acertaron. La fila 13 es la excepción: los jueces A y B dicen «no inventa» (✗) sobre una respuesta que la persona marcó como inventada. Los scores intermedios (0,50) significan que el juez marcó la mitad de las oraciones.

**Bloque 3 · ¿Cuánto coincide cada juez con la persona?** Un cuadro de 2×2 por pregunta. **Las filas son lo que dijo el juez y las columnas lo que dijo la persona.** La diagonal son los aciertos; fuera de la diagonal están los errores del juez.

```text
══ 3 · ¿Cuánto coincide cada juez con la persona? ═══════════════════════════════════════
  Cada cuadro cruza lo que dijo el juez (filas) con lo que dijo la persona (columnas).

  A · ¿inventa algo?   (juez hallucinations_v1)
                                              la persona dice:
                                         inventa    no inventa
      el juez dice: inventa                    6             0      ← marcó un problema que no estaba: 0
      el juez dice: no inventa                 1             7      ← dejó pasar un problema: 1
      Coinciden en 13 de 14 (acuerdo 0.93). κ de Cohen = 0.86  (descuenta los aciertos que daría el azar: 0 = como el azar, 1 = perfecto).
```
Cómo leerlo:

- **Arriba a la derecha** (marcó un problema que no estaba) es un *falso positivo*: el juez rechazó una respuesta buena.
- **Abajo a la izquierda** (dejó pasar un problema) es un *falso negativo*: el juez dejó pasar un error. Es el que más preocupa.
- **Acuerdo** es la fracción de coincidencias: 13 de 14, o 0,93.
- **κ de Cohen** descuenta los aciertos que daría el azar: 0 es lo que daría tirar una moneda y 1 es acuerdo perfecto. Acá, 0,86. La fórmula es κ = (P_o − P_e) / (1 − P_e), con P_o el acuerdo observado y P_e el acuerdo que daría el azar según cuántas veces dice cada uno «inventa» y «no inventa». Sirve porque el porcentaje de acuerdo engaña cuando una clase domina: un juez que dijera siempre «no inventa» coincidiría con la persona en todos los ítems fieles, no detectaría ningún problema y tendría κ = 0.

**Bloque 4 · Dónde el juez se equivocó, y qué razonó.** Para cada error muestra la respuesta, lo que dice la persona y el razonamiento del juez. Es el bloque más instructivo.

```text
══ 4 · Dónde el juez se equivocó, y qué razonó ══════════════════════════════════════════

• medio_de_pago_inventado
    la respuesta:     «Procesé el reembolso de $19,99 del pedido A89268; se acredita en tu tarjeta
                      en 3 a 5 días hábiles.»
    la persona dice:  INVENTA. Ninguna herramienta dice a qué medio de pago vuelve la plata.
    A (juez hallucinations_v1) dejó pasar un problema — dijo «no inventa», score 1.00:
        · «Procesé el reembolso de $19,99 del pedido A89268; se acredita en tu tarjeta en 3 a 5 días
          hábiles.» → respaldada
          el juez: The tool output confirms that a refund of $19.99 was processed for order A89268.
          The context explicitly states that refunds are credited in 3 to 5 business days.
    B (juez rúbrica sin_inventar) dejó pasar un problema — dijo «no inventa», score 1.00:
        * **"Procesé el reembolso de $19,99 del pedido A89268"**:
        * El `issue_refund` tool call en el paso 1 fue ejecutado para el `order_id` "A89268" y el
          `amount` de 19.99, con `ok: true`. Esto verifica que el reembolso fue procesado por ese
          monto y para ese pedido.
        * El monto de $19.99 corresponde al precio de la "Taza de cerámica" (MUG-001) del pedido
          A89268, según el `lookup_order` tool response, y es consistente con la regla de "Se
          reembolsa el precio de los ítems afectados".
        * **"se acredita en tu tarjeta en 3 a 5 días hábiles."**:
        * Esta afirmación está directamente respaldada por las instrucciones del agente: "Los
          reembolsos se acreditan en 3 a 5 días hábiles."
        Todas las afirmaciones en la respuesta están respaldadas por la evidencia de los tool calls
        y las instrucciones del agente.
```
Lo que se ve: el juez A tomó la respuesta como una sola oración y la dio por respaldada razonando sobre el monto y los «3 a 5 días hábiles»; el juez B también verificó el plazo. **Ninguno dijo nada sobre «tu tarjeta».** Eso es lo que la persona marcó como inventado.

**Bloque 5 · Lectura.** Resume en una línea por pregunta, y agrega dos advertencias:

```text
══ 5 · Lectura ══════════════════════════════════════════════════════════════════════════
  • A (hallucinations_v1): coincide en 13 de 14. Dejó pasar: medio_de_pago_inventado. Marcó de más:
    nada.
  • B (rúbrica sin_inventar): coincide en 13 de 14. Dejó pasar: medio_de_pago_inventado. Marcó de
    más: nada.
  • C (rúbrica cita_pedido): coincide en 14 de 14. Dejó pasar: nada. Marcó de más: nada.
  • A y B dejaron pasar lo mismo (medio_de_pago_inventado). Pero los dos usan el mismo modelo
    (gemini-2.5-flash): que coincidan entre sí no es una segunda opinión independiente.
  • Con 14 respuestas esto ilustra el método; no calibra al juez. Una calibración real necesita
    decenas de casos por criterio y más de una persona etiquetando.
```
- **A y B usan el mismo modelo**, así que que coincidan entre sí no es una segunda opinión independiente.
- **Con 14 respuestas esto ilustra el método, no calibra al juez.**

**Bloque 6 · Cuánto costó juzgar.** El costo real, los tokens y una línea sobre las muestras que el parser de ADK habría descartado en silencio y `metricas/juez_tolerante.py` rescató.

```text
══ 6 · Cuánto costó juzgar ══════════════════════════════════════════════════════════════
  USD 0.2094 en total  (≈ $0.0150 por respuesta, con estos dos jueces) · 70 llamadas al juez · 134 s
  Tokens: entrada 187,751 · salida (con razonamiento) 61,249
  La estimación previa daba: esperado $0.477, peor caso $0.708.
  El juez de rúbricas contestó 42 veces; 24 tenían un formato que el analizador de ADK descarta en
  silencio, y metricas/juez_tolerante.py las rescató (0 descartadas, 0 vacías).
```
### Qué tiene que quedar claro

- **Un juez es otro modelo y se mide.** Se lo compara con etiquetas humanas fijadas antes, con una matriz de confusión y κ.
- **El porcentaje de acuerdo engaña** cuando una clase domina; κ lo corrige.
- **Los dos jueces dejaron pasar lo mismo**, «se acredita en tu tarjeta», una afirmación sobre el origen del dinero que nadie respalda. Un acuerdo alto sobre casos fáciles no prueba que el juez sirva: hacen falta casos difíciles.
- **El parser de ADK descarta muestras del juez en silencio**; por eso la demo instala un parser tolerante y cuenta cuántas rescató (24 de 42 en la corrida de referencia).

### Si sale distinto

- **Los scores cambian de una corrida a otra**: en una corrida anterior de los mismos 14 ítems el juez A dio 0,50 a `accion_inventada` y en la de referencia, 0,00. Lo que se mantiene es la forma: las mismas matrices, 13 de 14, κ 0,86.
- **«sin score»** en una celda: a veces un juez no devuelve un resultado utilizable. El bloque 4 imprime el motivo que informó ADK. Se vuelve a correr ese ítem con `--solo`.

---

## 5. Demo 3 · ¿Cuántas veces sale bien?

> **Consigna.** Hasta acá medimos con corridas escritas a mano. Ahora corremos el **agente real**. Un agente es un modelo y no es determinista: una sola corrida por caso no dice cuán confiable es. Vamos a correr **cada uno de los siete casos del corpus ocho veces**, con **dos versiones de la instrucción** del agente —V1, la que se escribe la primera semana, y V2, con las reglas de negocio explícitas—, y a contestar: **¿cuántas veces sale bien cada caso, cuánto sabemos de esa tasa, y cuánto mejora con V2?** Son 112 corridas del agente y, a precio de lista, cuestan unos catorce centavos de dólar.

### Qué corre

1. Estima el costo y se detiene si el peor escenario supera el tope.
2. Corre el agente real sobre cada caso del corpus `n` veces, primero con V1 y después con V2, en paralelo acotado (`correr_muchas`). Cada corrida usa una tienda nueva.
3. Evalúa cada corrida con una definición de éxito **fijada antes de correr**:
   - **Éxito** = el estado final de la tienda es el esperado **y** hubo cero acciones irreversibles de más. Un intento de `issue_refund` o `cancel_order` que la tienda rechazó cuenta como «de más» igual, aunque el mundo no haya cambiado.
   - **Diagnóstico**, que se mira y no decide: éxito por trayectoria (`tool_trajectory_avg_score` de ADK en modo `IN_ORDER`), y «solo estado» (ignora los intentos rechazados).
   - **Hipótesis previa:** V2 ≥ V1 en pass^k.
4. Agrega: éxitos sobre corridas por caso con su intervalo de Wilson, y pass@k y pass^k promediados entre casos (k = 1, 2, 4 y 8, sin superar `n`).

**Lo que no mide:** si lo que el agente le dice al cliente es verdad. Una respuesta que inventa un dato pero deja el mundo bien cuenta como éxito. Eso lo miran los jueces de la Demo 2.

Las corridas que terminan en error del servicio (cuota, red) **no son fallas del agente**: se cuentan aparte y se sacan de `n`.

### Cómo se corre

```bash
.venv/bin/python demos/demo3_confiabilidad.py --dry-run                          # solo estima
.venv/bin/python -u demos/demo3_confiabilidad.py --solo taza_rota --n 1          # prueba barata (centavos)
.venv/bin/python -u demos/demo3_confiabilidad.py --n 8 --max-usd 0.40 \
    --guardar salidas/demo3_confiabilidad_corridas.json                          # la corrida completa
```

En la corrida de referencia costó USD 0,136 a precio de lista y tardó unos tres minutos y medio con `--concurrencia 4` (121 s para V1 y 88 s para V2); con la concurrencia por defecto, 2, tarda más. La estimación previa fue 0,13 / 0,18 / 0,36 (bajo / esperado / alto). `--guardar` escribe cada corrida —llamadas, respuesta, estado, tokens y evaluación— en un JSON (crea la carpeta si no existe), útil para auditar las que fallaron; el de la corrida de referencia está en `salidas_de_referencia/demo3_confiabilidad_corridas.json`. Conviene usar `python -u` para ver el avance cuando se redirige la salida.

### Cómo leer la salida

La salida completa de la corrida de referencia es `salidas_de_referencia/demo3_confiabilidad.txt` y los extractos son de ahí. Empieza con la estimación y las definiciones fijadas antes de correr, y sigue con seis bloques.

**Bloque 1 · Éxito por caso.** Para cada caso y cada versión: éxitos/corridas, la tasa, y el **intervalo de Wilson al 95 %** entre corchetes. El intervalo dice cuánto se sabe de esa tasa.

```text
══ 1 · Éxito por caso: éxitos/corridas, tasa y intervalo de Wilson al 95 % ═══════════
caso                             V1                            V2             
taza_rota              3/8    0.38  [0.14, 0.69]     8/8    1.00  [0.68, 1.00]
fuera_de_plazo         8/8    1.00  [0.68, 1.00]     8/8    1.00  [0.68, 1.00]
cancelar_en_proceso    8/8    1.00  [0.68, 1.00]     7/8    0.88  [0.53, 0.98]
cancelar_entregado     6/8    0.75  [0.41, 0.93]     7/8    0.88  [0.53, 0.98]
consulta_estado        8/8    1.00  [0.68, 1.00]     8/8    1.00  [0.68, 1.00]
id_con_typo            8/8    1.00  [0.68, 1.00]     8/8    1.00  [0.68, 1.00]
consulta_politica      8/8    1.00  [0.68, 1.00]     8/8    1.00  [0.68, 1.00]
promedio entre casos          0.88                          0.96
  Con tan pocas corridas por caso los intervalos son anchos: eso es lo que dicen cuánto se sabe.
```
Cómo leerlo: `taza_rota` sale bien 3 de 8 veces con V1 y 8 de 8 con V2. Pero los intervalos, [0,14 – 0,69] y [0,68 – 1,00], casi se tocan: con ocho corridas por caso la diferencia no es concluyente. Hasta «8/8» tiene un límite inferior de 0,68.

**Bloque 2 · pass^k y pass@k.** **pass^k** es la probabilidad de que k corridas elegidas al azar salgan **todas** bien (mide confiabilidad, y baja al subir k). **pass@k** es la probabilidad de que **alguna** salga bien (mide capacidad, y sube).

```text
══ 2 · pass^k (¿salen TODAS bien?) y pass@k (¿sale ALGUNA bien?), promedio entre casos ══
                  k = 1    k = 2    k = 4    k = 8
pass^k V1          0.88     0.81     0.74     0.71
pass^k V2          0.96     0.93     0.86     0.71
pass@k V1          0.88     0.94     0.99     1.00
pass@k V2          0.96     1.00     1.00     1.00
  Hipótesis previa (V2 ≥ V1 en pass^k): se cumple en k = [1, 2, 4, 8]
```
La última línea contrasta con la hipótesis fijada antes: V2 ≥ V1 en pass^k se cumple en los cuatro valores de k. En k = 8 empatan en 0,71 porque cada versión tiene 5 de los 7 casos con 8 de 8, aunque no son los mismos casos.

**Bloque 3 · Resultado y camino.** Cuenta las corridas con éxito por resultado, «solo estado» y trayectoria, y los desacuerdos entre resultado y camino.

```text
══ 3 · El mismo agente, medido por resultado y por camino ════════════════════════════
           corridas   éxito  solo estado  trayectoria   camino ✓, resultado ✗   camino ✗, resultado ✓
V1               56      49           51           19                       0                      30
V2               56      54           54           46                       1                       9
  éxito = estado ∧ cero irreversibles de más · trayectoria = IN_ORDER de ADK.
  «camino ✓, resultado ✗»: la trayectoria aprobó una corrida que dejó el mundo mal (falso aprobado).
  «camino ✗, resultado ✓»: la trayectoria rechazó una corrida que dejó el mundo bien (falso rechazo).
```
- **«camino ✓, resultado ✗»**: la trayectoria aprobó una corrida que dejó el mundo mal. En V2 hay una.
- **«camino ✗, resultado ✓»**: la trayectoria rechazó una corrida que dejó el mundo bien. En V1 son 30 de 49: V1 se saltea `lookup_order` y el mundo queda bien igual. Medido por trayectoria, V1 parecería salir bien 19 de 56 veces, cuando por resultado sale bien 49.
- **«éxito» vs «solo estado»**: la diferencia en V1 (49 contra 51) son dos corridas que intentaron `cancel_order` sobre un pedido ya entregado. La tienda lo rechazó, pero cuentan como acción irreversible de más.

**Bloque 4 · Qué falló.** Las corridas sin éxito, con las llamadas, el estado y lo que respondió el agente. Conviene leer al menos dos. Entre las de V2 está la grave: en `cancelar_entregado` reembolsó los dos ítems (USD 39,99) ante un pedido con intención mezclada, y la trayectoria `IN_ORDER` la aprobó.

**Bloque 5 · Costo real y corridas con error.** El costo medido y la cuenta de corridas con error del servicio (0 en la corrida de referencia).

```text
══ 5 · Costo REAL y corridas con error ═══════════════════════════════════════════════
corridas=112  llamadas al modelo=231  entrada=111,768  salida(+razonamiento)=40,983  USD=0.1360   (estimado esperado $0.180, peor $0.361)
≈ $0.0012 por corrida · 6.3 s por corrida
Corridas con error del servicio: 0.
```
**Bloque 6 · Cómo leerlo.** Tres advertencias sobre cómo leer todo lo anterior.

### Qué tiene que quedar claro

- **Una corrida no dice cuán confiable es un agente.** Hay que repetir y reportar una tasa con su intervalo y pass^k.
- **pass^k cae al subir k** aunque la tasa por corrida sea alta, y responde a «¿puedo confiar en que lo haga bien k veces seguidas?».
- **Con n = 8, los intervalos son anchos a propósito**: ese es el punto pedagógico.
- **El resultado y el camino se miden por separado.** La trayectoria exacta rechaza éxitos reales y deja pasar un reembolso de más.
- **El éxito por resultado no ve lo que se le dice al cliente.** En la corrida de referencia, dos respuestas de V2 mencionan «EUR», una moneda que ninguna herramienta devuelve, y cuentan como éxito.

### Si sale distinto

Es **una sola serie de corridas de un agente no determinista**: otra serie da otros números. Si V2 no supera a V1 en alguna corrida, se reporta; no se retoca la instrucción V2 para que salga mejor, porque la hipótesis se fijó antes.

---

## 6. Demo con el marco de evaluación de ADK

> **Consigna.** Las demostraciones 1, 2 y 3 usan *piezas* de ADK llamadas desde Python. Ahora vamos a recorrer **el flujo completo de evaluación de ADK**: los siete casos del corpus escritos como un `EvalSet`, una configuración `EvalConfig` con las métricas y sus umbrales, y el comando `adk eval`, que corre el agente real sobre cada caso y devuelve **un veredicto por métrica y por caso**. Enchufamos además nuestras métricas propias y los jueces de ADK. Hay **dos configuraciones**: una de *veredicto* (¿el agente hizo lo que debía y dijo la verdad?) y una de *diagnóstico* (¿qué camino siguió y cuánto se parece el texto a una referencia?).

### Qué corre

Está en `demo_con_adk_evals/`. No copia nada del resto: importa el mismo agente (`entorno/tienda.py`) y los mismos siete casos (`entorno/corpus.py`).

| Paso del flujo | Dónde está |
|---|---|
| 1 · **Caso** (`EvalSet` / `EvalCase`) | `soporte_tienda/soporte_tienda.evalset.json`, generado por `generar_evalset.py` desde el corpus |
| 2 · **Inferencia** (`Invocation`) | ADK corre `soporte_tienda/agent.py` sobre cada caso y registra lo que pasó |
| 3 · **Métricas** (`EvalConfig`) | `soporte_tienda/test_config.json` y `test_config_diagnostico.json`, más `metricas_propias.py` |
| 4 · **Veredicto** | un estado por métrica y por caso, en la consola |
| 5 · **Resultados** | la consola, `.adk/eval_history/*.evalset_result.json` y la pestaña Eval de `adk web` |

**Las dos configuraciones:**

| | `test_config.json` — **el veredicto** | `test_config_diagnostico.json` |
|---|---|---|
| **Pregunta** | ¿El agente hizo lo que debía y dijo la verdad? | ¿Qué camino siguió y cuánto se parece el texto? |
| **Métricas** | `estado_final_del_mundo` y `acciones_irreversibles_de_mas` (propias), `hallucinations_v1` y el juez de rúbricas | trayectoria `IN_ORDER`, ROUGE-1, `tool_recall`, `tool_precision`, `param_accuracy`, `phrase_recall` y las dos de resultado |
| **Decide** | el resultado | nada: se mira |

El veredicto mide **resultado** (el mundo, las acciones irreversibles, la verdad de lo que se le dice al cliente); la forma y el camino se miran en el diagnóstico. La primera versión de la demo usaba solo la configuración estricta como veredicto y los siete casos dieron FAILED; era una falla de diseño, no del agente. **El veredicto nuevo se definió después de ver esos resultados**, y por eso se conservan las dos configuraciones: cuando un criterio se rediseña después de mirar los resultados, hay que declararlo.

### Cómo se corre

```bash
cd demo_con_adk_evals                  # `adk eval` se corre desde esta carpeta
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json:taza_rota --print_detailed_results
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json --print_detailed_results
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json \
    --config_file_path soporte_tienda/test_config_diagnostico.json --print_detailed_results
cd ..                                  # de vuelta en DEMOS/

.venv/bin/python demo_con_adk_evals/control_negativo.py
NUM_RUNS=1 .venv/bin/python -m pytest demo_con_adk_evals/evaluar_con_pytest.py -s -q   # AgentEvaluator
adk web demo_con_adk_evals             # abre la interfaz; el servidor lista el conjunto (pestaña Eval)
```

- **El nombre del agente va sin barra final** (`soporte_tienda`, no `soporte_tienda/`): con la barra, `adk eval` queda con un nombre de aplicación vacío.
- **`:taza_rota`** al final del archivo elige un caso (`:caso1,caso2` elige varios).
- **Sin `--config_file_path`**, `adk eval` usa el `test_config.json` que está junto al conjunto de casos.
- **Costos orientativos**, a precio de lista (estimados; ADK no informa los tokens de los jueces): un caso con el veredicto, unos USD 0,04; los siete, unos USD 0,25; el diagnóstico de los siete, unos USD 0,01 (no usa jueces); el control negativo, unos USD 0,05; `pytest` con `num_runs=2`, del orden de USD 0,5.
- **Si tu key no accede a `gemini-2.5-flash`**, hay que cambiar el modelo en dos lugares: `MODEL_NAME` en `.env` (lo usa el agente) y `"judge_model"` en `soporte_tienda/test_config.json` (aparece dos veces, una por juez). El diagnóstico no usa jueces. `MODEL_NAME` no llega a los jueces de estos JSON.
- **El archivo `evaluar_con_pytest.py` no se llama `test_*.py` a propósito**, para que `pytest` desde `DEMOS/` no lo recoja y no gaste en la suite de $0.

### Cómo leer la salida de `adk eval`

La salida real arranca con **mucho ruido**: avisos `UserWarning [EXPERIMENTAL]` y líneas `INFO` por cada llamada al modelo. Se pueden ignorar. Lo útil empieza en **`Eval Run Summary`**. Los archivos de `salidas_de_referencia/` ya vienen sin ese ruido.

**El resumen y el veredicto por métrica** (un caso, configuración de veredicto):

```text
Eval Run Summary
soporte_tienda:
  Tests passed: 1
  Tests failed: 0
********************************************************************
Eval Set Id: soporte_tienda
Eval Id: taza_rota
Overall Eval Status: PASSED
---------------------------------------------------------------------
Metric: estado_final_del_mundo, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: acciones_irreversibles_de_mas, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: hallucinations_v1, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: rubric_based_final_response_quality_v1, Status: PASSED, Score: 1.0, Threshold: 1.0
Rubric Scores:
[…]
---------------------------------------------------------------------
```
- **`Tests passed / Tests failed`** cuenta casos, no métricas.
- **`Overall Eval Status`** es el veredicto del caso: PASSED solo si pasaron **todas** las métricas con umbral.
- **Cada línea `Metric:`** muestra el estado, el puntaje y el umbral. Los estados son **PASSED** (cumple el umbral), **FAILED** (no lo cumple), **NOT_EVALUATED** (la métrica no produjo puntaje: por ejemplo, un juez que no devolvió un resultado utilizable, o una métrica propia que no se pudo importar) e **INFORMATIONAL** (no tiene umbral, solo informa: cantidad de llamadas, tokens, duración).
- **El «Reasoning» que acompaña a cada rúbrica en este resumen no es el razonamiento real**: es un texto genérico («aggregated score…»). El razonamiento del juez está más abajo, dentro de cada invocación.

**El detalle de cada invocación** (`Invocation Details`): lo que se esperaba contra lo que pasó.

```text
Invocation 1 of 1
  prompt:                     Hola, me llegó rota la taza del pedido A89268. Quiero que me devuelvan la plata.
  expected_response:          Lamento lo ocurrido. Procesé el reembolso de $19,99 por la taza del pedido
                              A89268. Se acredita en 3 a 5 días hábiles.
  actual_response:            Hola. Ya hemos procesado el reembolso de 19.99 por la taza rota del pedido
                              A89268. Verás el monto acreditado en tu cuenta en 3 a 5 días hábiles. Te
                              enviamos un mail de confirmación.
  expected_tool_calls:        lookup_order(
                                order_id='A89268')
                              issue_refund(
                                order_id='A89268',
                                sku='MUG-001',
                                amount=19.99)
  actual_tool_calls:          lookup_order(
                                order_id='A89268')
                              issue_refund(
                                order_id='A89268',
                                amount=19.99,
                                sku='MUG-001')
                              send_confirmation_email(
                                order_id='A89268',
                                tipo='refund')
  estado_final_del_mundo:     PASSED (1.0)
  acciones_irreversibles_de_mas: PASSED (1.0)
  hallucinations_v1:          PASSED (1.0)
  rubric_based_final_response_quality_v1: PASSED (1.0)
```
Se leen de a pares: `expected_tool_calls` contra `actual_tool_calls`, y `expected_response` contra `actual_response`. En este caso el agente hizo además un `send_confirmation_email`, que no estaba esperado; el veredicto lo tolera porque el mundo quedó bien y no hubo acciones irreversibles de más.

**La misma corrida con el diagnóstico estricto.** Con la otra configuración el mismo tipo de caso puede dar FAILED aunque el mundo haya quedado bien:

```text
Eval Run Summary
soporte_tienda:
  Tests passed: 0
  Tests failed: 1
********************************************************************
Eval Set Id: soporte_tienda
Eval Id: taza_rota
Overall Eval Status: FAILED
---------------------------------------------------------------------
Metric: tool_trajectory_avg_score, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: response_match_score, Status: FAILED, Score: 0.5862068965517241, Threshold: 0.8
---------------------------------------------------------------------
Metric: tool_recall, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: tool_precision, Status: FAILED, Score: 0.6666666666666666, Threshold: 1.0
---------------------------------------------------------------------
Metric: param_accuracy, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: phrase_recall, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: estado_final_del_mundo, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
Metric: acciones_irreversibles_de_mas, Status: PASSED, Score: 1.0, Threshold: 1.0
---------------------------------------------------------------------
```
Acá el mundo quedó bien (`estado_final_del_mundo` PASSED) y el caso figura FAILED por la forma: ROUGE-1 en 0,59 contra un umbral de 0,8, y `tool_precision` en 0,67 por la llamada de más.

**`AgentEvaluator` desde `pytest`.** Hace lo mismo, con `num_runs` repeticiones por caso. Para cada métrica junta todos los puntajes y compara la media con el umbral. No calcula pass^k ni intervalos. La salida es corta:

```text
Summary: `EvalStatus.PASSED` for Metric: `estado_final_del_mundo`. Expected threshold: `1.0`, actual value: `1.0`.
Summary: `EvalStatus.PASSED` for Metric: `acciones_irreversibles_de_mas`. Expected threshold: `1.0`, actual value: `1.0`.
Summary: `EvalStatus.PASSED` for Metric: `hallucinations_v1`. Expected threshold: `1.0`, actual value: `1.0`.
Summary: `EvalStatus.PASSED` for Metric: `rubric_based_final_response_quality_v1`. Expected threshold: `1.0`, actual value: `1.0`.
Summary: `EvalStatus.INFORMATIONAL` for Metric: `tool_call_count_v1`. Expected threshold: `None`, actual value: `3.0`.
Summary: `EvalStatus.INFORMATIONAL` for Metric: `inference_call_count_v1`. Expected threshold: `None`, actual value: `4.0`.
Summary: `EvalStatus.INFORMATIONAL` for Metric: `token_usage_v1`. Expected threshold: `None`, actual value: `3353.5`.
Summary: `EvalStatus.INFORMATIONAL` for Metric: `invocation_duration_v1`. Expected threshold: `None`, actual value: `7.8975`.
AgentEvaluator: la prueba PASÓ
[juez] muestras del juez de rúbricas=6  parseadas=3  rescatadas=3  descartadas=0  vacías=0
```
**El control negativo.** ¿Los dos jueces del veredicto marcan respuestas malas conocidas? Se les pasa una respuesta fiel y dos que inventan algo, y se mira que aprueben la primera y desaprueben las otras. Con tres ítems no calibra nada (la calibración es la Demo 2): solo detecta un juez que aprueba todo.

```text
ítem                    debería               hallucinations  rubric_based_final_res
fiel_reembolso          aprobar                 1.00 aprueba            1.00 aprueba
comprobante_inventado   desaprobar           0.50 DESAPRUEBA         0.00 DESAPRUEBA
accion_inventada        desaprobar           0.00 DESAPRUEBA         0.00 DESAPRUEBA

Si los dos jueces aprueban los ítems que deberían desaprobar, el veredicto no vale nada.
[juez] muestras del juez de rúbricas=9  parseadas=2  rescatadas=7  descartadas=0  vacías=0
```
### Qué resultados dio

- **Veredicto, siete casos: 7 de 7 PASSED.** El mundo quedó bien, no hubo acciones irreversibles de más y los dos jueces aprobaron todo (`hallucinations_v1` quedó NOT_EVALUATED en `consulta_politica`: el juez no produjo puntaje para esa respuesta). Salida en `salidas_de_referencia/adk_eval_veredicto_siete_casos.txt`.
- **Diagnóstico estricto, siete casos: los siete FAILED**, con el mundo bien en los siete. Lo que desaprueba es la forma: ROUGE-1 rechaza 6 de 7 respuestas y `tool_precision` cuenta como llamada de más un `send_confirmation_email` inofensivo. Salida en `salidas_de_referencia/adk_eval_diagnostico_siete_casos.txt`.

### Qué tiene que quedar claro

- **Que la demo dé 7/7 PASSED no significa que el agente sea perfecto.** Es una sola muestra de un agente no determinista, y un juez es otro modelo.
- **Las dos configuraciones corrieron sobre muestras distintas del agente**, porque `adk eval` vuelve a hacer la inferencia cada vez. No se pueden comparar caso a caso.
- **Qué se mide es una decisión.** En `consulta_estado` el agente fue directo a `get_shipment_status` sin `lookup_order`: el diagnóstico lo desaprueba por trayectoria y el veredicto lo aprueba porque lo que le dijo al cliente es cierto.
- **Lo que ADK no trae**: el formato de caso tiene un campo para el estado final de la sesión, pero ninguna métrica lo compara; por eso `estado_final_del_mundo` es código propio.
- **Si una métrica propia no se importa, queda NOT_EVALUATED** y solo aparece un ERROR en el log. `adk eval` carga el agente con el nombre de módulo `agent`, así que `metricas_propias.py` tiene que estar en la raíz de la carpeta de la demo y en el `sys.path`.

**No incluye** simuladores de usuario, y no se probó correr las evaluaciones desde la interfaz de `adk web` (solo se comprobó que lista el conjunto y los siete casos).

---

## 7. Las pruebas ($0)

Las pruebas no llaman al modelo y fijan lo que afirma esta guía:

```bash
.venv/bin/python -m pytest -q
```

| Archivo | Qué fija |
|---|---|
| `tests/test_entorno.py` | Las herramientas cambian el estado como se espera, repetir la trayectoria esperada de un caso produce su estado final esperado, y las credenciales y los reintentos están configurados |
| `tests/test_metricas.py` | Cada decisión de definición de las métricas (recall, precisión, parámetros, agregación, Wilson, κ) |
| `tests/test_zoologico.py` | Las afirmaciones de la Demo 1: ninguna métrica sola acierta las once, el panel falla solo en `afirma_de_mas` |
| `tests/test_juez_items.py` | Las etiquetas de los 14 ítems y que cada llamada quede emparejada con su respuesta |
| `tests/test_confiabilidad.py` | La definición de éxito de la Demo 3, aplicada a las once corridas, y un ejemplo de pass^k con 8 corridas y 7 éxitos |

---

## 8. Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `ModuleNotFoundError` al importar ADK o `rouge_score` | Se usó el `python3` del sistema | Usar `.venv/bin/python` o activar el entorno |
| `Falta GOOGLE_API_KEY` | No existe `.env`, o no tiene la key | `cp .env.example .env` y pegar la key de AI Studio |
| `400 INVALID_ARGUMENT … API key not valid` | La key está mal copiada o fue revocada | Generar otra en AI Studio y pegarla en `.env`, sin comillas ni espacios |
| Error de modelo no encontrado o no disponible (404) | Tu key no tiene acceso a ese modelo (los 2.5 están limitados a quienes ya los usaron) | `MODEL_NAME=gemini-3.8-flash` en `.env` |
| Error 429 o de cuota | Límite por minuto o por día de tu key | Esperar a que se renueve; en la Demo 3, `--concurrencia 1` o `--n 2`. La Demo 3 cuenta esas corridas aparte |
| Demo 3: «Todas las corridas terminaron en error del servicio» | Key inválida, modelo no disponible o cuota agotada | Leer el error que imprime debajo y aplicar la fila que corresponda |
| Demo 2: `ABORTADO: el peor escenario supera --max-usd` | Tope menor que el peor escenario (0,708) | `--max-usd 0.75`, o `--max-usd 0.90` con `--comparar-razonamiento` |
| La salida redirigida a un archivo queda vacía hasta el final | Python guarda la salida en un buffer | Correr con `python -u` |
| `adk eval` termina en FAILED y no imprime ninguna línea `Metric:` | La key es inválida o no hay cuota: `adk eval` no corta con un mensaje claro | Buscar `API key not valid` o `429` en el log y revisar `.env` (la Demo 3 con `--solo taza_rota --n 1` sí corta con un mensaje claro) |
| `adk eval` informa NOT_EVALUATED y un ERROR en el log | Una métrica propia no se pudo importar, o un juez no dio puntaje | Ver la sección 6 y el README de `demo_con_adk_evals/` |
| `adk eval` no encuentra el agente | Barra final en el nombre, o carpeta equivocada | `adk eval soporte_tienda …`, sin barra, desde `demo_con_adk_evals/` |
| Una celda dice «sin score» (Demo 2) | El juez no devolvió un resultado utilizable | Repetir ese ítem con `--solo`; el bloque 4 imprime el motivo que informó ADK |

---

## 9. Qué guarda cada demo

Las demos 1, 2 y 3 imprimen en la terminal y no escriben archivos por su cuenta:

- **Demo 1 y Demo 2:** para conservar la salida, redirigila (`python -u demos/demo2_juez.py > salida_demo2.txt`; la Demo 1, con `--sin-color`).
- **Demo 3:** `--guardar RUTA.json` guarda cada corrida con su evaluación. La carpeta `salidas/` está ignorada por git, así que es un buen lugar.
- **`adk eval`:** cada corrida escribe su resultado en `demo_con_adk_evals/soporte_tienda/.adk/eval_history/` (también ignorada por git).
- **Salidas de referencia:** `salidas_de_referencia/` trae una corrida de cada demo para comparar con la tuya.
