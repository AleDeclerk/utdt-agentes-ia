# Guía de la demo: un grafo de conocimiento de talento con Neo4j y un agente (ADK 2)

Esta guía te lleva, paso a paso, por el mismo recorrido que hicimos en clase con la demo de talento. En el **módulo 1** explorás un grafo de conocimiento en Neo4j (personas, skills, similitudes, embeddings y comunidades). En el **módulo 2** le ponés encima un agente de ADK 2 que lo consulta con herramientas.

En cada paso encontrás: una explicación de qué hacemos y por qué, las consultas para copiar al visualizador de Neo4j, qué deberías ver y en qué archivo del código está implementado. Algunos pasos terminan con preguntas frecuentes.

## Antes de empezar

- Seguí el `README.md` (instalación, tu API key en `.env`) y después, desde esta carpeta: `./run.sh up`, `./run.sh 01` y `./run.sh check`. El grafo tiene que quedar con 100 personas.
- Abrí el visualizador de Neo4j en <http://localhost:7475>. Conexión: `bolt://localhost:7688`, usuario `neo4j`, clave `demo-talent-local` (si cambiaste los puertos o la clave en `.env`, usá tus valores).
- Para el módulo 2, abrí el agente con `./run.sh web` y entrá a <http://localhost:8000> (elegí «reclutador»).
- En el visualizador: **pegá la consulta** y ejecutala con `Ctrl+Enter`. Si devuelve nodos o caminos (`p`) se ve un **grafo**; si devuelve valores, una **tabla**.
- **Un clic** en un nodo o una relación muestra sus propiedades. **Doble clic** en un nodo trae a sus vecinos (hacelo sobre una *skill*: una persona tiene unas treinta relaciones y se llena de líneas). Arrastrá para mover y usá la rueda para el zoom.
- Para cambiar el color, el tamaño o el texto de un tipo de nodo, clic en su etiqueta (`Person`, `Skill`) arriba del resultado. El color es **por etiqueta**, no por el valor de una propiedad.
- Las consultas marcadas **«Ya hecho: solo para leer»** son para leer y entender (ya se ejecutaron al construir el grafo); las **«Solo para leer»** son código de Python o texto.
- **Sobre las cifras:** los datos de las personas, las relaciones de skills compartidas y las comunidades son siempre los mismos. Las similitudes *semánticas* (los puntajes y cuáles skills salen como «parecidas») dependen del modelo de embeddings: en clase se usó otro modelo, así que esas cifras pueden diferir un poco de lo que viste, y una relación que cae justo en el umbral puede aparecer o no.
- Si querés empezar de cero: `./run.sh reset`, `./run.sh up` y `./run.sh 01`.

## Módulo 1 — Fundamentos del grafo

### 1.1 · Los datos de partida

Para este caso de uso —buscar talento, formar equipos, ver quién puede cubrir a quién— empezamos con un dataset muy simple.

Es una tabla con tres campos: el email de cada persona, su nombre y la lista de skills que conoce. Son cien personas y cincuenta y cuatro skills distintas.

Los datos son sintéticos y las skills de cada persona son aleatorias. No esperes patrones reales: sirven para ver cómo funciona todo.

Esta tabla ya está cargada en el grafo (la cargó `./run.sh 01`). Con esta consulta la reconstruimos para verla.

**Consultas**

**Skills de cada persona (reconstruye la tabla)** — *Tabla*

```cypher
MATCH (p:Person)-[:KNOWS]->(s:Skill)
RETURN p.email AS email, p.name AS person_name, collect(s.name) AS skills
LIMIT 10
```

**Qué deberías ver:** Una fila por persona, con su email y la lista de sus skills.

**Dónde está en el código**

- `datos/expanded_skills.csv` — la tabla de partida: email, nombre y lista de skills de cada persona (datos sintéticos; la baja `./run.sh datos`)
- `grafo_talento.py` — `cargar_personas_y_skills()` lee el CSV y lo carga en el grafo

### 1.2 · Conectar y probar la conexión

Antes de seguir, comprobamos que estamos conectados y cuántos nodos hay.

Como ya está todo cargado, tendría que dar ciento cincuenta y cuatro: cien personas más cincuenta y cuatro skills.

**Consultas**

**Contar nodos** — *Tabla*

```cypher
MATCH (n)
RETURN count(n) AS nodos
```

**Qué deberías ver:** Un solo número: 154.

**Dónde está en el código**

- `comun.py` — `driver()` abre la conexión (`bolt://127.0.0.1:7688`); `leer()` ejecuta consultas en una sesión de solo lectura

### 1.3 · Restricciones (constraints)

Lo primero que se hace antes de cargar datos es declarar restricciones. Le decimos a Neo4j que el email identifica a una persona y que el nombre identifica a una skill: no puede haber dos iguales.

Esto tiene dos efectos: buscar y hacer MERGE se vuelve muy rápido, y no se duplican nodos.

Es común escuchar que Neo4j es lento. Muchas veces la causa es no haber definido esta restricción: entonces cada búsqueda de una persona es una búsqueda complicada en lugar de ir a un índice único.

Hacemos lo mismo con las skills, porque nuestro modelo tiene dos tipos de nodo: persona y skill.

**Consultas**

**Ver las restricciones que existen** — *Tabla*

```cypher
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
```

**Cómo se crean (ya hechas, no ejecutar)** — *Ya hecho: solo para leer, no la ejecutes*

```cypher
CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE;
CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE;
```

**Qué deberías ver:** Dos restricciones: una sobre el email de las personas y otra sobre el nombre de las skills.

**Dónde está en el código**

- `grafo_talento.py` — `esquema()` crea las restricciones de unicidad (`Person.email`, `Skill.name`) y el índice vectorial

### 1.4 · Cargar personas, skills y la relación KNOWS

Ahora la carga. La idea es muy simple y se repite para cada fila de la tabla.

Primero hacemos MERGE de la persona usando su email, y le ponemos el nombre. Después, para cada skill de su lista, hacemos MERGE de la skill usando su nombre, y MERGE de una relación que dice que esa persona conoce esa skill.

El resultado es el patrón que vamos a usar todo el tiempo: persona conoce skill.

Esto ya está hecho. La consulta es para leerla, no para ejecutarla (necesita los datos de la tabla como parámetro).

**Consultas**

**La carga (ya hecha, no ejecutar: necesita los datos de la tabla)** — *Ya hecho: solo para leer, no la ejecutes*

```cypher
UNWIND $rows AS row
MERGE (p:Person {email: row.email})
SET p.name = row.name
WITH p, row
UNWIND row.skills AS sk
MERGE (s:Skill {name: sk})
MERGE (p)-[:KNOWS]->(s)
```

**Dónde está en el código**

- `grafo_talento.py` — `cargar_personas_y_skills()` ejecuta esta carga (idempotente: se puede repetir)
- `01_grafo.py` — orquesta todo el módulo 1 (`construir()`), y es lo que corre `./run.sh 01`

### 1.5 · Explorar el grafo en el visualizador

Veamos qué hay. Primero las personas, cada una con su nombre y su email. Después las skills.

Y ahora lo más interesante: los caminos de persona a skill. Acá vemos la relación «conoce» uniendo a cada persona con las skills que sabe.

Hacé clic en cualquier nodo y mirá sus propiedades.

**Consultas**

**Personas** — *Grafo*

```cypher
MATCH (n:Person) RETURN n LIMIT 25
```

**Skills** — *Grafo*

```cypher
MATCH (n:Skill) RETURN n LIMIT 25
```

**Caminos persona → skill** — *Grafo*

```cypher
MATCH p=()-[:KNOWS]->() RETURN p LIMIT 25
```

**Qué deberías ver:** Primero nodos sueltos; en la tercera consulta, personas unidas a sus skills.

**Dónde está en el código:** es solo exploración en el visualizador; no hay código propio asociado.

**Ojo:** Si en la primera consulta el visualizador dibuja líneas entre las 25 personas, es porque muestra las relaciones que existan entre los nodos devueltos (opción «Connect result nodes»).

**Preguntas frecuentes**

- **¿«Conoce» es un tipo de relación propio de Neo4j?** No, lo inventamos nosotros. Podría llamarse «tiene». Y hoy importa más que antes: ahora que los modelos de lenguaje escriben consultas, las palabras que elegimos funcionan como una anotación para el modelo.

### 1.6 · Preguntas simples en Cypher

Un grafo de conocimiento es un conjunto de patrones para organizar y acceder a datos relacionados entre sí. Tiene tres piezas: los nodos, que son los sustantivos —personas, lugares, cosas—; las relaciones, que suelen ser verbos —conoce, vive con, maneja—; y las propiedades, que son atributos: un texto, un número, una lista o hasta un vector.

Para consultarlo usamos Cypher, que se lee casi literal y parece un dibujo en ASCII: `MATCH (persona)-[:KNOWS]->(skill)` conecta un nodo persona con un nodo skill a través de la relación. Las etiquetas, como `Person`, son parecidas al tipo de tabla en SQL.

No es un curso de Cypher: recorré las consultas para entender qué hacen.

Tres preguntas: quiénes son las personas, qué sabe cada una y cuáles son las skills más frecuentes. En la última contamos las personas distintas que conocen cada skill.

**Consultas**

**¿Qué personas hay?** — *Tabla*

```cypher
MATCH (p:Person)
RETURN p.name AS person_name
LIMIT 10
```

**¿Qué skills sabe cada persona?** — *Tabla*

```cypher
MATCH (p:Person)-[:KNOWS]->(s:Skill)
RETURN p.email AS email, p.name AS person_name, collect(s.name) AS skills
LIMIT 10
```

**¿Cuáles son las skills más frecuentes?** — *Tabla*

```cypher
MATCH (p:Person)-[:KNOWS]->(s:Skill)
RETURN s.name, COUNT(DISTINCT p) AS knownByCount
ORDER BY knownByCount DESC
LIMIT 10
```

**Qué deberías ver:** La skill más frecuente es System Design, con catorce personas; después vienen Agile, Angular y Security, con trece cada una.

**Dónde está en el código:** es solo exploración en el visualizador; no hay código propio asociado.

### 1.7 · Pregunta multihop: ¿quién sabe lo mismo que Lucy?

Ahora una pregunta de varios saltos: ¿quién sabe lo mismo que Lucy?

Partimos de Lucy, vamos a sus skills y volvemos hacia las otras personas que también las saben. Ese es el primer grafo.

Ahora lo alargamos un paso más: de esas personas, a todas las skills que ellas conocen. El grafo crece bastante.

Lo importante es esto: como la lógica de «parecido» está dibujada en el grafo, podemos controlarla con mucha más precisión, un paso a la vez, y cambiarla cuando queramos. Es información simbólica, no solamente un vector.

Y en esa red podemos encontrar las skills más centrales del grupo: las que más comparten las personas que se parecen a Lucy.

**Consultas**

**Personas que comparten alguna skill con Lucy (grafo)** — *Grafo*

```cypher
MATCH p=(p1:Person {name: "Lucy Clark"})-[:KNOWS]->(s1:Skill)<-[:KNOWS]-(p2:Person)
RETURN DISTINCT p
```

**Lo mismo, solo los nombres (tabla)** — *Tabla*

```cypher
MATCH p=(p1:Person {name: "Lucy Clark"})-[:KNOWS]->(s1:Skill)<-[:KNOWS]-(p2:Person)
RETURN DISTINCT p2.name AS person
```

**Un paso más: las skills de esas personas (grafo)** — *Grafo*

```cypher
MATCH p=(p1:Person {name: "Lucy Clark"})-[:KNOWS]->(s1:Skill)<-[:KNOWS]-(p2:Person)-[:KNOWS]-(s2:Skill)
RETURN DISTINCT p
```

**Lo mismo, solo las skills (tabla)** — *Tabla*

```cypher
MATCH p=(p1:Person {name: "Lucy Clark"})-[:KNOWS]->(s1:Skill)<-[:KNOWS]-(p2:Person)-[:KNOWS]-(s2:Skill)
RETURN DISTINCT s2.name AS skill
```

**Qué deberías ver:** Cada consulta tiene dos versiones: una devuelve el grafo, para verlo; la otra devuelve solo nombres, en una tabla.

**Dónde está en el código:** es solo exploración en el visualizador; no hay código propio asociado.

**Ojo:** Para ver un grafo la consulta tiene que devolver nodos o el camino `p`. Si devuelve solo nombres, el visualizador muestra una tabla y no puede reconstruir el camino.

**Preguntas frecuentes**

- **¿Para qué sirve el DISTINCT?** En consultas de varios saltos puede llegar el mismo camino dos veces, y DISTINCT filtra los duplicados. En la primera consulta no es imprescindible, pero sí cuando devolvemos solo un nombre, porque la misma persona puede aparecer varias veces.
- **¿Por qué a veces veo una tabla y a veces un grafo?** Si la consulta devuelve nodos o caminos, el visualizador dibuja un grafo. Si devuelve solo valores, como nombres, muestra una tabla.

### 1.8 · Similitud de personas por skills compartidas (y guardarla)

Una manera de medir qué tan parecidas son dos personas es contar cuántas skills exactas comparten.

Primero lo hacemos para Thomas Brown: con quién comparte más. Después, para todos los pares de personas.

Si vamos a necesitar esto seguido, conviene guardar el resultado como una relación, «mismo conjunto de skills» (`SIMILAR_SKILLSET`), con el solapamiento como propiedad. Así no repetimos el recorrido cada vez.

Eso ya está guardado: son mil trescientas diecinueve relaciones, con solapamientos de uno a tres. Hacé clic en una relación para ver cuántas skills comparten.

Y hay una segunda razón para guardarla: la vamos a usar enseguida para detectar comunidades.

**Consultas**

**Skills compartidas con Thomas Brown (tabla)** — *Tabla*

```cypher
MATCH path_1=(p1:Person{name: "Thomas Brown"})-[:KNOWS]->(s1:Skill)
MATCH path_2=(s1)<-[:KNOWS]-(p2:Person)
WITH p1.name AS person_1, p2.name AS person_2, COLLECT(DISTINCT s1.name) AS skill_list, COUNT(DISTINCT(s1)) AS skill_count
WHERE skill_count > 1 AND person_1 <> person_2
RETURN * ORDER BY skill_count DESC
```

**Los pares con más skills en común (tabla)** — *Tabla*

```cypher
MATCH path_1=(p1:Person)-[:KNOWS]->(s1:Skill)<-[:KNOWS]-(p2:Person)
WHERE p1.name < p2.name
WITH p1.name AS person_1, p2.name AS person_2, COLLECT(DISTINCT s1.name) AS skill_list, COUNT(DISTINCT(s1)) AS skill_count
WHERE skill_count >= 1
RETURN * ORDER BY skill_count DESC
LIMIT 10
```

**Guardar el resultado como relación (ya hecho, no ejecutar)** — *Ya hecho: solo para leer, no la ejecutes*

```cypher
MATCH (p1:Person)-[:KNOWS]->(s:Skill)<-[:KNOWS]-(p2:Person)
WHERE p1.email < p2.email
WITH p1, p2, count(DISTINCT s) AS overlap
MERGE (p1)-[r:SIMILAR_SKILLSET]->(p2)
SET r.overlap = overlap
```

**La red SIMILAR_SKILLSET (grafo)** — *Grafo*

```cypher
MATCH p=()-[:SIMILAR_SKILLSET]->() RETURN p LIMIT 50
```

**Solo las parejas con 2 o más skills en común (grafo)** — *Grafo*

```cypher
MATCH p=()-[s:SIMILAR_SKILLSET]->() WHERE s.overlap >= 2 RETURN p LIMIT 50
```

**Solo las parejas con 3 o más (grafo)** — *Grafo*

```cypher
MATCH p=()-[s:SIMILAR_SKILLSET]->() WHERE s.overlap >= 3 RETURN p LIMIT 50
```

**Qué deberías ver:** Una red de personas unidas por skills compartidas. Con tres o más en común quedan muy pocas parejas.

**Dónde está en el código**

- `grafo_talento.py` — `recalcular_similitudes()` calcula las skills compartidas por cada par de personas y las guarda como `SIMILAR_SKILLSET {overlap}` (se borran y recalculan enteras)

**Preguntas frecuentes**

- **Pero si lo guardamos queda estático. ¿Hay que recalcularlo cuando cambian los datos?** Sí, hay que volver a correr el cálculo. Depende de cuánto cambien los datos. No hay nada malo en repetir el recorrido de varios saltos cada vez: la base está hecha para eso. Si el grafo cambia todo el tiempo, quizá ni conviene guardar la relación.

### 1.9 · Comunidades con el algoritmo de Leiden

Neo4j trae algoritmos de grafos para enriquecer los datos: centralidad, caminos, detección de comunidades, embeddings de grafos. Acá usamos uno, para encontrar comunidades de personas.

El algoritmo se llama Leiden. Divide el grafo en una jerarquía, de pocas comunidades grandes a comunidades más chicas, y trata de maximizar la modularidad: una métrica que busca grupos donde las conexiones dentro del grupo son muchas y las conexiones entre grupos son pocas.

Lo corremos sobre la red de «mismo conjunto de skills» y guardamos en cada persona el número de su comunidad. Esto ya está calculado, así que miramos el resultado.

Son nueve comunidades. Y una advertencia honesta: los datos son aleatorios, así que no esperes un grupo de frontend y otro de datos. Acá cada comunidad se define por una skill que casi todos sus miembros comparten. Con datos reales, el mismo análisis mostraría perfiles.

La cuarta consulta es la tabla que, en un mapa de calor, mostraría cuántas veces aparece cada skill en cada comunidad. Sirve para entender de qué se trata cada grupo y hasta para ponerle nombre.

**Consultas**

**Cómo se calcula (GDS desde Python; ya hecho, no ejecutar)** — *Solo para leer*

```python
gds = GraphDataScience(NEO4J_URI, auth=NEO4J_AUTH)
G, res = gds.graph.project("person_similarity_projection", ["Person"],
    {"SIMILAR_SKILLSET": {"orientation": "UNDIRECTED", "properties": "overlap"}})
gds.leiden.write(G, writeProperty="leiden_community", relationshipWeightProperty="overlap",
    maxLevels=100, gamma=1.5, theta=0.001, concurrency=1, randomSeed=42)
G.drop()
```

**¿Cuántas personas hay en cada comunidad?** — *Tabla*

```cypher
MATCH (p:Person)
RETURN p.leiden_community AS Community, COUNT(*) AS MemberCount
ORDER BY MemberCount DESC
```

**Parejas con mucho solapamiento: ¿quedaron en la misma comunidad?** — *Tabla*

```cypher
MATCH (p1:Person)-[s:SIMILAR_SKILLSET]->(p2:Person)
WHERE s.overlap > 2
RETURN s.overlap AS Overlap, p1.name AS Person1, p1.leiden_community AS Community1, p2.name AS Person2, p2.leiden_community AS Community2
```

**Skills que más se repiten dentro de cada comunidad (la tabla detrás de un mapa de calor)** — *Tabla*

```cypher
MATCH (p:Person)-[:KNOWS]->(s)
WHERE (p.leiden_community) IS NOT NULL
WITH p.leiden_community AS leiden_community, s.name AS skill, count(*) AS cnt
WHERE cnt > 5
RETURN * ORDER BY leiden_community, cnt DESC
```

**Una comunidad: las similitudes entre sus miembros (grafo)** — *Grafo*

```cypher
MATCH p=(a:Person)-[:SIMILAR_SKILLSET]-(b:Person)
WHERE a.leiden_community = 0 AND b.leiden_community = 0 AND a.name < b.name
RETURN p
```

**Una comunidad: las skills de sus miembros (grafo)** — *Grafo*

```cypher
MATCH p=(a:Person {leiden_community: 0})-[:KNOWS]->(:Skill)
RETURN p
```

**Qué deberías ver:** Nueve comunidades de entre siete y dieciséis personas. En los dos grafos finales ves una sola comunidad.

**Dónde está en el código**

- `grafo_talento.py` — `comunidades_leiden()` corre Leiden y renumera las comunidades; `_leiden_gds()` hace la proyección y `gds.leiden.write`
- `docker-compose.yml` — `NEO4J_PLUGINS` activa los plugins de GDS y APOC dentro del contenedor

**Ojo:** El visualizador colorea por etiqueta, no por el valor de una propiedad: las comunidades se miran de a una, cambiando el número en la consulta. Si hacés clic en la etiqueta `Person`, podés poner el texto de los nodos en `leiden_community` para ver el número. Cada comunidad se define por una skill: System Design 14 de 16, Agile 13 de 15, Security 13 de 13, Testing 8 de 11, Scrum 11 de 11, Blockchain 8 de 9, Project Management 8 de 9, API Design 7 de 9, HTML5 7 de 7. Los números de comunidad (0 a 8) son los mismos en cada reconstrucción: Leiden corre con semilla fija y después se renumera de la más grande a la más chica.

**Preguntas frecuentes**

- **¿Cuándo conviene calcular comunidades?** Depende de las preguntas que vayan a hacer los usuarios. Si seguido van a querer saber qué comunidades de skills hay en la empresa, la analítica de grafos es muy útil: sirve para segmentar empleados, comparar desempeño entre grupos, y también para segmentar clientes o hacer recomendaciones. Si solo quieren encontrar personas con skills parecidas, quizá no hace falta: es un ejercicio de emparejamiento. Se usa cuando se quiere hacer un análisis de agrupamiento, guardarlo y tener visibilidad de que hay un método detrás, en lugar de un modelo inventando cómo se agrupa.

### 1.10 · Embeddings y búsqueda vectorial de skills

Hay otra manera de relacionar skills: por su significado. Para eso usamos embeddings.

Un embedding es una forma de comprimir datos: convierte un texto en un vector de números, de modo que lo que significa algo parecido queda cerca. Así encontramos cosas parecidas semánticamente, no solo por tener las mismas palabras.

Una pregunta para pensar: ¿qué conviene embeber, el nombre de la skill o su descripción? Con nombres muy cortos, como R o AWS, hay muy poca información. La descripción da un vector más informativo. Por eso guardamos una descripción de cada skill y embebemos el nombre junto con la descripción.

Los vectores los calcula el modelo `gemini-embedding-001` (768 dimensiones) a través de la API de Gemini; la primera corrida de `./run.sh 01` los calcula y los guarda en una caché (`.cache/`), así que repetirla no vuelve a llamar a la API.

Con esos vectores creamos un índice vectorial, que es uno de los tipos de índice de Neo4j, junto con los de rango, texto y texto completo. Ahora podemos buscar, dentro del grafo, las skills más cercanas a otra.

Probemos con Python. Salen Ruby, Django, Flask, Java… Algunas son mejores que otras, y eso es parte de la historia: la búsqueda semántica no es perfecta.

**Consultas**

**Ver los índices (entre ellos el vectorial de skills)** — *Tabla*

```cypher
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state
RETURN name, type, labelsOrTypes, properties, state
```

**Cómo se crea el índice vectorial (ya hecho, no ejecutar)** — *Ya hecho: solo para leer, no la ejecutes*

```cypher
CREATE VECTOR INDEX `skill_emb` IF NOT EXISTS
FOR (s:Skill) ON (s.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine' } }
```

**Skills más cercanas a Python (búsqueda vectorial)** — *Tabla*

```cypher
MATCH (s:Skill {name: 'Python'})
CALL db.index.vector.queryNodes('skill_emb', 10, s.embedding) YIELD node, score
WITH node AS skill, score, s ORDER BY score DESC
WHERE skill.name <> s.name AND score > 0.93
RETURN skill.name AS skill, score
```

**Qué deberías ver:** Una tabla con las skills más cercanas a Python y su puntaje (todas entre 0,93 y 0,95).

**Dónde está en el código**

- `comun.py` — `embed()` calcula los embeddings con la API de Gemini y los guarda en caché; `TAREA_EMBEDDING`, `DIM`, `INDICE_SKILLS` y `UMBRAL_*` fijan el tipo de embedding, el índice y los umbrales
- `grafo_talento.py` — `cargar_embeddings_de_skills()` los guarda en cada skill; `esquema()` crea el índice vectorial; `vecinas()` busca las skills más cercanas
- `01_grafo.py` — `./run.sh calibrar` imprime los scores de similitud para elegir los umbrales

**Ojo:** El puntaje de Neo4j se calcula como (1 + coseno) / 2, y con este modelo los puntajes entre skills quedan concentrados entre 0,86 y 0,96. Por eso los umbrales son tan altos: 0,94 para decidir si dos skills se guardan como parecidas y 0,895 para decidir si un texto libre coincide con una skill. Se eligieron a ojo con `./run.sh calibrar`, sin una métrica detrás: si cambiás el modelo de embeddings, repetí la calibración. Buscar un texto libre, por ejemplo «API coding», requiere calcular su embedding fuera del visualizador; lo hace la herramienta del agente. Con estos embeddings devuelve primero API Design (0,92). Los puntajes de esta guía vienen de la API de Gemini: pueden variar en la tercera cifra decimal, y una relación que está justo en el umbral (0,94) podría aparecer o no.

**Preguntas frecuentes**

- **¿El índice vectorial tiene que estar en Neo4j?** No necesariamente. Es una cuestión de costo por rendimiento. Tenerlo todo en un solo lugar evita sincronizar datos y, en teoría, baja la latencia porque se consulta una sola base. Pero si ya tenés los vectores en Postgres o en una base vectorial especializada, no hace falta migrarlos.

### 1.11 · Guardar la similitud semántica como relaciones

Esa similitud también se puede guardar en el grafo. Para cada skill buscamos sus vecinas más cercanas y, si son lo bastante parecidas, guardamos una relación «semánticamente parecida» (`SIMILAR_SEMANTIC`) con su puntaje.

Guardarla tiene ventajas: se puede visualizar, se puede usar para agrupar y se puede usar en las consultas.

Hacé zoom y fijate qué se forma: la nube —Azure, AWS, Cloud Architecture—, el grupo de datos —Data Analysis, Data Visualization, Tableau, Power BI—, CI/CD con Jenkins y DevOps, Docker con Kubernetes. No subestimes el poder de visualizar similitudes.

También aparecen relaciones discutibles, como Python con Ruby o Express.js con Flask. Y otra ventaja: si no creemos que Flask deba estar conectado con Express.js, podemos borrar esa relación. Cada vez que usemos las relaciones de similitud, tenemos control sobre ellas.

**Consultas**

**Cómo se crean (APOC, ya hecho, no ejecutar)** — *Ya hecho: solo para leer, no la ejecutes*

```cypher
CALL apoc.periodic.iterate(
  "MATCH (skill1:Skill) RETURN skill1",
  "WITH skill1
   CALL db.index.vector.queryNodes('skill_emb', 10, skill1.embedding) YIELD node, score
   WITH skill1, node AS skill2, score ORDER BY score DESC
   WHERE skill1.name < skill2.name AND score > 0.94
   MERGE (skill1)-[s:SIMILAR_SEMANTIC]->(skill2)
   SET s.score = score",
  {batchSize: 1000})
```

**Ver las skills semánticamente parecidas (grafo)** — *Grafo*

```cypher
MATCH p=()-[:SIMILAR_SEMANTIC]->() RETURN p
```

**Lo mismo como tabla ordenada por score** — *Tabla*

```cypher
MATCH (s1:Skill)-[r:SIMILAR_SEMANTIC]-(s2:Skill)
WHERE s1.name < s2.name
RETURN s1.name AS skill1, r.score AS score, s2.name AS skill2
ORDER BY score DESC
```

**Las vecinas semánticas de Express.js (para comparar antes y después)** — *Tabla*

```cypher
MATCH (:Skill {name: 'Express.js'})-[r:SIMILAR_SEMANTIC]-(t:Skill)
RETURN t.name AS skill, r.score AS score
ORDER BY score DESC
```

**Opcional: borrar la relación Express.js–Flask (modifica la base; después volvé a ejecutar la consulta anterior)** — *Opcional: modifica la base (se deshace con ./run.sh 01)*

```cypher
MATCH (:Skill {name: 'Express.js'})-[r:SIMILAR_SEMANTIC]-(:Skill {name: 'Flask'})
DELETE r
```

**Qué deberías ver:** Alrededor de veinticinco relaciones entre skills, con su puntaje.

**Dónde está en el código**

- `grafo_talento.py` — `recalcular_similitudes()` ejecuta `apoc.periodic.iterate`: por cada skill busca sus 10 vecinas con el índice vectorial y guarda las que superan el umbral como `SIMILAR_SEMANTIC {score}`
- `comun.py` — `UMBRAL_SKILL_SKILL = 0.94`

**Ojo:** La consulta «Cómo se crean» ya se ejecutó: no la corras. El bloque opcional borra una relación y modifica la base; se deshace con `./run.sh 01` (que recalcula todo).

**Preguntas frecuentes**

- **¿Esto sirve solo para visualizar?** No. Lo más útil es armar un puntaje a medida que balancee la similitud semántica contra las coincidencias exactas de skills, con el peso que queramos. Es lo que vemos en el próximo paso.

### 1.12 · Personas parecidas: skills exactas + similitud semántica

Ahora juntamos las dos evidencias: las skills exactas que dos personas comparten y las skills parecidas por significado. Sumamos los dos puntajes y obtenemos un número decimal. Así no dependemos solo de coincidencias exactas, sino también de skills cercanas, y podemos ponderar cada parte por separado.

La consulta parece intimidante, pero hace una sola cosa: balancear la similitud semántica con el solapamiento exacto.

Y una ventaja propia de las bases de grafos: las consultas de longitud variable. Con esa estrella en la relación decimos «andá por skills parecidas de cero a dos saltos».

Mirá el ejemplo de Claire Moore y Ryan Young. No comparten ninguna skill exacta, así que la relación de skills compartidas no los une. Pero hay otros caminos: Claire sabe AWS y Ryan sabe Cloud Architecture, que son parecidas (un salto). Y Claire sabe Power BI y Ryan sabe Data Visualization: se conectan pasando por Tableau (dos saltos).

Así controlamos hasta dónde dejamos llegar a la similitud. En la tabla de puntajes fijate en David Rodriguez: tampoco comparte ninguna skill exacta con Claire, pero queda entre los primeros por tres pares de skills parecidas.

**Consultas**

**El vecindario de Claire Moore (grafo; son muchos caminos)** — *Grafo*

```cypher
MATCH (p1:Person {name: "Claire Moore"})
CALL (p1) {
  MATCH p=(p1)-[:KNOWS]->(s1:Skill)-[r:SIMILAR_SEMANTIC]-(s2:Skill)<-[:KNOWS]-(p2:Person)
  RETURN p
  UNION
  MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person), p=(p2)-[:KNOWS]->(:Skill)
  RETURN p
}
RETURN p
```

**Las personas más parecidas a Claire Moore, con puntaje (tabla)** — *Tabla*

```cypher
MATCH (p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)
WITH p1, COLLECT(s.name) AS skills_1
CALL (p1) {
  MATCH (p1)-[:KNOWS]->(s1:Skill)-[r:SIMILAR_SEMANTIC]-(s2:Skill)<-[:KNOWS]-(p2:Person)
  WHERE p2 <> p1
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.score) AS score
  UNION
  MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person)
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.overlap) AS score
}
WITH person_1.name AS person_1, skills_1, person_2, SUM(score) AS score
WHERE score >= 1
MATCH (person_2)-[:KNOWS]->(s:Skill)
RETURN person_1, skills_1, person_2.name AS person_2, COLLECT(s.name) AS skills_2, score
ORDER BY score DESC
```

**Claire Moore y Ryan Young: ¿se pueden unir con un solo salto semántico? (grafo)** — *Grafo*

```cypher
MATCH p=(p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)-[:SIMILAR_SEMANTIC]-(:Skill)<-[:KNOWS]-(p2:Person {name: "Ryan Young"})
RETURN p
UNION
MATCH p=(p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)<-[:KNOWS]-(p2:Person {name: "Ryan Young"})
RETURN p
```

**Lo mismo con hasta 2 saltos semánticos: `*0..2` (grafo)** — *Grafo*

```cypher
MATCH p=(p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)-[:SIMILAR_SEMANTIC*0..2]-(:Skill)<-[:KNOWS]-(p2:Person {name: "Ryan Young"})
RETURN p
UNION
MATCH p=(p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)<-[:KNOWS]-(p2:Person {name: "Ryan Young"})
RETURN p
```

**Todas las parejas con puntaje mayor a 3 (tabla)** — *Tabla*

```cypher
MATCH (p1:Person)-[:KNOWS]->(s:Skill)
WITH p1, COLLECT(s.name) AS skills_1
CALL (p1) {
  MATCH (p1)-[:KNOWS]->(s1:Skill)-[r:SIMILAR_SEMANTIC]-(s2:Skill)<-[:KNOWS]-(p2:Person)
  WHERE p2 <> p1
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.score) AS score
  UNION
  MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person)
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.overlap) AS score
}
WITH person_1.name AS person_1, skills_1, person_2, SUM(score) AS score
WHERE score > 3
MATCH (person_2)-[:KNOWS]->(s:Skill)
RETURN person_1, skills_1, person_2.name AS person_2, COLLECT(s.name) AS skills_2, score
ORDER BY score DESC
```

**Qué deberías ver:** En el grafo con la estrella vemos caminos más largos, que pasan por skills intermedias.

**Dónde está en el código**

- `herramientas.py` — `_SIMILARES` es la consulta de `personas_similares()`: la misma idea con `UNION ALL` y un `LIMIT`

**Ojo:** El primer grafo, el vecindario de Claire Moore, es grande (más de cien caminos): hacé zoom.

**Preguntas frecuentes**

- **¿Cuándo uso el vector, cuándo el recorrido del grafo, cuándo los dos?** Se pueden usar los dos: los pasos se pueden componer. Por ejemplo, primero traer skills parecidas y después buscar personas. Depende de cómo separes las funciones para el agente. Si tenés una métrica de similitud muy específica, puede convenir acoplar la lógica en una sola consulta, como esta.
- **¿Cómo pasa el agente de una pregunta en lenguaje natural a las entidades correctas?** Lo vemos en el próximo módulo: cada herramienta define su punto de entrada.

## Módulo 2 — GraphRAG y agentes

### 2.1 · Qué preguntas queremos que responda el asistente

Ahora armamos un asistente sobre este grafo. Queremos que responda cuatro tipos de pregunta, y cada una es un patrón de recorrido que ya conocemos.

Uno: las skills de una persona. Dos: skills parecidas a otras. Tres: personas parecidas a una persona. Y cuatro: personas que tienen ciertas skills.

La idea de fondo: si sabemos qué preguntas queremos responder, aun un grafo muy simple nos permite poner la lógica del dominio en el modelo de datos. Si además le damos al agente el esquema y herramientas con recorridos definidos, ganamos control sobre cómo se recuperan los datos y podemos explicar mejor esa lógica.

Esto es cada vez más importante en un mundo con agentes: ya no es una búsqueda vectorial de un solo paso. Las preguntas se descomponen, y el grafo ofrece una lógica de recuperación que lo complementa.

**Dónde está en el código**

- `herramientas.py` — `HERRAMIENTAS` es la lista de las cuatro herramientas que usa el agente
- `agente.py` — `construir_agente()` arma el agente de ADK 2 con esas herramientas

### 2.2 · Herramienta 1: las skills de una persona

La primera herramienta es la más simple: dado el nombre de una persona, traer las skills a las que está conectada.

Es solamente persona conoce skill.

**Consultas**

**Skills de Lucy Turner (tabla)** — *Tabla*

```cypher
MATCH (p:Person {name: "Lucy Turner"})-[:KNOWS]->(s:Skill)
RETURN p.name AS name, COLLECT(s.name) AS skills
```

**Lo mismo, como grafo** — *Grafo*

```cypher
MATCH p=(:Person {name: "Lucy Turner"})-[:KNOWS]->(:Skill)
RETURN p
```

**Qué deberías ver:** Lucy Turner y sus cinco skills.

**Dónde está en el código**

- `herramientas.py` — `habilidades_de_persona()`; usa `_persona()` (busca sin distinguir mayúsculas) y `_no_encontrada()` (sugerencias si no existe)

**Ojo:** La herramienta busca sin distinguir mayúsculas y, si la persona no existe, devuelve sugerencias en lugar de fallar.

### 2.3 · Herramienta 2: skills parecidas (búsqueda vectorial + 1 salto)

La segunda herramienta: skills parecidas. El problema es que lo que escribe el usuario quizá no coincide palabra por palabra con las skills de la base.

Entonces usamos búsqueda vectorial para encontrar las skills más cercanas a lo que escribió, con un umbral de puntaje para traer solo lo que corresponde. Y después damos un salto por la relación semántica para sumar skills relacionadas.

Acá lo simulamos partiendo de skills que ya existen: CI/CD, Kubernetes y Security. Fijate que Security no trae vecinas: ninguna otra skill está lo bastante cerca.

**Consultas**

**Skills cercanas + un salto semántico (CI/CD, Kubernetes, Security)** — *Tabla*

```cypher
UNWIND ['CI/CD', 'Kubernetes', 'Security'] AS nombre
MATCH (q:Skill {name: nombre})
CALL db.index.vector.queryNodes('skill_emb', 3, q.embedding) YIELD node, score
WHERE score > 0.93
OPTIONAL MATCH (node)-[:SIMILAR_SEMANTIC]-(s:Skill)
WITH COLLECT(node) AS nodes, COLLECT(DISTINCT s) AS skills
WITH nodes + skills AS all_skills
UNWIND all_skills AS skill
RETURN DISTINCT skill.name AS skill_name
```

**Qué deberías ver:** Una lista de skills: las más cercanas a las tres de partida y sus vecinas semánticas (CI/CD, Jenkins, DevOps, Kubernetes, Docker y Security).

**Dónde está en el código**

- `herramientas.py` — `habilidades_similares()`; `_skills_cercanas()` embebe el texto con Gemini y busca en el índice; `_relacionadas()` da el salto por `SIMILAR_SEMANTIC`
- `comun.py` — `embed()` y `UMBRAL_CONSULTA = 0.895`

**Ojo:** En el visualizador no se puede calcular el embedding de un texto libre; la herramienta real lo hace con la API de Gemini.

### 2.4 · Herramienta 3: personas parecidas, tres estrategias

La tercera herramienta: personas parecidas a una persona. Hay varias maneras de hacerlo. Las vemos de la más simple a la más rica, con Claire Moore.

Una: por comunidad. Buscamos a todas las personas de su misma comunidad.

Dos: por solapamiento exacto, usando la relación de skills compartidas que guardamos antes.

Tres: la suma ponderada. Combina el solapamiento exacto con la similitud semántica. Da un puntaje decimal y una respuesta distinta, que no depende solo de conexiones duras sino también de skills cercanas, y cada parte se puede ponderar por separado. Fijate en David Rodriguez: sin ninguna skill exacta en común con Claire, sube al segundo lugar por tres pares de skills relacionadas.

La herramienta del agente usa esta tercera estrategia. Fijate que en cada resultado aparece si la persona es o no de la misma comunidad: es un dato informativo, y en el paso siguiente vemos por qué a veces una persona muy parecida no está en el mismo grupo.

**Consultas**

**Estrategia 1 — misma comunidad** — *Tabla*

```cypher
MATCH (p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)
WITH p1, COLLECT(s.name) AS s1
MATCH (p2:Person {leiden_community: p1.leiden_community})-[:KNOWS]->(s2:Skill)
RETURN p1.name AS person_1, s1 AS skills_1, p1.leiden_community AS community, p2.name AS person_2, COLLECT(s2.name) AS skills_2
```

**Estrategia 2 — skills exactas en común** — *Tabla*

```cypher
MATCH (p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)
WITH p1, COLLECT(s.name) AS s1
MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person)-[:KNOWS]->(s2:Skill)
WHERE r.overlap > 1
RETURN p1.name AS person_1, s1 AS skills_1, r.overlap AS score, p2.name AS person_2, COLLECT(DISTINCT s2.name) AS skills_2
ORDER BY score DESC
```

**Estrategia 3 — exactas + semánticas (puntaje decimal)** — *Tabla*

```cypher
MATCH (p1:Person {name: "Claire Moore"})-[:KNOWS]->(s:Skill)
WITH p1, COLLECT(s.name) AS skills_1
CALL (p1) {
  MATCH (p1)-[:KNOWS]->(s1:Skill)-[r:SIMILAR_SEMANTIC]-(s2:Skill)<-[:KNOWS]-(p2:Person)
  WHERE p2 <> p1
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.score) AS score
  UNION
  MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person)
  RETURN p1 AS person_1, p2 AS person_2, SUM(r.overlap) AS score
}
WITH person_1.name AS person_1, skills_1, person_2, SUM(score) AS score
WHERE score >= 1
MATCH (person_2)-[:KNOWS]->(s:Skill)
RETURN person_1, skills_1, person_2.name AS person_2, COLLECT(s.name) AS skills_2, score
ORDER BY score DESC LIMIT 5
```

**Qué deberías ver:** La primera trae a toda la comunidad; la segunda ordena por solapamiento exacto; la tercera mezcla ambas y puede cambiar el orden.

**Dónde está en el código**

- `herramientas.py` — `personas_similares()` y su consulta `_SIMILARES`: usa la estrategia 3 y devuelve por separado las skills exactas en común, los pares relacionados y `misma_comunidad` (lee la propiedad)

**Ojo:** La herramienta devuelve por separado las skills exactas en común, los pares de skills relacionadas y un indicador de si son de la misma comunidad (lee la propiedad, no busca por comunidad).

### 2.5 · Por qué dos personas parecidas pueden estar en comunidades distintas

Una pregunta que seguro va a aparecer: si el agente me dice que dos personas se parecen, ¿cómo puede ser que no sean de la misma comunidad? Veamos un caso real de este grafo: Amelia Hall y John Taylor.

Primero hay que entender que la herramienta y las comunidades no miran lo mismo. Las comunidades las calcula Leiden usando solamente las skills exactas que dos personas comparten, es decir, la relación «mismo conjunto de skills». Y reparte a cada persona en un solo grupo: el que mejor ordena toda la red. La herramienta de personas parecidas, en cambio, suma además las skills parecidas por significado, que Leiden nunca ve. Y la comunidad, en la respuesta, es solo un dato extra: no es el criterio con el que se busca.

Ahora el caso. Amelia está en la comunidad 1 y John en la 4. Comparten una sola skill exacta, CSS3, así que el vínculo entre ellos tiene peso uno, el mínimo.

Amelia tiene todos sus vínculos fuertes dentro de la comunidad 1: doce vecinos, con un peso total de doce. John tiene los suyos en la comunidad 4: diez vecinos, con un peso total de diez. Cada uno queda con su grupo, y una sola relación de peso uno no alcanza para juntarlos. La cuarta consulta lo explica: la comunidad 1 se define por Agile y la 4 por Scrum.

Entonces, ¿dónde aparece el parecido? En dos pares de skills relacionadas por significado: Agile con Scrum, y Azure con AWS. Eso es lo que la herramienta suma y Leiden ignora. Tanto es así que John Taylor es el primero de la lista de Amelia, con casi tres puntos, muy por encima de los demás (menos de dos), aunque no sea de su comunidad.

Dos advertencias para leer bien el resultado. Primera: con estos datos, las comunidades salen de una única skill compartida y los datos son aleatorios, así que dos personas que comparten una skill pueden quedar en grupos distintos. Segunda: «no es de la misma comunidad» no quiere decir «no se parece». Es un dato aparte.

**Consultas**

**Las dos personas: comunidad y skills** — *Tabla*

```cypher
MATCH (p:Person)
WHERE p.name IN ['Amelia Hall', 'John Taylor']
RETURN p.name AS persona, p.leiden_community AS comunidad, [(p)-[:KNOWS]->(s:Skill) | s.name] AS skills
```

**Lo que las une por skills exactas: una sola relación de peso 1** — *Tabla*

```cypher
MATCH (a:Person {name: 'Amelia Hall'})-[r:SIMILAR_SKILLSET]-(b:Person {name: 'John Taylor'})
RETURN a.name AS persona_1, b.name AS persona_2, r.overlap AS overlap
```

**Dónde tiene cada una sus vínculos, por comunidad** — *Tabla*

```cypher
MATCH (a:Person)-[r:SIMILAR_SKILLSET]-(b:Person)
WHERE a.name IN ['Amelia Hall', 'John Taylor']
RETURN a.name AS persona, b.leiden_community AS comunidad_del_vecino, count(*) AS vecinos, sum(r.overlap) AS peso_total
ORDER BY persona, peso_total DESC
```

**Qué skill define cada una de esas dos comunidades (la más repetida entre sus miembros)** — *Tabla*

```cypher
MATCH (p:Person)-[:KNOWS]->(s:Skill)
WHERE p.leiden_community IN [1, 4]
WITH p.leiden_community AS comunidad, s.name AS skill, count(DISTINCT p) AS miembros
ORDER BY comunidad, miembros DESC
WITH comunidad, collect([skill, miembros])[0] AS top
RETURN comunidad, top[0] AS skill_que_la_define, top[1] AS miembros_que_la_tienen
ORDER BY comunidad
```

**Dónde aparece el parecido: la skill exacta y los pares de skills relacionadas (grafo)** — *Grafo*

```cypher
MATCH p=(a:Person {name: 'Amelia Hall'})-[:KNOWS]->(:Skill)-[:SIMILAR_SEMANTIC*0..1]-(:Skill)<-[:KNOWS]-(b:Person {name: 'John Taylor'})
RETURN p
```

**Lo mismo, preguntándole al agente (herramienta esperada: personas_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Qué personas tienen skills parecidas a las de Amelia Hall?
```

**Qué deberías ver:** Las dos personas en comunidades distintas, con una sola skill exacta en común (CSS3) y dos pares de skills relacionadas (Agile ~ Scrum y Azure ~ AWS).

**Dónde está en el código**

- `herramientas.py` — `_SIMILARES` suma las skills exactas en común (`SIMILAR_SKILLSET`) y los pares de skills relacionadas (`SIMILAR_SEMANTIC`); `misma_comunidad` solo compara la propiedad `leiden_community` de las dos personas
- `grafo_talento.py` — `comunidades_leiden()` calcula las comunidades usando solamente `SIMILAR_SKILLSET` (las skills exactas compartidas)

**Ojo:** Esto no es un error del agente: `misma_comunidad` solo compara la propiedad `leiden_community` de las dos personas. El agente está instruido para mencionar la comunidad una sola vez, al final y como dato informativo; si igual la pone junto a cada persona o la presenta como un defecto, es una respuesta imperfecta del modelo: es un dato aparte. Las cifras salen de la partición actual (Leiden con semilla fija), que se reproduce en cada reconstrucción.

**Preguntas frecuentes**

- **¿Entonces las comunidades no sirven para buscar personas parecidas?** Sirven para otra cosa: agrupar toda la red de forma persistente y poder describir esos grupos. Para encontrar a alguien parecido a una persona concreta, el recorrido de la herramienta, que suma skills exactas y relacionadas, es más preciso.
- **¿Se puede hacer que las comunidades tengan en cuenta la similitud semántica?** En principio sí, sumando esas relaciones a la red sobre la que corre Leiden, pero no lo probamos. Hoy Leiden corre solo sobre las skills exactas compartidas.

### 2.6 · Herramienta 4: personas que tienen ciertas skills

La cuarta herramienta recomienda personas a partir de ciertas skills. Es el recorrido más largo, en cuatro pasos.

Uno: búsqueda vectorial para ubicar las skills en el grafo. Dos: ampliamos con las skills parecidas por significado. Tres: encontramos a las personas que las saben. Cuatro: contamos a cuántas de esas skills llega cada una y ordenamos.

Esta consulta ordena solo por el conteo. La herramienta del agente, además, pone primero a quien tiene la skill pedida y recién después a quien tiene una parecida.

**Consultas**

**Personas que cubren más skills (AWS y Security, ampliadas por significado)** — *Tabla*

```cypher
UNWIND ['AWS', 'Security'] AS nombre
MATCH (q:Skill {name: nombre})
CALL db.index.vector.queryNodes('skill_emb', 3, q.embedding) YIELD node, score
WHERE score > 0.93
OPTIONAL MATCH (node)-[:SIMILAR_SEMANTIC]-(s:Skill)
WITH COLLECT(node) AS nodes, COLLECT(DISTINCT s) AS skills
WITH nodes + skills AS all_skills
UNWIND all_skills AS skill
MATCH (p:Person)-[:KNOWS]->(skill)
RETURN p.name AS person, COUNT(DISTINCT(skill)) AS score, COLLECT(DISTINCT(skill.name)) AS similar_skills
ORDER BY score DESC LIMIT 10
```

**Qué deberías ver:** Una tabla de personas ordenadas por cuántas de esas skills conocen; John Garcia y Mia Nelson conocen las dos (AWS y Security).

**Dónde está en el código**

- `herramientas.py` — `personas_con_habilidades()`: arma, por cada skill pedida, el conjunto de skills cercanas y relacionadas, y rankea a las personas por cuántas de las pedidas cubren

### 2.7 · El agente: elige y encadena herramientas

Ahora sí, el agente. Recibe una pregunta, elige qué herramienta usar y la llama. Puede encadenar varias.

Lo importante: el modelo elige la herramienta y sus argumentos. Todo lo demás lo decide el código: el Cypher, que sea solo de lectura, los topes de cada herramienta y el límite de seis llamadas al modelo. El modelo nunca escribe Cypher.

Hacele preguntas, de menos a más. Primero, preguntas que necesitan una sola herramienta: qué skills tiene Lucy Turner, qué skills son parecidas a PowerBI y a Data Visualization, qué personas tienen skills parecidas a las de Daniel Hill, y quién tiene experiencia en Python y AWS. En cada una el agente elige la herramienta que corresponde.

Después, preguntas compuestas, donde tiene que decidir más. «Daniel Hill se va del proyecto: ¿quién podría reemplazarlo y qué skills tiene esa persona que él no tiene?». Y «quiero armar un equipo con Lucy Turner: ¿qué skills tiene y quién más en la empresa sabe Security?», que necesita dos herramientas encadenadas.

Y una pregunta que no necesita ninguna herramienta: un saludo. El agente tiene que darse cuenta de eso y responder directamente.

Por último, una conversación de varios turnos, en la misma sesión. Preguntá qué skills están relacionadas con Power BI. Después: ¿quiénes saben esas skills? Y por último: ¿y quién se parece a esas personas? Fijate que el agente recuerda cuáles eran «esas» y llama a la herramienta de personas parecidas una vez por cada persona.

En el panel de eventos de `adk web` ves exactamente qué herramienta llamó y con qué argumentos. Ahí está la explicabilidad.

**Consultas**

**Skills de una persona (herramientas esperadas: habilidades_de_persona)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Qué skills tiene Lucy Turner?
```

**Skills similares (herramientas esperadas: habilidades_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Qué skills son parecidas a PowerBI y a Data Visualization?
```

**Personas similares (herramientas esperadas: personas_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Qué personas tienen skills parecidas a las de Daniel Hill?
```

**Personas con skills (herramientas esperadas: personas_con_habilidades)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Quién tiene experiencia en Python y AWS?
```

**Pregunta compuesta (herramientas esperadas: personas_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
Daniel Hill se va del proyecto: ¿quién podría reemplazarlo y qué skills tiene esa persona que él no tiene?
```

**Cadena de herramientas (herramientas esperadas: habilidades_de_persona, personas_con_habilidades)** — *Pregunta para el agente: pegá solo este texto*

```text
Quiero armar un equipo con Lucy Turner: ¿qué skills tiene y quién más en la empresa sabe Security?
```

**Ninguna herramienta (herramientas esperadas: ninguna)** — *Pregunta para el agente: pegá solo este texto*

```text
Hola, ¿qué podés hacer por mí?
```

**Conversación de varios turnos, Turno 1 (herramienta esperada: habilidades_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Qué skills están relacionadas con Power BI?
```

**Conversación de varios turnos, Turno 2 (herramienta esperada: personas_con_habilidades)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Quiénes saben esas skills?
```

**Conversación de varios turnos, Turno 3 (herramienta esperada: personas_similares)** — *Pregunta para el agente: pegá solo este texto*

```text
¿Y quién se parece a esas personas?
```

**Dónde está en el código**

- `agente.py` — `INSTRUCCION` (qué hace y qué no), `construir_agente()` y `_tope_de_llamadas()` (límite de 6 llamadas al modelo)
- `agentes/reclutador/agent.py` — el punto de entrada para `adk web` (`./run.sh web`)
- `02_agente.py` — corre las 7 preguntas, verifica las herramientas usadas y audita los nombres (`./run.sh 02`)

**Ojo:** Para abrir el agente: `./run.sh web`, luego <http://localhost:8000> y elegir «reclutador». Las preguntas son las mismas que corre `./run.sh 02`. **Pegá solo el texto de la pregunta**, sin números ni flechas ni la anotación de la herramienta: lo que pegás le llega al agente tal cual. En la conversación de varios turnos, un mensaje por turno y en la misma sesión. En la pregunta compuesta del reemplazo, el agente a veces mira primero las skills de la persona; es válido. Si el agente dice «no es de la misma comunidad» como si fuera un defecto, ver el paso 2.5. Es un modelo y puede variar de una corrida a otra: si en el tercer turno de la conversación pide aclarar a quién te referís en lugar de buscar, repetí la pregunta. Si la capa gratuita de tu clave se queda sin cuota por minuto, `./run.sh 02` espera y reintenta; en `adk web` esperá un minuto y volvé a preguntar.

**Preguntas frecuentes**

- **¿Qué tan bien escriben Cypher los modelos?** Están mejorando, y depende de la complejidad del esquema. En agregaciones simples, o con mucha ingeniería de prompts sobre recorridos muy específicos, andan bien. Para recorridos complicados recomendamos tener herramientas expertas propias, como funciones de Python o un servidor MCP, que es lo que hicimos acá. También se puede restringir al modelo a unos pocos patrones y dejarlo completar una parte. Y Neo4j publicó modelos afinados, basados en Gemma, para generar Cypher.
- **¿Qué buenas prácticas hay para que un agente entienda el modelo de datos?** Que el modelo se lea como lenguaje natural: persona conoce skill, con nodos como sustantivos y relaciones como verbos. Los modelos simples funcionan mejor cuando el modelo genera las consultas. Hay que evitar cientos o miles de etiquetas: mejor usar propiedades. Para darle el esquema se pueden traer las etiquetas y los tipos de relación como un JSON y combinarlos con el prompt. Si el modelo de datos no cambia mucho, conviene anotar el esquema, explicando qué hace cada propiedad o etiqueta, y agregar los patrones de consulta, como persona conoce skill, porque el modelo los lee y recorre mejor.
- **¿Conviene un solo grafo o varios?** Con agentes ayuda un modelo de datos más chico, sobre todo si las consultas se generan dinámicamente. Cuando se necesitan recorridos de baja latencia entre dos datos, esos datos tienen que estar en el mismo grafo. Después es una decisión qué va como etiqueta y qué como propiedad.

## Cierre

Para cerrar, tres ideas.

Primera: si sabemos qué preguntas queremos responder, un grafo, aun muy simple, nos deja poner la lógica del dominio en los datos.

Segunda: las herramientas del agente son recorridos con nombre propio. Cada una define qué significa «parecido», y esa definición queda a la vista y se puede cambiar.

Tercera: el agente decide qué herramienta usar; el código decide cómo se recorre el grafo, cuánto y con qué límites. Por eso podemos explicar cómo llegó a cada respuesta.
