# Demo con el marco de evaluación de ADK

Las demostraciones 1, 2 y 3 usan **piezas** de ADK (`Invocation`, los evaluadores, el registro de
métricas) llamadas directamente desde Python. Esta carpeta recorre en cambio **el flujo completo de
evaluación de ADK**: los siete casos del corpus escritos como un `EvalSet` (con rúbricas por caso),
una configuración `EvalConfig`, el agente real corrido por ADK, métricas propias y jueces
enchufados, y los tres ejecutores (`adk eval`, `AgentEvaluator` desde `pytest`, `adk web`). No
usa simuladores de usuario todavía.

Es el mismo agente (`entorno/tienda.py`) y los mismos siete casos (`entorno/corpus.py`) de las
otras demos; no se copia nada, se importa.

## Dos configuraciones, dos preguntas

| archivo | pregunta | métricas |
|---|---|---|
| `soporte_tienda/test_config.json` — **el veredicto** | ¿El agente hizo lo que debía y dijo la verdad? | `estado_final_del_mundo` y `acciones_irreversibles_de_mas` (propias), `hallucinations_v1` y `rubric_based_final_response_quality_v1` (los jueces de ADK; una rúbrica general y una o dos por caso) |
| `soporte_tienda/test_config_diagnostico.json` | ¿Qué camino siguió y cuánto se parece el texto a la referencia? | trayectoria `IN_ORDER`, ROUGE-1, `tool_recall`, `tool_precision`, `param_accuracy`, `phrase_recall` |

Es el panel de la demo 1: lo que decide es el **resultado** (el mundo, las acciones irreversibles,
la verdad de lo que se le dice al cliente). El camino y la forma del texto se miran, pero no
deciden: un agente puede llegar bien por un atajo o decir lo correcto con otras palabras.

> **Cómo se llegó a esto.** La primera versión de la demo usaba solo la configuración estricta
> como veredicto, con umbral 1,0 en todo: los siete casos dieron FAILED, y era una falla de
> diseño, no del agente (se mezclaban métricas de camino y de forma con las de resultado, y
> ROUGE-1 contra referencias escritas a mano). El veredicto nuevo se definió **después de ver esos
> resultados**; no es un ajuste de umbrales sino un cambio de qué se mide. Por eso se dice acá, y
> por eso las dos configuraciones se conservan: cuando un criterio se rediseña después de mirar los
> resultados, hay que declararlo.

## Qué hay, y qué paso del flujo es cada cosa

| Paso del flujo | Dónde está |
|---|---|
| 1 · **Caso** (`EvalSet` / `EvalCase`) | `soporte_tienda/soporte_tienda.evalset.json`, generado por `generar_evalset.py` desde `entorno/corpus.py` (mensaje, trayectoria, referencia, rúbricas, estado final) |
| 2 · **Inferencia** (`Invocation`) | ADK corre `soporte_tienda/agent.py` sobre cada caso y registra lo que pasó |
| 3 · **Métricas** (`EvalConfig`) | las dos configuraciones de arriba y `metricas_propias.py` |
| 4 · **Veredicto** | un estado por métrica y por caso (PASSED / FAILED / NOT_EVALUATED / INFORMATIONAL), en consola |
| 5 · **Resultados** | consola, `soporte_tienda/.adk/eval_history/*.evalset_result.json` (se crea al correr) y la pestaña Eval de `adk web` |
| Tres maneras de correrlo | `adk eval` · `evaluar_con_pytest.py` (`AgentEvaluator`) · `adk web` |
| Punto de extensión: métricas propias | `metricas_propias.py` (seis funciones; el veredicto usa dos) |
| Punto de extensión: simuladores | **no incluidos** |

```
demo_con_adk_evals/
├── generar_evalset.py          corpus → EvalSet (JSON), con las rúbricas de cada caso
├── metricas_propias.py         tool_recall, tool_precision, param_accuracy, phrase_recall,
│                               estado_final_del_mundo, acciones_irreversibles_de_mas
├── evaluar_con_pytest.py       AgentEvaluator.evaluate — se corre a mano
├── control_negativo.py         ¿los jueces marcan respuestas malas conocidas?
└── soporte_tienda/             la «carpeta del agente» que ADK espera
    ├── __init__.py             prepara el sys.path e instala el parser tolerante del juez
    ├── agent.py                root_agent: mismo agente que las demos, con un mundo por sesión
    ├── soporte_tienda.evalset.json
    ├── test_config.json        el veredicto (la que usan por defecto adk eval y AgentEvaluator)
    └── test_config_diagnostico.json
```

## Cómo correrlo

Desde `DEMOS/`, con el entorno activado (`source .venv/bin/activate`) y tu API key en `DEMOS/.env`
(ver `DEMOS/.env.example`). **Estas corridas llaman al modelo y consumen cuota** (con la capa gratuita
no se paga; a precio de lista cuestan lo que sigue). Orden de magnitud (estimado con los precios de
`metricas/costo.py`; ADK no informa los tokens de los jueces): el veredicto de un caso ≈ $0,04 y de
los siete ≈ $0,25; el diagnóstico de los siete ≈ $0,01 (no usa jueces); el control negativo ≈ $0,05;
`pytest` con `num_runs=2` ≈ $0,5.

```bash
python demo_con_adk_evals/generar_evalset.py     # solo si cambia el corpus o las rúbricas

cd demo_con_adk_evals                            # `adk eval` se corre desde acá
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json:taza_rota --print_detailed_results
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json --print_detailed_results
adk eval soporte_tienda soporte_tienda/soporte_tienda.evalset.json \
    --config_file_path soporte_tienda/test_config_diagnostico.json --print_detailed_results
cd ..

python demo_con_adk_evals/control_negativo.py
NUM_RUNS=1 python -m pytest demo_con_adk_evals/evaluar_con_pytest.py -s -q    # AgentEvaluator
adk web demo_con_adk_evals                       # abre la interfaz; el servidor lista el conjunto (pestaña Eval)
```

El sufijo `:taza_rota` elige casos dentro del archivo (`:caso1,caso2`). Sin `--config_file_path`,
`adk eval` usa el `test_config.json` que está junto al conjunto de casos. La salida de `adk eval`
empieza con muchos avisos `[EXPERIMENTAL]` y líneas `INFO`: lo útil arranca en `Eval Run Summary`.
Las salidas de una corrida de referencia están en `../salidas_de_referencia/adk_eval_*.txt`, sin
esos avisos.

**Si tu key no accede a `gemini-2.5-flash`** (Google limita los modelos 2.5 a quienes ya los
usaron), hay que cambiar el modelo en **dos lugares**: `MODEL_NAME` en `.env` (lo usa el agente) y
`"judge_model"` en `soporte_tienda/test_config.json` (aparece dos veces: uno por juez). El
diagnóstico no usa jueces. `MODEL_NAME` no llega a los jueces de estos JSON.

**Si `adk eval` termina en `FAILED` y no imprime ninguna línea `Metric:`**, el problema no es el agente: mirá el log, que dice `API key not valid` (key mal copiada) o `429` (cuota). A diferencia de las demos 2 y 3, `adk eval` no corta con un mensaje claro.

## Resultados de la corrida de referencia (Gemini 2.5 Flash, ADK 2.12.0)

**Veredicto, siete casos: 7 de 7 PASSED.** El mundo quedó bien en los siete, no hubo ninguna acción
irreversible de más y los dos jueces aprobaron todo (`hallucinations_v1` quedó NOT_EVALUATED en
`consulta_politica`: el juez no produjo puntaje para esa respuesta, y por eso no cuenta en el
veredicto del caso).

**Esto no significa que el agente sea perfecto.** Hay tres razones para no leerlo así:

1. **Es una sola muestra de un agente que no es determinista.** En la corrida de diagnóstico, el
   agente contestó `consulta_politica` diciendo que no tenía acceso a la política de devoluciones
   (aunque la regla de 30 días está en su instrucción) y en `cancelar_entregado` pidió una
   aclaración sin consultar el pedido. En la del veredicto contestó bien los dos. Un caso por
   corrida no dice cuán confiable es el agente: para eso están `num_runs` y la Demo 3 (pass^k).
   Las dos configuraciones corrieron sobre muestras distintas, porque `adk eval` vuelve a hacer la
   inferencia cada vez; no se pueden comparar caso a caso.
2. **Un juez es otro modelo.** El control negativo (`control_negativo.py`) lo comprueba en lo
   mínimo: los dos jueces aprueban la respuesta fiel y desaprueban las dos que inventan algo.

   | ítem | debería | `hallucinations_v1` | juez de rúbricas |
   |---|---|---|---|
   | `fiel_reembolso` | aprobar | 1,00 | 1,00 |
   | `comprobante_inventado` | desaprobar | 0,50 | 0,00 |
   | `accion_inventada` | desaprobar | 0,00 | 0,00 |

   Con tres ítems no calibra nada. La calibración (matriz de confusión y κ de Cohen) está en
   `demos/demo2_juez.py`.
3. **El veredicto es más permisivo en la forma, a propósito.** Por ejemplo, en `consulta_estado` el
   agente fue directo a `get_shipment_status` sin `lookup_order`: el diagnóstico estricto lo
   desaprueba por trayectoria, el veredicto lo aprueba porque lo que le dijo al cliente es cierto.
   Es una decisión de qué se mide, y tiene que ser explícita.

**Diagnóstico estricto, siete casos** (primera corrida, otra muestra del agente; umbral 1,0 en todo
y 0,8 en ROUGE-1, fijados antes de correr):

| caso | trayectoria | ROUGE-1 | recall | precision | params | frases | estado | irrev. |
|---|---|---|---|---|---|---|---|---|
| taza_rota | ✓ | ✗ 0,55 | ✓ | ✗ 0,67 | ✓ | ✓ | ✓ | ✓ |
| fuera_de_plazo | ✓ | ✗ 0,39 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| cancelar_en_proceso | ✓ | ✗ 0,13 | ✓ | ✗ 0,67 | ✓ | ✓ | ✓ | ✓ |
| cancelar_entregado | ✗ | ✗ 0,26 | ✗ 0 | ✗ 0 | ✗ 0 | ✗ 0,50 | ✓ | ✓ |
| consulta_estado | ✗ | ✓ 0,92 | ✗ 0,50 | ✓ | ✗ 0,50 | ✓ | ✓ | ✓ |
| id_con_typo | ✓ | ✗ 0,57 | ✓ | ✓ | ✓ | ✗ 0,50 | ✓ | ✓ |
| consulta_politica | ✓ | ✗ 0,11 | ✓ | ✓ | ✓ | ✗ 0 | ✓ | ✓ |

Los siete figuran como FAILED con el mundo bien en los siete. Lo que desaprueba es la forma: ROUGE-1
rechaza 6 de 7 respuestas (varias correctas, dichas con otras palabras); `tool_precision` cuenta como
llamada de más un `send_confirmation_email` inofensivo; `phrase_recall` falla con «verificar» en lugar
de «confirmar». Es lo que enseña la demo 1, ahora con el agente real.

## Cosas que conviene saber

- **El parser de ADK descarta muestras del juez en silencio.** Cuando Gemini 2.5 Flash escribe el
  razonamiento de una rúbrica en varias líneas, el parser de ADK no la entiende y el puntaje se
  calcula con menos muestras, sin aviso en el reporte. `soporte_tienda/__init__.py` instala el parser
  tolerante de `metricas/juez_tolerante.py` y al terminar imprime una línea `[juez]`. Muestras que el
  parser original habría perdido en la corrida de referencia: 3 de 21 en los siete casos, 7 de 9 en
  el control negativo, 3 de 6 con `AgentEvaluator`. Ninguna se descartó.
- **Las rúbricas de un caso tienen dos trampas.** Necesitan `type="FINAL_RESPONSE_QUALITY"` (si no, el
  juez las descarta sin avisar) y su `rubric_id` no puede repetirse con los de `test_config.json`
  (es un error): llevan el id del caso como prefijo. `generar_evalset.py` ya lo hace.
- **Un mundo por sesión.** `adk eval` carga el agente una vez y lo corre sobre todos los casos, en
  paralelo. Con una única `Tienda`, la cancelación de un caso cambiaría el mundo del siguiente.
  `agent.py` usa un `before_tool_callback` que ejecuta las mismas herramientas contra una tienda
  propia de cada sesión.
- **Una métrica propia que no se puede importar queda «no evaluada», no «fallida».** ADK carga el
  agente bajo el nombre `agent`, no `soporte_tienda`, y no pone esta carpeta en el `sys.path`: sin
  ayuda, las seis métricas propias salen `NOT_EVALUATED` en el reporte y el único aviso es un `ERROR`
  con su traceback en el log. El veredicto del caso sigue dependiendo solo de las demás métricas.
  `soporte_tienda/__init__.py` agrega la carpeta al `sys.path`.
- **ADK no compara el estado final.** El `EvalSet` guarda `final_session_state` (lo escribe
  `generar_evalset.py`), pero ninguna de las 17 métricas lo lee. `estado_final_del_mundo` lo mide
  reproduciendo las llamadas reales y las esperadas sobre una tienda nueva y comparando el resultado.
- **ADK no pasa el caso entero a una métrica**, solo las invocaciones. `phrase_recall` encuentra las
  frases esperadas buscando el mensaje del cliente en el corpus, y falla si no lo encuentra (con una
  lista vacía valdría 1,0).
- **Escribir `adk eval soporte_tienda/`** (con la barra final del autocompletado) deja el nombre de la
  app vacío: sin barra.
- **`evaluar_con_pytest.py` no se llama `test_*.py` a propósito**, para que `pytest` desde `DEMOS/` no
  lo recoja y no llame al modelo dentro de la suite de $0.

## Límites de esta demo

- No se probó correr evaluaciones desde la pestaña Eval de `adk web`. Sí se comprobó que el servidor
  lista la app `soporte_tienda`, el conjunto y sus siete casos.
- No se corrió el conjunto completo con `AgentEvaluator` y jueces (≈ $0,5): se verificó con un caso y
  dos corridas.
- Las cifras de arriba son de una sola corrida; las tuyas van a diferir.
