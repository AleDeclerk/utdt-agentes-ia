# El ciclo de vida de un agente en producción

Cómo se lleva un agente de prototipo a producción, en ocho fases que forman un ciclo. Las prácticas no dependen del proveedor del modelo, del framework de agentes ni de la nube.

**De dónde sale.** De la guía pública de Google [*The lifecycle*](https://google.github.io/agents-cli/guide/lifecycle/), de agents-cli (actualizada el 4/11/2026). Se usan solo los conceptos: esta nota no describe un producto de Google.

**Dónde apareció en el curso.** Matías recomendó una herramienta de línea de comandos que se instala como skill de Claude Code. En la [clase 10](../resumenes/clase-10.md) dijo que se instala "como Skill" [00:05] y que desde ahí "pueden correr directamente las evaluaciones" [00:07]. En la [clase 12](../resumenes/clase-12.md) la recordó: "te va guiando por todo el proceso, desde el diseño hasta el prototipo, las evaluaciones y el despliegue en producción" [00:03]. La transcripción deforma el nombre ("Ison CD Li"); por la descripción, probablemente es agents-cli (dudoso).

## 1. El agente es la parte chica

Un agente tiene tres partes: un modelo, una instrucción y un conjunto de herramientas. Ese código es corto, muchas veces menos de 50 líneas. La mayoría de las fallas en producción no vienen de ahí, sino de lo que falta alrededor:

- Una evaluación que frene una versión cuando el agente recomienda una acción insegura.
- Un test de integración que detecte un cambio en el contrato de una herramienta.
- Una traza que permita reproducir una corrida después de un problema.

Una demo tiene solo el agente. Un sistema en producción tiene el agente y estas piezas.

## 2. El ciclo

Son ocho fases. La salida de la última vuelve a la fase de evaluación.

```text
spec -> scaffold -> build -> orchestrate -> evaluate -> deploy -> publish -> observe
                                               ^                                |
                                               +------ casos de test nuevos ----+
```

| # | Fase | Qué hace el equipo | Resultado |
|---|---|---|---|
| 0 | Spec | Escribe las herramientas, las restricciones y los criterios de éxito | Un archivo de especificación |
| 1 | Scaffold | Arma desde la spec un proyecto con tests, evaluaciones, infraestructura y CI | Un proyecto con estructura de producción |
| 2 | Build | Escribe el modelo, la instrucción y las herramientas | El agente |
| 3 | Orchestrate | Divide un agente grande en un orquestador y agentes especialistas | Un equipo de agentes |
| 4 | Evaluate | Corre un dataset de casos y puntúa cada respuesta contra rúbricas | Un puntaje y un pasa o no pasa |
| 5 | Deploy | Manda el mismo código al runtime, con identidad propia | Un agente corriendo |
| 6 | Publish | Registra el agente en un catálogo | Un agente que otros pueden encontrar |
| 7 | Observe | Lee trazas y analítica, y suma los casos fallidos al dataset | Casos de test nuevos |

## 3. Fase 0: la spec es la fuente

La spec es un archivo corto que nombra las herramientas, las restricciones y los criterios de éxito. Todas las demás fases leen de ella: el scaffold, las rúbricas de evaluación, los guardrails y los atributos de las trazas.

Ejemplo, para un agente que hace el triage de incidentes:

```markdown
## Herramientas
| Herramienta                     | Fuente de datos    |
| ------------------------------- | ------------------ |
| query_logs(service, severity)   | Almacén de logs    |
| check_metrics(service, metric)  | Almacén de métricas|
| search_runbook(query)           | Índice de runbooks |

## Restricciones
1. Citar la sección del runbook en cada recomendación.
2. No recomendar una acción destructiva si el runbook no la permite para este síntoma.

## Criterios de éxito
- 80 % o más de los diagnósticos coinciden con la causa raíz del ground truth.
- 100 % de las recomendaciones citan una sección del runbook.
- 0 recomendaciones destructivas sin permiso del runbook.
```

- Cada restricción es una regla que un test puede verificar, no una frase del prompt que se espera que el modelo obedezca.
- Cada criterio de éxito tiene un número. Un criterio sin número no puede frenar una versión.

## 4. Fases 1 y 2: primero el scaffold, después el agente

El scaffold arma la estructura completa (tests, archivos de evaluación, infraestructura como código y pipeline de CI) antes de escribir el agente. Así, la primera versión del agente ya corre dentro del pipeline de entrega.

El modelo es una línea de configuración. Si se cambia de proveedor, la evaluación, el despliegue y la observabilidad no cambian. Por eso la evaluación no tiene que depender de un modelo.

## 5. Fase 3: dividir un agente grande en especialistas

Cuando la tarea crece, un agente con muchas herramientas se vuelve poco confiable. Se divide en un orquestador y pocos especialistas, cada uno con un conjunto acotado de herramientas. Ejemplo: el orquestador reparte el trabajo entre un investigador (logs y métricas), un diagnosticador (búsqueda en runbooks) y uno que propone la acción, y arma la respuesta final con sus resultados.

Tres beneficios:

1. Cada prompt es más chico, así que cada agente es más confiable.
2. Cada especialista tiene sus propias herramientas, así que puede tener sus propios guardrails.
3. La traza muestra qué especialista cometió el error.

Cuando los agentes corren en procesos distintos o son de otro equipo, se comunican con un protocolo estándar entre agentes.

## 6. Fase 4: la evaluación es un gate de la versión

La evaluación corre un dataset de casos contra el agente, y un modelo juez puntúa cada respuesta contra una rúbrica. El resultado es un número que el equipo puede defender. Tiene un umbral: por debajo, el comando de evaluación falla y el CI frena el merge. Antes de la primera versión hay que esperar varias vueltas.

Cuatro fallas frecuentes, cada una con su chequeo:

| Falla | Qué es | Cómo se detecta |
|---|---|---|
| Resultado de herramienta inventado | El agente dice que llamó a una herramienta y no la llamó | Comparar las llamadas reales con las esperadas |
| Respuesta sin evidencia | La respuesta trae datos que ninguna herramienta devolvió | Comparar cada afirmación con las salidas de las herramientas |
| Prompt injection | Un mensaje le pide al agente que ignore una regla de seguridad | Una rúbrica de seguridad y un filtro de entrada en tiempo de ejecución |
| Desvío del tema | El agente da consejos generales y no investiga | Una rúbrica de relevancia sobre la respuesta final |

## 7. Fase 5: desplegar con defensa en capas

El mismo código puede correr en un runtime administrado de agentes, en un servicio de contenedores o en un cluster. El despliegue suma tres controles:

- **Identidad propia.** El agente corre con su propia identidad y el mínimo privilegio, no con una cuenta de servicio compartida. Si la identidad no puede borrar un recurso, el agente tampoco, aunque la evaluación se haya perdido un error.
- **Control de acceso.** Un agente interno queda detrás del inicio de sesión único de la empresa, no abierto a internet.
- **Sin claves guardadas.** El CI obtiene credenciales de corta duración de la nube; el repositorio no tiene claves de cuentas de servicio.

Las capas: la evaluación es la primera, la identidad la segunda y una persona la tercera. Para una acción destructiva, el agente recomienda y una persona confirma. Si la evaluación se pierde un error, las otras dos capas todavía pueden frenar la acción.

## 8. Fase 6: publicar

Desplegar le da al agente una dirección. Publicar es un paso aparte: registra el agente en un catálogo para que usuarios y otros agentes lo encuentren.

## 9. Fase 7: observar y cerrar el ciclo

Cada corrida deja una traza, con un span por cada llamada al modelo, cada llamada a una herramienta y cada traspaso entre agentes. Con las trazas y la analítica se encuentran regresiones que la evaluación no vio, aumentos de costo por una herramienta que se llama demasiado y usuarios que intentan saltear las reglas de seguridad.

Para cerrar el ciclo, una persona lee las corridas fallidas y las suma al dataset de evaluación. Ninguna herramienta hace este paso sola. Después se corre la evaluación de nuevo y se compara el puntaje con las corridas anteriores.

## 10. Qué cambia con el ciclo

| Problema | Sin el ciclo | Con el ciclo |
|---|---|---|
| El agente inventa una acción | El cliente lo descubre después de la versión | La rúbrica de evaluación frena el merge |
| Cambia la API de una herramienta | El agente falla sin mensaje de error | El test de integración en CI detecta el cambio de esquema |
| Un usuario usa mal el agente | El equipo no puede reproducir la corrida | Las trazas y la analítica muestran la corrida en menos de una hora |
| Una herramienta sube el costo | El equipo lo ve en la próxima factura | El conteo de spans por herramienta lo muestra en pocas horas |

## 11. Checklist antes de la primera versión en producción

- [ ] La spec nombra cada herramienta y su fuente de datos.
- [ ] Cada restricción es una regla que un test puede verificar.
- [ ] Cada criterio de éxito tiene un número.
- [ ] El proyecto tiene tests, evaluaciones, infraestructura como código y CI desde el primer commit.
- [ ] La evaluación tiene un umbral y el CI frena el merge por debajo.
- [ ] El dataset tiene casos de resultados inventados, respuestas sin evidencia, prompt injection y desvío del tema.
- [ ] El agente corre con identidad propia y el mínimo privilegio.
- [ ] Una persona confirma cada acción destructiva.
- [ ] Cada corrida deja una traza con un span por llamada al modelo, llamada a herramienta y traspaso.
- [ ] Una persona suma las corridas fallidas de producción al dataset, con una frecuencia fija.

## Cruce con las clases

| Fase | Dónde se vio en el curso |
|---|---|
| 0 y 1. Spec y scaffold | La herramienta de línea de comandos de las clases [10](../resumenes/clase-10.md) y [12](../resumenes/clase-12.md): entrevista para la especificación y recién después el prototipo |
| 2. Build | Clases [3](../resumenes/clase-03.md) y [4](../resumenes/clase-04.md): Agent, herramientas y MCP |
| 3. Orchestrate | Clase [5](../resumenes/clase-05.md): arquetipos de orquestación |
| 4. Evaluate | Clases [8](../resumenes/clase-08.md) y [9](../resumenes/clase-09.md): evals, jueces LLM y umbrales |
| 5. Deploy | Clases [13](../resumenes/clase-13.md) y [14](../resumenes/clase-14.md): identidad por agente y mínimo privilegio |
| 6. Publish | Clases [13](../resumenes/clase-13.md) y [14](../resumenes/clase-14.md): el registro de agentes |
| 7. Observe | Clase [10](../resumenes/clase-10.md): trazas, Langfuse y casos que vuelven al dataset |

Ver también [La arquitectura completa](arquitectura-completa.md), que ordena las mismas piezas en tres capas.
