# El ciclo de vida de un agente según agents-cli (Google)

**Fuente:** [The lifecycle · agents-cli](https://google.github.io/agents-cli/guide/lifecycle/), guía oficial de Google, actualizada el 4/11/2026. Leída el 19/11/2026. No es material del curso.

`agents-cli` es la herramienta de Google para llevar un agente ADK desde el notebook hasta producción. Lo interesante no es la herramienta sino el ciclo que propone. Es el mismo mapa de [la arquitectura completa](arquitectura-completa.md), contado desde el desarrollo en vez de desde la seguridad.

## La idea

Definir el agente es lo fácil: modelo, instrucción y tools son unas 30 líneas. Lo que separa una demo de un producto es lo que rodea al agente:

- una **evaluación** que frena el release si el agente propone algo peligroso,
- un **test de integración** que detecta cuando una tool cambia de contrato,
- una **traza** que permite reproducir una corrida concreta cuando algo sale mal.

El ciclo corto es `scaffold → eval → deploy → observe`, y vuelve a empezar.

## Las ocho fases

| # | Fase | Qué se hace | Comando |
|---|---|---|---|
| 0 | Spec | Un archivo `.agents-cli-spec.md` con tools, restricciones y criterios de éxito. Todo lo demás se deriva de acá | — |
| 1 | Scaffold | El spec se convierte en un proyecto con forma de producción (~60 archivos: código, tests, evals, Terraform, CI/CD) | `create` |
| 2 | Build | El cuerpo del agente: modelo, instrucción y tools | — |
| 3 | Orchestrate | Cuando un agente crece, se parte en un orquestador y especialistas, cada uno con sus tools | — |
| 4 | Evaluate | Un dataset de casos y un LLM juez con rúbricas. Con umbral, el comando sale con error si no llega | `eval run` |
| 5 | Deploy | El mismo código va a un runtime gestionado, a un contenedor o a un cluster | `deploy` |
| 6 | Publish | Registrar el agente en un catálogo para que otros lo encuentren | `publish` |
| 7 | Observe | Trazas por tool, por modelo y por sub-agente, más analítica. Los casos que fallan vuelven al dataset | — |

## Lo que vale más allá de Google

1. **El spec es la fuente de todo.** Los criterios de éxito se escriben antes del código y son medibles ("100 % de las recomendaciones citan una sección del runbook", "0 acciones destructivas sin respaldo"). De ahí salen las rúbricas, los guardrails y los atributos de la traza.
2. **Las restricciones van en el spec, no en el prompt.** "Nunca recomendar una acción destructiva si el runbook no la autoriza" es una regla que se evalúa, no una frase que se espera que el modelo respete.
3. **El agente recomienda, la persona confirma.** En el ejemplo, el agente diagnostica y propone la acción, pero no la ejecuta: un humano tiene que confirmar.
4. **La eval es un gate de CI, no un reporte.** Se itera entre 5 y 10 veces hasta pasar el umbral. Cuatro fallas típicas y quién las atrapa:

   | Falla | La detecta |
   |---|---|
   | Dice que llamó a una tool que nunca llamó | Comparar las llamadas reales contra la trayectoria esperada |
   | Afirma cosas que las tools no devolvieron | Chequear cada afirmación contra el contexto de las tools |
   | Un mensaje inyecta instrucciones para saltear reglas | Rúbrica de seguridad, más un filtro en tiempo de ejecución |
   | Se va del tema | Rúbrica de relevancia de la respuesta final |

5. **Partir en especialistas sirve por tres razones:** prompts más chicos son más confiables, cada especialista tiene sus propios guardrails, y la traza dice exactamente cuál falló.
6. **El agente tiene identidad propia.** Corre con una identidad de mínimo privilegio, no con una cuenta compartida. Si la identidad no puede borrar, el agente no puede borrar aunque la eval falle. Es la segunda línea de defensa.
7. **El modelo es intercambiable.** Cambiar de proveedor es una línea; eval, deploy y observabilidad no cambian. Por eso la eval tiene que ser independiente del modelo.
8. **El ciclo se cierra a mano.** Nada pasa los casos de producción al dataset solo: alguien tiene que mirar las trazas y agregar los que fallaron. Es el flywheel de la [clase 8](../resumenes/clase-08.md).

## Problemas que el ciclo resuelve

| Sin el ciclo | Con el ciclo |
|---|---|
| Una acción inventada la descubre el cliente | La rúbrica bloquea el PR antes del merge |
| Una API de una tool cambia y el agente se rompe en silencio | El test de integración detecta el cambio de esquema |
| Un mal uso en producción no se puede reproducir | La traza y la analítica lo muestran en horas |
| Una tool que se llama de más dispara el costo | El conteo de spans por tool lo muestra en horas, no en la factura |

## Cómo se conecta con el curso

- **Fases 0, 1 y 4** = la capa de pre-deployment ([clase 8](../resumenes/clase-08.md), evals offline).
- **Fases 5 y 6** = el despliegue con identidad propia y acceso controlado ([clase 10](../resumenes/clase-10.md) y la capa de defensa en tiempo real).
- **Fase 7** = observabilidad con trazas ([clase 10](../resumenes/clase-10.md), OpenTelemetry) y el flywheel de vuelta a la fase 4.
