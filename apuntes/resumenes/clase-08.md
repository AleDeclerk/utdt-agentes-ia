# Clase 8 · 22/10 · Evals y métricas: trayectoria, resultado y el problema del "92 %"

**Docente e invitados:** Matías Zabaljauregui (sin invitados).
**Material del campus:** Slides "Evals y métricas"; material complementario "Handbook y Reporte 2026". Código de apoyo: `MODULO_9/DEMOS`.

## En una frase
Introducción a las evaluaciones offline de agentes: por qué un "92 %" suelto no informa nada y cómo medir trayectoria y estado final con métricas de herramientas, parámetros y frases.

## Recorrido de la clase

**[00:00] Apertura y mapa de tres capas**
- En la otra comisión casi nadie había armado infraestructura mínima de evals. Motivo de la clase: sin instrumentación no hay señales para decidir qué mejorar en el próximo sprint.
- Capa 1: evals offline antes del despliegue (hoy). Capa 2: monitoreo en tiempo real (módulo 10). Capa 3: aprendizaje y automejora, un flywheel que convierte lo observado en casos nuevos.
- Los benchmarks públicos dan una línea base; hace falta un conjunto propio. Los scores alimentan gates que promueven versiones a stage o producción con GitHub Actions y MLflow (lógica de AgentOps, heredera de MLOps).
- Comenta un reporte 2026 recién publicado, con entrevistas a grandes empresas: según él, incluso en producción falta infraestructura de evals, observabilidad y trazabilidad. Compartirá un resumen de sus problemas de evaluación.

**[00:15] Experiencias de los asistentes**
- Casos contados: clasificador con revisión humana como juez, tabla de logs con herramientas llamadas, y DeepEval para métricas semánticas de RAG (explica por qué falló cada test).
- El docente pide separar IA generativa de agentes (múltiples pasos, herramientas). Código, humanos y modelos como jueces hacen falta los tres para escalar.
- ADK 2 emite telemetría con OpenTelemetry sin instrumentar a mano (sirve con Tempo, Loki, Grafana o Langfuse).

**[00:25] El problema del "92 %"**
- Offline (antes del despliegue) y online (tráfico real) se complementan.
- Sin evals hay superficies de ataque expuestas, daño reputacional y económico, o el proyecto se cae.
- Crítica del "92 %": no dice de qué (éxito de tarea, satisfacción) ni sobre cuántas corridas. Con n menor a 30 la estimación puntual no tiene peso estadístico y alimenta el sesgo de confirmación. Hace falta un intervalo de confianza.

**[00:44] Trayectoria y resultado**
- En sistemas multipaso un error temprano se arrastra y se amplifica. Puede haber efectos secundarios irreversibles (p. ej. una transacción indebida) con un resultado final aparentemente correcto.
- Dos "sondas" (diagnósticos): trayectoria (herramientas, parámetros, respuesta, tono) y estado final del mundo. Referencia: el benchmark τ-bench (2024).
- Ejemplo guía: soporte de un marketplace, cliente con un ítem roto que pide reembolso. Cada caso define trayectoria, respuesta y mundo final esperados.

**[00:49] Crear casos y qué ofrece ADK**
- Empezar con casos manuales (expertos de dominio, producto); luego logs, generación con modelo (revisada a mano) y benchmarks como línea base.
- Técnicas: adversarial (reclamos contradictorios, ambiguos o maliciosos), variaciones mínimas de palabras (término dudoso) e interpolación distribucional (mezclar dos intenciones, que rompe clasificadores de intención). Dejar casos hold-out para no sobreajustar.
- La plataforma de agentes de Google (Next 26) tiene cuatro pilares: Build, Scale, Govern, Optimize (nombre exacto dudoso). Optimize soporta el feedback loop.
- ADK 2.12 representa casos y sets, corre invocaciones, trae métricas por defecto y propias, agrega por promedio, suma o peor caso, y simula usuarios y mundos sintéticos. Se ve en la consola de Google Cloud o en Langfuse.

**[01:05] Precisión, recall y F1 (nivelación)**
- Un alumno explicó con un test médico que los falsos positivos y negativos cuestan distinto según el dominio. El docente sumó que mover la frontera de decisión mejora una métrica a costa de la otra.
- F1 es la media armónica: penaliza la divergencia, pero no mira los true negatives y pesa igual precisión y recall.

**[01:18] Métricas de trayectoria**
- La matriz de confusión se mapea a llamadas: herramienta esperada y llamada es acierto; llamada de más baja la precisión; omitida baja el recall.
- `tool_recall` y `tool_precision` no ven parámetros. La exactitud de parámetros no detecta acciones de más (eso requiere un juez). `phrase_recall` no ve paráfrasis ni prueba que la acción ocurrió.
- Una tabla de cuatro corridas mostró que trayectoria y estado final se complementan: lo común es que una pase y la otra no. El éxito de trayectoria exige que todos los scores superen su umbral.

**[01:43] Demo 1 y cierre**
- Matriz de once corridas y recorrido del código (ver demos). [01:55] Se difieren las slides restantes a la próxima clase.
- [02:03] La capa 1 es un gate automático; la 2 captura señales solo visibles en producción; la 3 las vuelve casos nuevos. Los cambios silenciosos del proveedor se detectan con observabilidad.

## Conceptos clave
- **Ficha de una métrica:** unidad que se compara; emparejamiento (léxico o semántico, orden, repeticiones); qué hacer con el denominador 0; agregación.
- **Denominador 0:** no se esperaba ni se hizo ninguna llamada. ADK lo configura; un estudio de 2025 halló que τ-bench puede contar respuestas vacías como éxito.
- **Agregación:** ante fallos catastróficos (diagnóstico médico) se usa el peor caso: importa el 5 % que falla.
- **Estado final del mundo:** variables que el agente modificó, contra el mundo ideal.
- **Reward hacking:** explotar un objetivo mal especificado.
- **Drift:** cambios de usuarios, datos o del modelo del proveedor que degradan un agente sin tocar su código.
- **Sesgos de los jueces (adelanto):** posición, verbosidad y autopreferencia.

## Demos y ejemplos mostrados
- **Demo 1 "zoológico":** `demos/demo1_zoologico.py` (según el README del repo, cuesta $0 porque no llama al modelo). Once corridas guionadas de variantes de la misma tarea, con la etiqueta humana (aceptable o no) fijada antes de medir. La matriz marca, por métrica, falsos aciertos y falsos rechazos.
- **Conclusión:** ninguna métrica sola acierta las once; hay que combinarlas. El tablero muestra también ROUGE y BLEU, pendientes.

## Recomendaciones y advertencias del docente
- Armar evals ya en los propios agentes, con pocos casos y un framework. Cualquier cambio de prompt, versión o workflow obliga a re-evaluar.
- Versionar de forma inmutable datasets y experimentos, para auditoría.
- Cambios granulares y rollout progresivo: A/B testing, shadow o canary (módulo 10).
- En un flujo determinista casi no tiene sentido medir la selección de herramientas. Reforzar el system prompt es un parche que no le gusta.

## Preguntas de la clase que vale la pena recordar
- ¿Cómo justificar el esfuerzo extra ante el negocio? → Con métricas de negocio (ahorro, expansión); además se subestima el riesgo, y conviene preguntar si hace falta un agente donde ya hay algo determinista y rápido.
- ¿Hace falta una herramienta de soporte? → Se empieza a mano; los tableros sirven cuando el set crece.
- ¿ADK permite fijar el orden de las llamadas? → Sí: lista exacta o no, con orden o sin él, con repeticiones o sin ellas.
- ¿La métrica de frases falla con paráfrasis? → Sí; es una debilidad de las métricas sin modelo.

## Anuncios, tareas y material referenciado
- Tarea: armar evals sobre los propios agentes y contar cómo les fue.
- Próxima clase: jueces con rúbricas, κ de Cohen, métricas de RAG, métricas por componente, evals end-to-end, simulación de usuario y mundo, intervalo de Wilson, Demos 2 y 3.
- Herramientas: DeepEval, Langfuse, MLflow, GitHub Actions, Promptfoo, PyRIT, Giskard.
- Compartirá un texto sobre precisión y recall, el resumen del reporte y una charla sobre evals (título dudoso). Prepara una demo de banca con Langfuse.
- Consultas hasta las 20:30.
