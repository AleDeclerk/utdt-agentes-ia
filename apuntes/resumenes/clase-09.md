# Clase 9 · 27/10 · Validación y medición: jueces LLM, kappa, Ragas, pass@k y Wilson

**Docente e invitados:** Matías Zabaljauregui. Sin invitados.
**Material del campus:** solo la grabación, sin slides. En pantalla: el deck "Validación y Medición" (Módulo 9) y dos grupos de slides complementarias (jueces y estadística, regulación).

## En una frase
Segunda parte del Módulo 9: cómo usar LLMs como jueces, por qué un "92 % de éxito" de una sola corrida no sirve y qué métricas (kappa de Cohen, pass@k, pass^k, intervalo de Wilson) exigen hoy los reguladores.

## Recorrido de la clase

**[00:00] Apertura y mapa del módulo**
- En esta comisión nadie tenía evaluaciones implementadas. Dos ejes: qué reportar más allá de la accuracy y qué intervalos de confianza pide la industria.
- Se retoma la matriz de confusión de la demo 1. El stack se acerca a un pipeline CI/CD real con tres capas: offline (pre-deploy), controles en ejecución y un flywheel que convierte trazas reales en nuevos casos de evaluación.

**[00:08] LLM como juez: criterios vs rúbricas**
- Entre los cuatro escalones de la slide, el foco es el cuarto, el más estándar: telemetría OpenTelemetry integrada en Langfuse (o MLflow), que produce un score; un gate en GitHub Actions decide si el candidato pasa a producción.
- Juez por criterios (ejemplo: alucinaciones): el framework parte la respuesta en oraciones y contrasta cada una con lo que devolvieron las herramientas, según la traza. Sin respaldo, hay indicio de alucinación.
- Juez por rúbricas: criterios en lenguaje natural; se muestrea n veces y se agrega (promedio o voto mayoritario).
- ADK 2 trae ambos como clases que solo se configuran, sin instrumentar el código.

**[00:19] Costo, sesgos, varianza y gobierno del juez**
- Costo: el juez por criterios hace unas dos llamadas por respuesta; el de rúbricas, una por corrida; el razonamiento suma tokens. Todo cambio (prompt, framework, chunking, indexado) obliga a reevaluar, así que se usan cascadas de jueces y corridas periódicas.
- Sesgos: de posición, de verbosidad y de autopreferencia. Conviene mezclar jueces de distintas familias o proveedores.
- Varianza: el mismo juez puede dar veredictos distintos. El juez es un componente más: se mide, se valida y se versiona.

**[00:30] Versionado y Langfuse**
- Versionar es tratar dataset y prompt como código, para no comparar experimentos incomparables en una auditoría.
- Langfuse integra telemetría de otras herramientas (DeepEval, por ejemplo). Es open source y el docente lo corre en Docker; el cloud tiene planes pagos. Un alumno citó LangSmith con plan gratis de 5.000 trazas al mes.

**[00:36] Kappa de Cohen**
- Un eval set sin ejemplos negativos da acuerdo humano-juez altísimo y no sirve. F1 ignora los verdaderos negativos; kappa descuenta el acuerdo por azar y el desbalance de clases.
- Rangos (de un paper antiguo): negativo, peor que el azar; 0 a 0,2, azar; 0,2 a 0,4, insuficiente, no va a producción ni a staging; 0,4 a 0,6, riesgo bajo o revisión humana obligatoria; 0,6 a 0,8, apto para la mayoría de usos industriales; 0,8 a 1, requerido en sistemas críticos (seguros, legal, salud, banca, fintech).

**[00:53] Ragas y calidad del retriever**
- En un agente con RAG fallan dos sitios: el recuperador (info incorrecta, faltante o con ruido) y el generador (usa mal el contexto o inventa).
- Métricas de Ragas (2023), sin referencia humana en las primeras: fidelidad, relevancia de la respuesta, precisión y recall del contexto. Para la relevancia, genera preguntas a partir de la respuesta y compara con la original.
- Fidelidad alta no implica respuesta correcta: la base puede estar desactualizada o el proveedor cambió el modelo de embeddings sin cambiar el nombre. Fidelidad alta con relevancia baja: responde fiel a los chunks, pero otra pregunta.
- Dos familias de evaluación: por componente y por resultado (éxito de tarea, consistencia, coherencia multiturno con usuario simulado, alucinaciones).

**[~01:15, aprox.] pass@k, pass^k y Wilson**
- Una sola corrida no tiene peso estadístico; con menos de 30 muestras, hay ruido.
- pass@k (techo de capacidad): probabilidad de que al menos uno de k intentos acierte. Respuestas: human in the loop o Best-of-N (reintentos paralelos con validador).
- pass^k (consistencia): probabilidad de acertar los k intentos, p^k. Con p = 0,8 y k = 3 baja a 51 %. En transacciones financieras debe ser alto.
- Wilson reemplaza al intervalo normal clásico porque el experimento es binomial y con n chico.
- Plantilla de la slide: 50 tareas, k = 5, 250 trazas, 95 %. pass@5 de 92 % con cota inferior de 81 %; pass^k de 72 % con k = 1 cae a 26 % con k = 4, y la cota inferior llega a 18 %.

**[01:39] Regulación y experiencias de alumnos**
- EU AI Act: art. 15 (precisión y robustez declaradas), art. 9 (riesgo), art. 14 (supervisión humana). No aceptan estimaciones puntuales: la cota inferior de Wilson debe cumplir el umbral legal. En banca y fintech: pass^k de 99,9 % y cota inferior sobre 99 %.
- Alumnos de banca y seguros: predomina el human in the loop; una aseguradora prohíbe agentes en reclamos o pagos; en antilavado el LLM falla con documentos mal escaneados.

**[01:58] Argentina**
- BCRA (según el docente): inventario de componentes de IA, métricas de confiabilidad documentadas, datos versionados, trazabilidad inmutable (WORM) y límites sobre regiones cloud. También aplican la Ley de Defensa del Consumidor, la de datos personales e ISO 27001.

## Conceptos clave
- **LLM como juez:** modelo que puntúa; no es un oráculo y no es determinista.
- **Control negativo:** casos de error en el eval set; sin ellos kappa no dice nada.
- **Kappa de Cohen:** acuerdo humano-juez corregido por azar.
- **Best-of-N:** paralelizar el agente y elegir la mejor salida con un validador.
- **Optimismo estadístico:** reportar sin cota ni varianza; las auditorías lo rechazan.

## Demos y ejemplos mostrados
- Demo 1: matriz de confusión con métricas simples. Demo 2: kappa por corridas y modelos contra humanos, con estimación de costo por parámetro. Demo 3: el "92 %" sin tamaño muestral. El código se salteó a propósito.
- Langfuse local en Docker.

## Recomendaciones y advertencias del docente
- Empezar a evaluar ya, aunque sea con dos métricas simples; cada cambio exige una corrida nueva.
- Nunca reportar una única corrida ni un número sin intervalo; incluir la cota inferior.
- Kappa menor a 0,4: seguir iterando. Estimar el costo del juez antes de elegirlo.
- Incluir validaciones de trato desigual.

## Preguntas de la clase que vale la pena recordar
- ¿El juez no sale caro? → Sí; se usan cascadas de jueces y corridas periódicas.
- ¿Fidelidad alta implica respuesta correcta? → No necesariamente.
- ¿Debe evaluar alguien independiente de quien construye el agente? → Sin respuesta registrada (la transcripción corta en [02:09]).

## Anuncios, tareas y material referenciado
- Sin entregas formales. Se pidió revisar las slides complementarias y su PDF, y bajar Ragas para probar los retrievers.
- Próxima clase: jueves; arranca observabilidad en producción. Garak, PyRIT y Promptfoo llegan con seguridad (módulo 12, según el docente).
- Un alumno ofreció compartir material de un evento y una compilación regulatoria.
- Repo (verificado, no citado por ruta en clase): `MODULO_9/Evaluation_metrics_handbook.pdf`, `MODULO_9/DEMOS`.
