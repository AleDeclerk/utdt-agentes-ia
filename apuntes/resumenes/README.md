# Resúmenes de clase · Arquitectura de Agentes IA (UTDT, 2.ª edición)

Notas personales de estudio. Cubren las clases 1 a 9 (24/09 al 27/10/2026), dictadas por Matías Zabaljauregui.

**Cómo se armaron.** Cada resumen sale de la transcripción automática que genera Zoom en la grabación de la clase, completada con el material del campus y del repo del curso. La transcripción automática tiene errores de reconocimiento: los pasajes que no se entendieron están marcados "(transcripción dudosa)" o se omitieron. La de la **clase 1** salió casi ilegible, así que ese resumen se apoya sobre todo en `MODULO_1` del repo y lo indica en cada punto.

**No subir esta carpeta a un repo público.** Son notas de un curso pago.

## Las clases

| Clase | Fecha | Tema | Archivo |
|---|---|---|---|
| 1 | 24/09 | Qué es un agente, el *agency spectrum* y el Lab 01 (un reclamo bancario en tres arquitecturas) | [clase-01.md](clase-01.md) |
| 2 | 29/09 | Diseño de sistemas agénticos: componentes, elección de modelo, trade-offs y routing | [clase-02.md](clase-02.md) |
| 3 | 01/10 | Piezas mínimas de un agente en ADK (Agent, Runner, Session, Tools) y guardrails | [clase-03.md](clase-03.md) |
| 4 | 06/10 | Herramientas y MCP: tipos de tools, protocolo, transportes y demos en `adk web` | [clase-04.md](clase-04.md) |
| 5 | 08/10 | Orquestación: los 6 arquetipos y cómo se combinan | [clase-05.md](clase-05.md) |
| 6 | 13/10 | Memoria y conocimiento: tipos de memoria, RAG moderno y grafos | [clase-06.md](clase-06.md) |
| 7 | 15/10 | GraphRAG con Neo4j: demo de gestión de talento | [clase-07.md](clase-07.md) |
| 8 | 22/10 | Evals (1): trayectoria vs. resultado, métricas y sus puntos ciegos | [clase-08.md](clase-08.md) |
| 9 | 27/10 | Evals (2): jueces LLM, kappa de Cohen, Ragas, pass@k, pass^k y Wilson | [clase-09.md](clase-09.md) |

## Las ideas que atraviesan el curso

- **La arquitectura más simple que resuelva el problema.** Aparece en el *agency spectrum* (clase 1), en los arquetipos ordenados por autonomía (clase 5) y en los niveles de memoria (clase 6). Se sube un escalón solo cuando el actual falla.
- **El modelo propone, el código dispone.** Topes de iteraciones y de llamadas, herramientas con parámetros acotados, confirmación humana en acciones riesgosas. En la clase 7, el LLM nunca escribe Cypher: elige una tool con una consulta fija.
- **La descripción de una tool es parte del código.** El modelo decide por el docstring, el nombre y el esquema (clases 3 y 4).
- **La seguridad del modelo es probabilística, los guardrails tienen que ser deterministas** (callbacks de ADK, Model Armor, NeMo Guardrails; clase 3).
- **El costo es un criterio de diseño.** El routing entre modelos (clase 2), el costo de Deep Research (clase 5) y el de los jueces LLM (clases 8 y 9).
- **Un número sin n no es evidencia.** Se mide trayectoria y estado final por separado, con varias corridas y un intervalo de confianza (clases 8 y 9).
- **ADK 2 va hacia workflows en grafo.** Las plantillas Sequential, Parallel y Loop siguen funcionando pero quedan deprecadas (clases 2 y 5).

## Tareas y pedidos del docente

| Clase | Qué pidió |
|---|---|
| 1 | Lab 01 (la última slide dice "entrega la próxima clase"; en la transcripción parece que es opcional) |
| 3 | Leer el README de cada ejemplo de `ADK_Tutorial0` y repasar funciones asíncronas en Python |
| 5 | Explorar `MODULO_5/LABS/01_onboarding_crediticio` y leer "fallas típicas" y "cuándo elegirlo" en las slides |
| 6 | Traer 2 o 3 novedades del área por semana |
| 8 | Armar evals sobre los propios agentes y contar cómo les fue |
| 9 | Revisar las slides complementarias y probar Ragas sobre un retriever |

## Calendario

Son 18 clases. Después de la 9 vienen la 10 (29/10), y de la 11 a la 18 el 3/11, 5/11, 12/11, 17/11, 19/11, 24/11, 26/11 y 1/12. La del martes 10/11 se canceló por el feriado de la visita papal y el curso termina el **martes 1/12**. Detalle en [../notas/calendario-y-logistica.md](../notas/calendario-y-logistica.md).
