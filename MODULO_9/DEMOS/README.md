# Módulo 9 — Validación y medición de agentes · Demos

Tres demostraciones del módulo y una cuarta que recorre el flujo completo de evaluación de ADK, para correr en tu máquina con una API key gratuita de Google AI Studio. Todas giran alrededor de un mismo agente: el de soporte de una tienda online (una tienda **simulada en memoria**, con seis herramientas, entre ellas `lookup_order` e `issue_refund`). Sobre ese agente se mide, de tres maneras distintas, si hizo lo que debía:

| Demostración | Pregunta | Qué usa | Cuesta |
|---|---|---|---|
| **Demo 1** · `demos/demo1_zoologico.py` | ¿Qué métrica ve qué falla? | Once corridas ya escritas del mismo pedido y todas las métricas del módulo | $0: no llama al modelo |
| **Demo 2** · `demos/demo2_juez.py` | ¿Y quién evalúa al juez? | Los dos jueces de ADK sobre catorce respuestas ya escritas, contra etiquetas humanas | USD 0,21 a precio de lista en la corrida de referencia |
| **Demo 3** · `demos/demo3_confiabilidad.py` | ¿Cuántas veces sale bien? | El agente real sobre los 7 casos, n veces cada uno, con dos versiones de su instrucción (V1 y V2): tasa con intervalo de Wilson, pass@k y pass^k | USD 0,14 a precio de lista con n = 8 |
| **Demo con el marco de ADK** · `demo_con_adk_evals/` | ¿Cómo se ve el flujo completo de ADK? | `EvalSet`, `EvalConfig`, `adk eval`, `AgentEvaluator`, métricas propias y jueces, con el agente real (tiene su propio [README](demo_con_adk_evals/README.md)) | del orden de USD 0,25 por corrida de los siete casos |

La **guía de las demostraciones** ([`guia_demos.md`](guia_demos.md)) explica cada una en detalle: qué corre, cómo leer la salida bloque por bloque y qué tiene que quedar claro. Empezá por su sección 1, que distingue el corpus, el zoológico y los ítems del juez: se parecen y no son lo mismo.

## Puesta en marcha

```bash
cd MODULO_9/DEMOS
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # google-adk[eval]==2.12.0, python-dotenv, pytest
cp .env.example .env                       # y pegar tu API key
```

`.env` define tres variables (`.env` está ignorado por git: **no lo subas a ningún repositorio**):

| Variable | Para qué |
|---|---|
| `GOOGLE_API_KEY` | tu API key de [Google AI Studio](https://aistudio.google.com/apikey) (es gratis) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE`: usa AI Studio con tu key |
| `MODEL_NAME` | opcional: el modelo del agente y de los jueces (por defecto, `gemini-2.5-flash`) |

La versión de ADK está fijada porque las métricas de evaluación cambiaron entre 2.10 y 2.12. Se probó con Python 3.12.

**Un modelo que tu key quizás no tenga.** Google limita los modelos 2.5 a quienes ya los usaron. Si tu key es nueva y la primera llamada falla con un error de modelo no encontrado o no disponible, probá uno más nuevo, por ejemplo `MODEL_NAME=gemini-3.8-flash`. Otro modelo puede tardar más y juzgar distinto: las cifras de referencia y las estimaciones de costo son de 2.5 Flash.

## Qué se puede correr sin gastar nada

Todos los comandos se corren desde `DEMOS/`, con el entorno virtual activado.

```bash
python -m pytest -q                                   # las pruebas: no llaman al modelo
python demos/demo1_zoologico.py                       # Demo 1 (agregar --sin-color para guardar la salida)
python demos/demo2_juez.py --dry-run                  # Demo 2: solo estima el costo, no llama al modelo
python demos/demo3_confiabilidad.py --dry-run         # Demo 3: ídem
```

## Qué llama al modelo (y consume cuota)

| Comando | Qué hace | Costo orientativo, a precio de lista |
|---|---|---|
| `python demos/demo2_juez.py --max-usd 0.75` | Demo 2 completa: los 14 ítems con los dos jueces. Imprime la estimación antes y aborta si el peor escenario supera el tope | USD 0,21 en la corrida de referencia (dos corridas: 0,2114 y 0,2094); la estimación previa daba 0,48 esperado y 0,71 en el peor caso |
| `python demos/demo2_juez.py --solo accion_inventada` | Un solo ítem, para probar | centavos |
| `python demos/demo2_juez.py --comparar-razonamiento --max-usd 0.90` | Repite todo con el razonamiento del juez apagado | el tope previo ronda los USD 0,85 |
| `python -u demos/demo3_confiabilidad.py --n 8 --max-usd 0.60` | Demo 3 completa: 7 casos × 8 corridas × 2 versiones = 112 corridas del agente, sin jueces. Imprime la estimación antes y aborta si el peor escenario supera el tope | USD 0,136 en la corrida de referencia (estimación previa: 0,13 / 0,18 / 0,36 en bajo / esperado / alto) |
| `python -u demos/demo3_confiabilidad.py --solo taza_rota --n 1` | Prueba barata de la Demo 3 | centavos |
| `adk eval` y `AgentEvaluator`, desde `demo_con_adk_evals/` (comandos en su README) | El agente real y los jueces de ADK sobre los siete casos | ≈ USD 0,25 por corrida de los siete casos (estimado: ADK no informa los tokens de los jueces) |

El precio usado en las estimaciones (Gemini 2.5 Flash: USD 0,30 por millón de tokens de entrada y USD 2,50 por millón de salida) está en `metricas/costo.py`. Las estimaciones son eso: estimaciones; el costo real de los jueces se mide con el contador de tokens y se imprime al final. ADK no informa el costo de los jueces por su cuenta.

**Con la capa gratuita no se paga, pero se consume cuota.** Una key gratuita tiene límites por minuto y por día (se ven en [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit)). La Demo 3 completa hace unas 230 llamadas al modelo y la Demo 2, unas 70. Si el servicio contesta 429 o 503, la librería espera y reintenta. Si te pasa seguido, bajá `--concurrencia` a 1 en la Demo 3, usá `--n 2` o esperá a que se renueve la cuota. Más en la sección 2 de la guía.

## Qué hay en cada carpeta

```
DEMOS/
├── guia_demos.md             la guía de las tres demostraciones
├── entorno/                  el mundo que se evalúa
│   ├── tienda.py             la tienda simulada, las seis herramientas, las dos instrucciones del agente
│   │                         (INSTRUCCION_V1 / INSTRUCCION_V2) y cómo se corre un caso contra el modelo
│   ├── corpus.py             los siete casos: mensaje, llamadas esperadas, frases, estado final esperado
│   ├── zoologico.py          las once corridas escritas a mano, con su etiqueta humana fijada antes de medir
│   └── juez_items.py         las catorce respuestas ya escritas para medir al juez, con su etiqueta
├── metricas/                 las métricas
│   ├── planificacion.py      tool_recall, tool_precision, param_accuracy, phrase_recall, acciones irreversibles
│   ├── agregacion.py         promedio, tasa, pass^k, pass@k, intervalo de Wilson, matriz de confusión, κ de Cohen
│   ├── adk_nativo.py         los evaluadores nativos de ADK (trayectoria y ROUGE-1) sobre trazas armadas a mano
│   ├── referencias.py        otras dos convenciones del caso vacío, para compararlas
│   ├── costo.py              estimador de costo y contador de tokens reales
│   └── juez_tolerante.py     parser que rescata muestras del juez de rúbricas que ADK descarta
├── demos/                    Demo 1, Demo 2 y Demo 3
├── demo_con_adk_evals/       el flujo completo de ADK (tiene su propio README)
├── salidas_de_referencia/    la salida de una corrida de cada demo, para comparar con la tuya
└── tests/                    pruebas: entorno, métricas, zoológico, ítems del juez, confiabilidad
```

`conftest.py` agrega esta carpeta al `sys.path` para que las pruebas importen `metricas` y `entorno` sin instalar nada.

`salidas_de_referencia/` trae la salida de una corrida de cada demo (Gemini 2.5 Flash, ADK 2.12.0), con un encabezado que dice el comando. Las de `adk eval` vienen sin los avisos `[EXPERIMENTAL]` y las líneas `INFO` que ADK imprime antes del resumen. La carpeta `salidas/` (sin `_de_referencia`) es donde guardan las tuyas, y git la ignora.

## Resultados de referencia

Son los de una corrida con Gemini 2.5 Flash y ADK 2.12.0. Son **una muestra**: tus números van a ser parecidos en la forma y distintos en el detalle.

### Demo 2

14 ítems, 70 llamadas al juez, 134 segundos.

| Criterio | Verdaderos positivos | Falsos positivos | Falsos negativos | Verdaderos negativos | Acuerdo | κ de Cohen |
|---|---|---|---|---|---|---|
| `hallucinations_v1` → alucina | 6 | 0 | 1 | 7 | 0,93 | 0,86 |
| rúbrica `sin_inventar` → alucina | 6 | 0 | 1 | 7 | 0,93 | 0,86 |
| rúbrica `cita_pedido` → no cita | 1 | 0 | 0 | 13 | 1,00 | 1,00 |

Los dos jueces dejan pasar el mismo ítem, `medio_de_pago_inventado` («se acredita en tu tarjeta»): la persona lo marca como problema porque ninguna herramienta dice a qué medio de pago vuelve el dinero, y los dos jueces lo aprobaron con 1,00. Con 14 ítems esto ilustra el método; no calibra nada.

El juez de rúbricas dio 42 muestras y 24 de ellas tenían un formato que el analizador de ADK descarta en silencio; `metricas/juez_tolerante.py` las rescató (ninguna quedó descartada ni vacía).

### Demo 3

112 corridas del agente real (7 casos × 8 × V1 y V2), USD 0,136, 6,3 segundos por corrida y ninguna con error del servicio (con `--concurrencia 4`).

| | k = 1 | k = 2 | k = 4 | k = 8 |
|---|---|---|---|---|
| pass^k V1 | 0,88 | 0,81 | 0,74 | 0,71 |
| pass^k V2 | 0,96 | 0,93 | 0,86 | 0,71 |

La hipótesis previa (V2 ≥ V1) se cumple en todos los k. En k = 8 empatan en 0,71 porque cada versión tiene 5 de los 7 casos con 8 de 8, aunque no son los mismos casos.

- **Dónde cambia.** `taza_rota`: V1 salió bien 3 de 8 veces y V2, 8 de 8. En 5 de sus corridas V1 no reembolsó: pidió el SKU o una confirmación al cliente. En esta evaluación de un solo turno, pedir una aclaración termina la corrida sin reembolso. Los intervalos de Wilson, [0,14 – 0,69] y [0,68 – 1,00], casi se tocan: con n = 8 la diferencia no es concluyente.
- **La decisión sobre los intentos rechazados.** V1 intentó 2 veces `cancel_order` sobre un pedido ya entregado; la tienda lo rechazó y el mundo no cambió, pero cuentan como acción irreversible de más. En la columna «solo estado» V1 tiene 51 de 56 en lugar de 49.
- **Lo que falló en V2.** En `cancelar_entregado` reembolsó los dos ítems (USD 39,99) ante un pedido con intención mezclada, y en `cancelar_en_proceso` pidió confirmación sin actuar.
- **Resultado y camino.** La trayectoria `IN_ORDER` rechazó 30 de los 49 éxitos de V1 (se saltea `lookup_order` y el mundo queda bien) y 9 de V2. Con ese criterio V1 parecería salir bien 19 de 56 veces. Aprobó el reembolso de más de V2: es la única corrida donde el camino dice sí y el resultado, no.
- **Lo que no ve el éxito.** 2 respuestas de V2 mencionan «EUR», una moneda que ninguna herramienta devuelve. El mundo quedó bien, así que cuentan como éxito; hacen falta los jueces de la Demo 2.

Es una sola serie de corridas de un agente no determinista: otra serie daría otros números.

## Una advertencia sobre cómo leer las salidas

Los jueces y el agente son modelos: **no son deterministas**. Una corrida de los siete casos es una muestra, no una medida de confiabilidad, y dos configuraciones corridas por separado ven muestras distintas del agente, así que sus resultados no se comparan caso a caso. Las etiquetas humanas de la Demo 1 y de la Demo 2 se fijaron **antes** de medir; con 11 y 14 ítems son una ilustración del método, no una calibración.
