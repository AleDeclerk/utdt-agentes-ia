"""Construcción del grafo de talento (módulo 1 de la demo), idempotente.

Modelo:  (:Person {email, name, leiden_community})-[:KNOWS]->(:Skill {name, description, embedding})
Derivadas (se borran y se recalculan enteras, así correr dos veces da el mismo resultado):
  (:Person)-[:SIMILAR_SKILLSET {overlap}]->(:Person)   cantidad de skills en común (email menor -> email mayor)
  (:Skill)-[:SIMILAR_SEMANTIC {score}]->(:Skill)       vecinas por embedding (nombre menor -> nombre mayor)
  Person.leiden_community                              Leiden (GDS) sobre SIMILAR_SKILLSET
"""
import csv

from comun import DATOS, DIM, INDICE_SKILLS, NEO4J_AUTH, NEO4J_URI, UMBRAL_SKILL_SKILL, ddl, embed, escribir, leer

SEMILLA = 42      # misma partición en cada corrida
RESOLUCION = 1.5  # el parámetro `gamma` de Leiden: más alto, comunidades más chicas; se deja sin ajustar para que «salga lindo»
K_VECINAS = 10
PROYECCION = "person_similarity_projection"  # nombre de la proyección en memoria de GDS


def _abrir_dato(nombre: str):
    ruta = DATOS / nombre
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Descargá los datos con:  ./run.sh datos")
    return open(ruta, encoding="utf-8")


def esquema() -> None:
    # NODE KEY es solo de Enterprise: con UNIQUE alcanza (MERGE rápido, sin duplicados).
    ddl("CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE")
    ddl("CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE")
    ddl(f"CREATE VECTOR INDEX {INDICE_SKILLS} IF NOT EXISTS FOR (s:Skill) ON (s.embedding) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'cosine'}}}}")


def cargar_personas_y_skills() -> int:
    """CSV de personas -> Person, Skill y KNOWS (MERGE: idempotente)."""
    with _abrir_dato("expanded_skills.csv") as f:
        filas = [{"email": r["email"], "name": r["name"], "skills": [s.strip() for s in r["skills"].split(",")]}
                 for r in csv.DictReader(f)]
    escribir(
        "UNWIND $rows AS row "
        "MERGE (p:Person {email: row.email}) SET p.name = row.name "
        "WITH p, row UNWIND row.skills AS sk "
        "MERGE (s:Skill {name: sk}) MERGE (p)-[:KNOWS]->(s)", rows=filas)
    return len(filas)


def cargar_embeddings_de_skills() -> int:
    """Descripción de cada skill -> embedding (768 dim.) -> propiedad del nodo."""
    with _abrir_dato("skills_descripciones.csv") as f:
        desc = {r["skill"]: r["descripcion"] for r in csv.DictReader(f)}
    nombres = [r["n"] for r in leer("MATCH (s:Skill) RETURN s.name AS n ORDER BY n")]
    # Una skill sin descripción se embebe solo con su nombre.
    textos = [f"{n}. {desc[n]}" if n in desc else n for n in nombres]
    vectores = embed(textos)
    escribir(
        "UNWIND $rows AS row MATCH (s:Skill {name: row.n}) "
        "SET s.description = row.d WITH s, row CALL db.create.setNodeVectorProperty(s, 'embedding', row.v)",
        rows=[{"n": n, "d": desc.get(n), "v": v} for n, v in zip(nombres, vectores)])
    return len(nombres)


def vecinas(nombre: str, k: int = K_VECINAS) -> list[dict]:
    """Skills más cercanas a una skill del grafo (vía el índice vectorial; incluye la propia)."""
    r = leer("MATCH (s:Skill {name: $n}) RETURN s.embedding AS v", n=nombre)
    if not r:
        return []
    return leer(
        f"MATCH (d:Skill) SEARCH d IN (VECTOR INDEX {INDICE_SKILLS} FOR $v LIMIT $k) SCORE AS score "
        "RETURN d.name AS skill, score", v=r[0]["v"], k=k)


def recalcular_similitudes() -> dict:
    escribir("MATCH ()-[r:SIMILAR_SKILLSET|SIMILAR_SEMANTIC]->() DELETE r")
    escribir(
        "MATCH (p1:Person)-[:KNOWS]->(s:Skill)<-[:KNOWS]-(p2:Person) WHERE p1.email < p2.email "
        "WITH p1, p2, count(DISTINCT s) AS overlap "
        "MERGE (p1)-[r:SIMILAR_SKILLSET]->(p2) SET r.overlap = overlap")
    # SIMILAR_SEMANTIC: apoc.periodic.iterate + búsqueda vectorial de las K vecinas de cada skill.
    r = escribir(
        """CALL apoc.periodic.iterate(
             "MATCH (skill1:Skill) RETURN skill1",
             "WITH skill1 CALL db.index.vector.queryNodes($indice, $k, skill1.embedding) YIELD node, score
              WITH skill1, node AS skill2, score ORDER BY score DESC
              WHERE skill1.name < skill2.name AND score > $umbral
              MERGE (skill1)-[s:SIMILAR_SEMANTIC]->(skill2) SET s.score = score",
             {batchSize: 1000, params: {indice: $indice, k: $k, umbral: $umbral}})
           YIELD total, failedOperations, errorMessages
           RETURN total, failedOperations, errorMessages""",
        indice=INDICE_SKILLS, k=K_VECINAS, umbral=UMBRAL_SKILL_SKILL)[0]
    if r["failedOperations"]:
        raise RuntimeError(f"apoc.periodic.iterate falló: {r['errorMessages']}")
    return {"similar_skillset": leer("MATCH ()-[r:SIMILAR_SKILLSET]->() RETURN count(r) AS n")[0]["n"],
            "similar_semantic": leer("MATCH ()-[r:SIMILAR_SEMANTIC]->() RETURN count(r) AS n")[0]["n"]}


def _leiden_gds() -> None:
    """Proyección en memoria + gds.leiden.write (ids de comunidad crudos en Person.leiden_community)."""
    from graphdatascience import GraphDataScience
    gds = GraphDataScience(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        try:
            gds.graph.get(PROYECCION).drop()  # por si quedó una de una corrida cortada
        except Exception:  # noqa: BLE001
            pass
        G, _ = gds.graph.project(PROYECCION, ["Person"],
                                 {"SIMILAR_SKILLSET": {"orientation": "UNDIRECTED", "properties": "overlap"}})
        gds.leiden.write(G, writeProperty="leiden_community", relationshipWeightProperty="overlap",
                         maxLevels=100, gamma=RESOLUCION, theta=0.001, concurrency=1, randomSeed=SEMILLA)
        G.drop()
    finally:
        gds.close()


def comunidades_leiden() -> list[int]:
    """Leiden sobre SIMILAR_SKILLSET (no dirigido, peso = overlap), semilla fija. Devuelve el tamaño de cada comunidad.

    Después se RENUMERAN las comunidades 0..n-1 (más grandes primero, desempate por email): los ids crudos de GDS son
    números arbitrarios y así las consultas y la guía son legibles.
    """
    _leiden_gds()
    filas = leer("MATCH (p:Person) RETURN p.email AS e, p.leiden_community AS c")
    grupos: dict = {}
    for f in filas:
        grupos.setdefault(f["c"], []).append(f["e"])
    orden = sorted(grupos, key=lambda c: (-len(grupos[c]), min(grupos[c])))
    asign = [{"e": e, "c": rango} for rango, c in enumerate(orden) for e in grupos[c]]
    escribir("UNWIND $a AS x MATCH (p:Person {email: x.e}) SET p.leiden_community = x.c", a=asign)
    return [len(grupos[c]) for c in orden]


def construir() -> dict:
    """Todo el módulo 1, de punta a punta. Seguro de repetir."""
    esquema()
    n_personas = cargar_personas_y_skills()
    n_skills = cargar_embeddings_de_skills()
    sim = recalcular_similitudes()
    tamanos = comunidades_leiden()
    return {"personas_del_csv": n_personas, "skills_con_embedding": n_skills, **sim,
            "comunidades": len(tamanos), "tamanos_comunidades": tamanos}


def resumen_del_grafo() -> dict:
    """Conteos para verificar idempotencia."""
    q = lambda c: leer(c)[0]["n"]  # noqa: E731
    return {"Person": q("MATCH (p:Person) RETURN count(p) AS n"),
            "Skill": q("MATCH (s:Skill) RETURN count(s) AS n"),
            "KNOWS": q("MATCH ()-[r:KNOWS]->() RETURN count(r) AS n"),
            "SIMILAR_SKILLSET": q("MATCH ()-[r:SIMILAR_SKILLSET]->() RETURN count(r) AS n"),
            "SIMILAR_SEMANTIC": q("MATCH ()-[r:SIMILAR_SEMANTIC]->() RETURN count(r) AS n"),
            "indice": leer("SHOW INDEXES YIELD name, state WHERE name = $n RETURN state", n=INDICE_SKILLS)}
