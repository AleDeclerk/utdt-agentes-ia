# Clase 10 · 29/10 · Observabilidad en producción: Langfuse, trazas, prompts versionados y datasets

**Docente:** Matías Zabaljauregui.
**Material del campus:** solo la grabación (2:20:16), sin slides. En pantalla: el deck "Monitoreo en producción" (pie "UTDT 2026 · Módulo 10 de 14 · ADK 2.12"), una demo propia del docente (el portal de un banco minorista con su agente) y la interfaz de Langfuse. Cerca de la hora 2:00 apareció la slide 108 de 116 de `AgentSecOps_clase_v3.pdf`.

## En una frase
Primera clase del Módulo 10: las evals de las clases [8](clase-08.md) y [9](clase-09.md) se llevan al agente en producción, con Langfuse como pieza que recibe trazas por OpenTelemetry, versiona prompts y datasets, corre experimentos y hace de gate y de alertas.

## Recorrido de la clase

**[00:00] Apertura y anuncio**
- Dos alumnos contaron proyectos chicos donde empezaron o piensan aplicar evals (un bot de turnos médicos y un agente casero). El docente insiste en incorporarlas como buena práctica, en paralelo con el agente: son un cuello de botella cada vez mayor para llegar a producción.
- [~00:07, aprox.] Anuncio: una herramienta de línea de comandos, instalable también como skill de Claude Code (nombre dudoso en la transcripción), que arma el scaffolding de un agente, lo despliega y corre evals. Nació atada a ADK; la novedad de la semana suma otros frameworks, entre ellos LangGraph (transcripción dudosa).

**[~00:09, aprox.] Drift y el caso del banco**
- Objetivo: extender las evals al agente desplegado, donde aparecen problemas que el laboratorio no muestra y drift (cambios en las llamadas, el consumo de tokens y el comportamiento de los usuarios; definición en la [clase 8](clase-08.md)). Se detecta midiendo la distancia entre distribuciones, por ejemplo con la divergencia de Kullback-Leibler. Se ve la próxima clase y Langfuse la calcula sola.
- Caso: el backend (LangGraph) de un portal de un banco minorista manda su telemetría por OpenTelemetry a Langfuse. Es el corazón del pipeline: recibe trazas y métricas de todos los componentes y, con los scores, se decide si una versión pasa a producción.

**[00:15] "El tablero está en verde"**
- Slide inicial, con "disponible 99.9%", "p95 120 ms" y "0 errores 500", y cuatro preguntas. Es el problema del "92 %" de la [clase 8](clase-08.md): un número sin contexto no informa.
  - ¿Verde según quién? Ahora importan también la calidad de las respuestas, los tokens y los intentos de ataque.
  - ¿Y si responde mal sin caerse? Un fallo de lenguaje no da error de infraestructura: da una respuesta fluida y equivocada.
  - ¿Quién se entera, y cuándo? Cada familia de métricas necesita un responsable.
  - ¿Cuánto cuesta saberlo? Medir bien en producción y a escala es caro.
- En vivo aparecen casos borde que los casos de evaluación no cubren: preguntas imprevistas, herramientas que cambian, usuarios maliciosos. El monitoreo no es un control de seguridad agregado al final: cierra el ciclo evaluar, desplegar, observar y mejorar (el flywheel de la [clase 8](clase-08.md)).
- [00:23] Shadow: se duplica el sistema, ambos ven tráfico real pero solo uno responde. Canary: variante de A/B testing en la que parte del tráfico usa la versión nueva y se miden métricas para decidir si se despliega.

**[00:25] Objetivos del módulo, observabilidad, OpenTelemetry y SLO**
- El módulo cubre esta clase y la próxima: logs, métricas y trazas; por qué en producción no hay respuesta de referencia y de dónde sale una señal semántica; fijar qué se mide; despliegue progresivo (shadow, canary, A/B); y operar con responsabilidad (datos personales, dueños de métricas y alertas). Las slides sobre ADK se saltearon: hoy importa la infraestructura de medición.
- [00:32] Observar es conservar el detalle de lo que genera el agente para poder hacerle preguntas, incluso las no pensadas. Se diseña junto con el agente: qué registrar, con qué atributos, a qué costo y con qué cuidado de datos personales. Un log es un registro puntual (una llamada puede generar 1000); una traza es el recorrido completo de un turno, con trayectoria, tiempos, costo por paso, tokens, contexto y, a veces, la cadena de pensamiento. Por ahora, una traza sale de un turno.
- [00:37] OpenTelemetry es el protocolo casi universal para integrar observabilidad: permite elegir vendor y alimenta a Langfuse desde muchos emisores. En la [clase 8](clase-08.md), ADK 2 ya lo emitía.
- [00:39] SLO (objetivo a nivel de servicio): sin objetivo no hay umbral con sentido. Es el valor que se promete sostener sobre una ventana de tiempo (ejemplo: 90 % de sesiones resueltas en 28 días) y suele ir en el contrato. El docente compartirá un texto con estas siglas.

**[00:44] La demo y los cinco objetivos**
- Pregunta guía: ¿qué evidencia necesita un equipo para operar un asistente generativo en producción? Foco en instituciones reguladas (ver [clase 9](clase-09.md)).
- Demo: tráfico sintético pero instalación real (portal, agente, Langfuse v4), todo en la máquina del docente. Cada traza tiene un link a Langfuse y otro a una APM tradicional (nombre dudoso), que no muestra el comportamiento del agente. El feedback del usuario alimenta dashboards. El agente tiene seis herramientas (listar cuentas, ver transacciones, bloquear una tarjeta, abrir una disputa, entre otras).
- [~00:49, aprox.] Al terminar, se debería poder: (1) reconstruir qué hizo un agente desde su traza; (2) tratar los system prompts como artefactos versionados, con etiquetas y rollback; (3) decidir si una versión avanza con datasets, experimentos y gates; (4) medir calidad y riesgo, y cuánto se puede creer esa medición (el punto que más importa al docente, ver kappa en la [clase 9](clase-09.md)); (5) vigilar con tableros y alertas que disparen acciones.
- De las tres preguntas de la slide (no quedaron dictadas), la clave es la tercera: qué cambió, ya sea por nosotros (agente, prompt, bibliotecas) o por el entorno (drift). Nada de esto agrega latencia: corre fuera del camino crítico de la respuesta.

**[00:56] Desvío: inyección de prompts**
- Según el docente, se intentó demostrar que no tiene solución computacional y hace unos dos meses OpenAI (se entiende así) lo reconoció en su blog. El modelo mezcla en su contexto datos, prompt, herramientas e historial sin separarlos. Hay variante directa e indirecta (esta última, en la [clase 6](clase-06.md)).
- Los guardrails (NeMo Guardrails, Model Armor, [clase 3](clase-03.md)) combinan heurísticas, expresiones regulares y clasificadores de ML, y el problema sigue abierto. PyRIT hace red teaming emulando ataques con otro modelo (cambios de rol, sycophancy en varios turnos). Se ve en seguridad.

**[01:01] Langfuse: vocabulario, conexión y cómo empezar**
- **Turno:** una consulta. **Observación:** un paso de la traza, tipado (llamada al modelo, a una herramienta, aviso de un guardrail). **Sesión:** una conversación. **Score:** resultado de un juicio; la industria tiende a evaluar observaciones y no trazas enteras. **Evaluador**, **dataset** y **experimento** completan el modelo. Es open source; el docente usa la versión self-hosted, útil para un banco que no quiere que los datos salgan.
- [01:06] Conexión: las señales de ADK pasan por una capa llamada OpenInference, que las convierte a OpenTelemetry y llegan a Langfuse. En LangGraph hay que escribir pocas líneas de instrumentación.
- [01:10] Para empezar, instalar en Claude Code la skill oficial de Langfuse y su servidor MCP, y pedirle a Claude que instrumente el agente, arme datasets y experimentos y devuelva métricas. ADK tiene evals offline propias; Langfuse es más robusto.

**[01:13] Tipos, interfaz, anotación humana y dashboards**
- Cada objeto tiene tipo (generation es una llamada a un LLM, tool una herramienta) y de eso depende qué controles se aplican; el agente debe enviarlo bien. Conviene usar nombres descriptivos, evitar ruido de infraestructura e incluir la cadena de pensamiento en la traza si se quiere investigar una decisión.
- La interfaz muestra las trazas en árbol o grafo, con los scores de cada una (booleanos, numéricos o categóricos). Se le puede pedir a Claude las últimas cinco trazas bajo un umbral para buscar un patrón.
- Langfuse no filtra nada: enmascarar datos sensibles es responsabilidad del agente, o se filtran hacia Langfuse.
- [~01:24, aprox.] Anotación humana: colas de trazas con formularios simples para que el experto de dominio las anote y se compare con el juez LLM. [01:26] Ahí vuelve kappa de Cohen con intervalos como el de Wilson, lo que se espera en una industria regulada ([clase 9](clase-09.md)).
- [~01:29, aprox.] Dashboards para negocio: 445 casos resueltos sin pasar a un humano, costo, modos de fallo, tipos de riesgo y pulgares arriba y abajo (feedback subestimado, útil para producto). Los datos son sintéticos.
- [01:33] ¿Langfuse clasifica los riesgos con su propio LLM? No: la función `input assessment` (nombre tal como se entiende) del agente devuelve el tipo de riesgo y viaja por OpenTelemetry. Langfuse solo guarda y permite analytics.

**[01:35] Prompts como artefactos versionados**
- Los alumnos dieron tres razones: cambiar el prompt al cambiar de LLM, hacer A/B y volver atrás rápido. El docente suma: cada cambio es una versión con etiqueta, el rollback es mover la etiqueta de "producción", y se puede correr el mismo agente, dataset y modelo cambiando solo el prompt.
- El agente no depende de Langfuse para correr: tras el release se puede copiar el prompt elegido al código. Es trabajo offline, no en tiempo real. Para un A/B en producción hay que desplegar dos versiones del agente y repartir el tráfico (por ejemplo 80/20).

**[01:46] Datasets, evaluadores, experimentos y alertas**
- Los datasets son artefactos versionados con entrada, salida esperada y metadatos (en la demo: "Golden" v1, una versión en español y uno de seguridad). Un experimento corre una versión de un dataset con evaluadores y produce scores numéricos, binarios o categóricos; hay templates y se pueden crear evaluadores propios.
- Alertas: un motor de monitoreo en tiempo real que dispara acciones. Lo más interesante para el docente es conectarlas con GitHub Actions para un rollback automático ante una degradación fuerte. No estaba configurado; lo armará.
- Langfuse será el orquestador al que se sumen Ragas, PyRIT, Garak y otros. En el chat un alumno listó PyRIT, RAGAS, Giskard y promptfoo.

**[01:56] El pipeline de tres capas**
- Capa 1: Langfuse consolida scores y aplica el gate; si no alcanzan el umbral, la versión no se promueve. Lo que se promueve incluye prompts, datasets y experimentos congelados, como evidencia. Capa 2: tráfico en vivo. Capa 3: las observaciones se curan y vuelven al ciclo. Es el mapa de la [clase 8](clase-08.md); la slide 108 está en [La arquitectura completa](../notas/arquitectura-completa.md).

**[01:59] Cierre y consultas**
- Un alumno comentó que se suele ver solo la punta del iceberg; el docente mostró la slide de la charla informativa. Lo que se trabaja ahora está por debajo de la punta, ligado al "famoso 95 %" de proyectos agénticos que no llegan a producción. La disciplina evoluciona de MLOps a LLMOps; la gobernanza se implementa como código versionado, parte del pipeline.
- [02:04] El proyecto demo irá al repo, adaptado y en pasos. No es una tarea entregable ni hace falta implementarlo.
- [02:13] Una arquitectura de referencia completa es la situación ideal: el docente no la ve entera en sus clientes. Conviene empezar chico y sumar complejidad cuando haga falta. Habrá dos encuentros de seguridad.
- [02:16] No se verá fine-tuning: el Módulo 7 quitó las técnicas que reentrenan modelos. Podría haber una clase opcional al final. También reentrenar con refuerzo, cuantizar o destilar tienen riesgos importantes.

## Conceptos clave
- **Traza vs. log:** el log responde una pregunta puntual; la traza reconstruye el turno.
- **OpenTelemetry:** protocolo común hacia Langfuse; permite cambiar de vendor.
- **SLO:** valor prometido sobre una ventana de tiempo; da sentido al umbral.
- **Shadow y canary:** exponer una versión nueva sin arriesgar a todos.
- **Gate:** umbral sobre scores consolidados que decide la promoción.

## Demos y ejemplos mostrados
- Portal y agente del banco (LangGraph), con trazas en Langfuse v4 y en una APM tradicional.
- Recorrido de Langfuse (trazas, scores, anotación humana, dashboards, prompts, datasets, experimentos, alertas) y pedidos a Claude Code con su skill y MCP. No se mostró el código del agente.

## Recomendaciones y advertencias del docente
- Diseñar la observabilidad junto con el agente, no al final.
- Enmascarar datos sensibles en el agente antes de enviarlos: Langfuse no filtra.
- Versionar prompt, dataset, modelo y embeddings; si no, el experimento no vale.
- Tipar y nombrar bien las observaciones; evitar el ruido de infraestructura.
- Pedirle a Claude lo repetitivo.

## Preguntas de la clase que vale la pena recordar
- ¿Cómo llegan los datos a Langfuse? → ADK vía OpenInference y OpenTelemetry; LangGraph con pocas líneas de instrumentación.
- ¿Langfuse clasifica los riesgos? → No, los manda el agente.
- Si el prompt vive en Langfuse, ¿el agente depende de él? → No; se puede copiar al código tras el release.
- ¿Cómo se hace A/B de prompts en producción? → Dos versiones desplegadas y tráfico repartido.

## Anuncios, tareas y material referenciado
- Sin entregas ni tareas formales.
- Próxima clase: martes 3/11. Sigue el módulo: señal semántica en producción, stacks de referencia, patrones de despliegue progresivo y métricas de drift. Después, seguridad.
- Pendientes del docente: subir el proyecto demo, compartir el texto sobre SLI y SLO y armar el rollback con GitHub Actions. Atiende consultas por mail.
- Repo (verificado, no citado en clase): `MODULO_10/El Gap de Observabilidad en agentes` y `MODULO_10/PAI_obervability-gap-in-ai-agents.pdf`. La nota resume un informe de la Partnership on AI sobre OpenAI Agents SDK, Claude Agent SDK, LangGraph y CrewAI. Separa la capa de ejecución ("qué hizo el agente"), resoluble extendiendo OpenTelemetry, de la cognitiva ("cómo decidió": cadena de razonamiento y log-probs), hoy bloqueada a nivel de proveedor del modelo. Pide exigir telemetría y exportación de estado al elegir frameworks, y auditoría de caja blanca en dominios de alto riesgo.
