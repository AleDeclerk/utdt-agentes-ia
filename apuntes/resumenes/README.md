# Resúmenes de clase · Arquitectura de Agentes IA (UTDT, 2.ª edición)

Notas personales de estudio. Cubren las clases 1 a 14 (24/09 al 17/11/2026), dictadas por Matías Zabaljauregui.

**Cómo se armaron.** Cada resumen sale de la transcripción automática que genera Zoom en la grabación de la clase, completada con el material del campus y del repo del curso. La transcripción automática tiene errores de reconocimiento: los pasajes que no se entendieron están marcados "(transcripción dudosa)" o se omitieron. La de la **clase 1** salió casi ilegible, así que ese resumen se apoya sobre todo en `MODULO_1` del repo y lo indica en cada punto.

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
| 10 | 29/10 | Monitoreo en producción: OpenTelemetry, Langfuse, prompts y datasets versionados, gates y alertas | [clase-10.md](clase-10.md) |
| 11 | 03/11 | Seguridad: modelar amenazas (STRIDE, MAESTRO), nombrarlas (OWASP), ver al adversario (MITRE ATLAS) y gobernar (NIST, ISO) | [clase-11.md](clase-11.md) |
| 12 | 05/11 | Red teaming de agentes: garak (amplitud) y PyRIT (profundidad) en la capa 1, y un primer vistazo a NeMo Guardrails | [clase-12.md](clase-12.md) |
| 13 | 12/11 | Gobernanza (1): por qué fallan los agentes en producción, registro como frontera, identidad atestiguada (SPIFFE) y políticas como código (PDP y PEP) | [clase-13.md](clase-13.md) |
| 14 | 17/11 | Gobernanza (2): motores de políticas, Agent Gateway y Agent Registry, con demo en Google Cloud y un roadmap de 90 días | [clase-14.md](clase-14.md) |

## Las ideas que atraviesan el curso

- **La arquitectura más simple que resuelva el problema.** Aparece en el *agency spectrum* (clase 1), en los arquetipos ordenados por autonomía (clase 5) y en los niveles de memoria (clase 6). Se sube un escalón solo cuando el actual falla.
- **El modelo propone, el código dispone.** Topes de iteraciones y de llamadas, herramientas con parámetros acotados, confirmación humana en acciones riesgosas. En la clase 7, el LLM nunca escribe Cypher: elige una tool con una consulta fija.
- **La descripción de una tool es parte del código.** El modelo decide por el docstring, el nombre y el esquema (clases 3 y 4).
- **La seguridad del modelo es probabilística, los guardrails tienen que ser deterministas** (callbacks de ADK, Model Armor, NeMo Guardrails; clase 3).
- **La seguridad es, en gran parte, una decisión de arquitectura.** Se modela durante el diseño, no al final, y el arquitecto es "el primer responsable de la seguridad" aunque no la audite ni la implemente en detalle (clase 11).
- **En seguridad no se aprueba por promedio.** En capacidades alcanzan los promedios y los umbrales; en red teaming un solo fallo crítico bloquea el despliegue, y una sola corrida de ataques es una muestra de tamaño uno (clase 12).
- **El costo es un criterio de diseño.** El routing entre modelos (clase 2), el costo de Deep Research (clase 5) y el de los jueces LLM (clases 8 y 9).
- **Un número sin n no es evidencia.** Se mide trayectoria y estado final por separado, con varias corridas y un intervalo de confianza (clases 8 y 9).
- **Evaluar, desplegar, observar y mejorar es un solo ciclo.** Las trazas de producción vuelven como casos de evaluación, y prompts, datasets y experimentos se versionan como artefactos (clases 8 a 10). El mapa está en [La arquitectura completa](../notas/arquitectura-completa.md).
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
| 10 | Sin tareas. El docente va a subir al repo el proyecto demo (portal del banco con Langfuse) y compartir un texto sobre SLI y SLO |
| 11 | Sin tareas formales. Consejo de cierre: arrancar de a poco con uno de los marcos (primero MAESTRO, después OWASP y MITRE ATLAS). Las slides 88 y 89 proponen una evaluación opcional |
| 12 | Sin tareas. Recomendó practicar con una plataforma de ejercicios tipo capture the flag y quedó en compartir el informe del inicio, el playbook y el panel de resultados |
| 13 | Sin tareas. Quedó en compartir informes, artículos sobre MCP, el informe de los componentes en Google Cloud y el roadmap de 90 días |
| 14 | Sin tareas. Quedó en compartir el código del agente de la demo y un ejemplo en Terraform; el roadmap de 90 días ya está en el campus |

## Calendario

Son 18 clases. Después de la 14 vienen, de la 15 a la 18, el 19/11, 24/11, 26/11 y 1/12. La del martes 10/11 se canceló por el feriado de la visita papal y el curso termina el **martes 1/12**. Detalle en [../notas/calendario-y-logistica.md](../notas/calendario-y-logistica.md).
