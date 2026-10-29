# Clase 4 · 06/10 · Herramientas y Model Context Protocol (MCP)

**Docente e invitados:** Matías Zabaljauregui. Sin invitados.
**Material del campus:** Slides Intro Tools-MCP, Slides Módulo 4, Slides Conceptos Técnicos. Contexto del repo: `MODULO_4` (labs de MCP y reportes).

## En una frase

Inicio del módulo 4: tipos de herramientas, la metadata de una tool como parte del diseño, y MCP como protocolo cliente-servidor que baja el problema M×N a M+N, con demos en ADK 2 (una falló en vivo por una alucinación).

## Recorrido de la clase

**[00:00] Apertura y LiteLLM**
- Un alumno preguntó si LiteLLM, usado en el ejemplo multimodelo anterior, es práctica habitual. Respuesta: sí, es un adaptador/gateway muy usado para enchufar modelos distintos y rutear dinámicamente; en el curso no se usa para rutear. Mencionó que tuvo problemas de seguridad de cadena de suministro.

**[00:08] Qué es MCP**
- Un alumno lo definió como un protocolo entre agente y sistemas, parecido a una API pero para agentes. El docente lo validó.
- Anthropic lo publicó como estándar abierto para la comunicación vertical (agente-herramientas). La horizontal (agente-agente) es A2A de Google. Ambos quedaron bajo la Linux Foundation; propuestas rivales (Cisco, IBM) convergieron en ellos.
- El LLM no habla MCP: lo hace el agente o framework.

**[00:12] Tipos de tools y regla de oro**
- Cuatro ejes del módulo: MCP, mínimo privilegio, diseño de tools e implementación en ADK. Desde acá los errores tienen consecuencias reales (por ejemplo, escribir en una base).
- Tipos: locales (funciones Python en el mismo proceso, predecibles pero exigen redesplegar), basadas en API (wrapper HTTP: rate limits, caídas, autenticación, secretos, reintentos) y MCP.
- El modelo nunca ve el código, solo nombre, descripción y esquema. Tres reglas: nombre preciso (mejor uno verboso que `execute_query`), descripción sin solapamiento y con cláusula negativa ("cuándo no usarla"), y esquema estricto (Pydantic, rangos, enumeraciones cerradas).
- Mencionó los naming attacks: servidores copiados con mejor nombre y descripción para ganar el discovery.

**[00:32] Informes del docente**
- Dos trabajos en la carpeta de recursos: un análisis de casi 100 servidores MCP públicos, con vulnerabilidades explotables en servidores de alto perfil, y un informe sobre la evolución de MCP. Del primero dijo que estaba en revisión de pares y pidió no difundirlo, pero enseguida se corrigió: ya está aprobado (figura en su LinkedIn) y se puede compartir.
- Cambios recientes: el protocolo dejó de ser stateful y se abandonó SSE; quedó Streamable HTTP con JSON-RPC.

**[00:35] El problema M×N**
- Sin protocolo, cada aplicación de IA (M) necesita integración propia con cada herramienta (N), con autenticación, formato y versionado distintos.
- Con MCP cada aplicación implementa el cliente una vez y cada recurso el servidor una vez: las integraciones se suman en vez de multiplicarse.
- Un alumno contó que con Claude Code armó un servidor MCP local que envuelve la API de una herramienta de grabación de reuniones. El docente lo tomó como caso válido.

**[00:49] Host, cliente, servidor y topologías**
- El host (nuestro agente) contiene un módulo cliente MCP. El LLM solo recibe una lista de tools, sea cual sea el backend.
- Topologías: un servidor por API, un servidor compuesto y el MCP gateway con servidores virtuales jerárquicos, que centraliza gobernanza, seguridad y observabilidad. Advirtió sobre la experimentación no gobernada (transcripción dudosa sobre "shadow").

**[01:00] Cómo funciona**
- El servidor expone métodos por JSON-RPC 2.0. Dos definen el protocolo: listar tools (nombre, descripción, esquema) y llamar una tool. Separar descubrimiento de ejecución es el corazón del diseño.
- Si el servidor agrega una tool, el agente la ve sin cambios. Transportes: stdio para procesos locales y Streamable HTTP para remotos.

**[01:06] Demos en ADK** (ver sección de demos)

**[01:47] Modelo y temperatura**
- Un alumno notó que con un modelo más nuevo la demo no alucinaba; el docente tenía pendiente actualizarlo por avisos de Google.
- Otra alumna señaló que la temperatura se fija en `generate_content_config`. El docente explicó temperatura y top-k como muestreo sobre la última capa de probabilidades, y aclaró que solo afectan la generación.

**[01:57] Preguntas finales y cierre**

## Conceptos clave

- **MCP:** especificación abierta, no un producto, para conectar agentes con herramientas y datos.
- **Host, cliente, servidor:** el host es el agente o framework, el cliente es el módulo que habla MCP dentro del host, el servidor expone las tools.
- **Problema M×N:** integraciones a medida entre M aplicaciones y N recursos. MCP lo reduce a M+N.
- **Discovery en tiempo real:** el agente consulta qué tools hay al conectarse.
- **Mínimo privilegio:** eje de seguridad del módulo, que se retoma en gobernanza.

## Demos y ejemplos mostrados

Todas con `adk web` sobre una carpeta de ejemplos y datos simulados.
1. **Clima (servidor propio):** `McpToolset` con `StdioConnectionParams` lanza un script con FastMCP y funciones `@mcp.tool` (clima actual, pronóstico, listar ciudades). Al pedir las ciudades, el modelo las inventó sin llamar al servidor (el trace nunca mostró la llamada). Diagnóstico: prompt demasiado flojo. Solución propuesta: prompt estricto y un `before_model_callback`. Con "Tucum" no hay búsqueda semántica: el modelo infirió Tucumán.
2. **Filesystem:** servidor MCP instalado al vuelo con `npx`, sobre una carpeta sandbox. Tools vistas en el trace: listar directorio y leer archivo.
3. **Google Maps local:** servidor descargado y corrido en la máquina que llama la API de Google Maps. Respondió bien, pero el docente lo calificó de raro y deprecado.
4. **Google Maps remoto (grounding lite):** `StreamableHTTPConnectionParams` con endpoint remoto y autenticación. Invierte la relación: solo corremos el cliente. Devolvió clima real; aún sin indicaciones de ruta.

## Recomendaciones y advertencias del docente

- No mostrar a un cliente un agente en este estado; él se negó a hacerlo en un caso real.
- Prompts estrictos y callbacks para que el modelo no complete de memoria lo que debe traer de la tool.
- Preferir servidores MCP oficiales a los comunitarios e investigar su reputación.
- Para auditorías: versión vigente del protocolo, sin features deprecadas, y revisar la taxonomía de vulnerabilidades MCP de OWASP (nombre dudoso en la transcripción).

## Preguntas de la clase que vale la pena recordar

- **¿Se actualiza el cliente cuando el protocolo suma propiedades?** → El LLM no se entera; el framework maneja el protocolo.
- **¿Hay búsqueda semántica si escribo mal una ciudad?** → No estaba implementada; el modelo infirió el nombre.
- **¿La temperatura evita esta alucinación?** → No; solo afecta la generación, no si se llama la tool.
- **¿Qué pasa si un proveedor cambia algo sin avisar?** → Agregar tools no rompe nada por el discovery; el riesgo es que no actualice la versión del protocolo. Las features deprecadas suelen convivir cerca de un año.

## Anuncios, tareas y material referenciado

- Sin tareas ni entregas.
- Faltan subir las slides de las clases 2, 3 y 4, más material complementario.
- Los dos informes están en la carpeta de recursos de `MODULO_4`.
- Carpetas del repo: `labs_MCP` y `links_reportes_MCP`.
- El docente dio su correo personal para consultas (autenticación y autorización, por ejemplo).
- Próxima clase: jueves a las 18 h, orquestación. Gateway MCP y seguridad se verán más adelante.
