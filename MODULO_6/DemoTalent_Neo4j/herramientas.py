"""Herramientas del agente reclutador: cada una es un patrón de recorrido del grafo con nombre propio.

Son funciones Python normales: ADK deriva el esquema de la firma y del docstring.
El agente elige la herramienta y sus argumentos; el CÓDIGO fija todo lo demás:
  - el Cypher es una plantilla fija con parámetros (el modelo nunca escribe Cypher);
  - todas son de SOLO LECTURA;
  - topes: MAX_SKILLS por consulta y MAX_RESULTADOS por respuesta;
  - un fallo se devuelve como {"error": ...}: una herramienta que lanza una excepción mata la corrida.
"""
import functools

from comun import INDICE_SKILLS, UMBRAL_CONSULTA, embed, leer

MAX_SKILLS = 5
MAX_RESULTADOS = 10
K_VECTOR = 3   # skills más cercanas que se consideran por cada texto de la consulta


def _seguro(fn):
    """Convierte cualquier excepción en {"error": ...} para que el modelo la vea y la corrida siga."""
    @functools.wraps(fn)
    def envoltura(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    return envoltura


def _norm(texto: str) -> str:
    return "".join(c for c in texto.lower() if c.isalnum())


def _acotar(items: list[str]) -> list[str]:
    limpios = [s.strip() for s in items if isinstance(s, str) and s.strip()]
    return list(dict.fromkeys(limpios))[:MAX_SKILLS]


def _persona(nombre: str) -> dict | None:
    """Busca una persona sin distinguir mayúsculas. Si no existe, devuelve sugerencias."""
    r = leer("MATCH (p:Person) WHERE toLower(p.name) = toLower($n) "
             "RETURN p.name AS name, p.email AS email, p.leiden_community AS comunidad", n=nombre.strip())
    return r[0] if r else None


def _no_encontrada(nombre: str) -> dict:
    parecidas = leer("MATCH (p:Person) WHERE toLower(p.name) CONTAINS toLower($n) RETURN p.name AS n LIMIT 5",
                     n=nombre.strip().split(" ")[-1])
    return {"error": "persona no encontrada", "buscada": nombre, "sugerencias": [x["n"] for x in parecidas]}


def _skills_cercanas(texto: str) -> list[dict]:
    """Skills del grafo cercanas a un texto libre (índice vectorial) con score >= UMBRAL_CONSULTA."""
    v = embed([texto])[0]
    rs = leer(f"MATCH (d:Skill) SEARCH d IN (VECTOR INDEX {INDICE_SKILLS} FOR $v LIMIT $k) SCORE AS score "
              "RETURN d.name AS skill, score", v=v, k=K_VECTOR)
    return [{"skill": r["skill"], "score": round(r["score"], 3)} for r in rs if r["score"] >= UMBRAL_CONSULTA]


def _relacionadas(skills: list[str]) -> list[str]:
    """Vecinas por la arista SIMILAR_SEMANTIC (precalculada en la ingesta)."""
    rs = leer("MATCH (s:Skill)-[:SIMILAR_SEMANTIC]-(t:Skill) WHERE s.name IN $s RETURN DISTINCT t.name AS n ORDER BY n",
              s=skills)
    return [r["n"] for r in rs if r["n"] not in skills]


@_seguro
def habilidades_de_persona(nombre: str) -> dict:
    """Devuelve las skills que tiene una persona, dado su nombre completo (por ejemplo 'Lucy Turner')."""
    p = _persona(nombre)
    if not p:
        return _no_encontrada(nombre)
    skills = leer("MATCH (p:Person {email: $e})-[:KNOWS]->(s:Skill) RETURN s.name AS n ORDER BY n", e=p["email"])
    return {"persona": p["name"], "email": p["email"], "skills": [s["n"] for s in skills]}


@_seguro
def habilidades_similares(habilidades: list[str]) -> dict:
    """Dado un conjunto de skills o temas en texto libre (máximo 5, por ejemplo ['PowerBI', 'visualización de datos']),
    devuelve las skills del grafo que coinciden por significado y las que están semánticamente relacionadas con ellas."""
    out = []
    for h in _acotar(habilidades):
        directas = _skills_cercanas(h)
        nombres = [d["skill"] for d in directas]
        out.append({"consulta": h, "coincidencias": directas, "relacionadas": _relacionadas(nombres)})
    if not out:
        return {"error": "no se indicó ninguna habilidad"}
    return {"resultados": out}


# Puntaje = skills EXACTAS en común (SIMILAR_SKILLSET.overlap) + suma de los scores de los pares de skills
# semánticamente relacionadas (SIMILAR_SEMANTIC). UNION ALL, no UNION: UNION descartaría filas repetidas.
_SIMILARES = """
MATCH (p1:Person {email: $email})
CALL (p1) {
  MATCH (p1)-[r:SIMILAR_SKILLSET]-(p2:Person) RETURN p2, r.overlap AS puntaje, 'exacta' AS tipo
  UNION ALL
  MATCH (p1)-[:KNOWS]->(:Skill)-[r:SIMILAR_SEMANTIC]-(:Skill)<-[:KNOWS]-(p2:Person) WHERE p2 <> p1
  RETURN p2, r.score AS puntaje, 'semantica' AS tipo
}
WITH p1, p2, sum(puntaje) AS puntaje
WHERE puntaje >= 1
RETURN p2.name AS persona, p2.email AS email, round(puntaje, 2) AS puntaje,
       p2.leiden_community = p1.leiden_community AS misma_comunidad,
       [(p1)-[:KNOWS]->(s:Skill)<-[:KNOWS]-(p2) | s.name] AS skills_exactas_en_comun,
       [(p1)-[:KNOWS]->(a:Skill)-[:SIMILAR_SEMANTIC]-(b:Skill)<-[:KNOWS]-(p2) | a.name + ' ~ ' + b.name] AS pares_relacionados,
       [(p2)-[:KNOWS]->(s:Skill) | s.name] AS todas_sus_skills
ORDER BY puntaje DESC, persona LIMIT $k
"""


@_seguro
def personas_similares(nombre: str) -> dict:
    """Encuentra personas con skills parecidas a las de una persona dada (por su nombre completo). Combina las skills
    exactas en común con las skills semánticamente relacionadas, y dice si pertenecen a la misma comunidad (Leiden)."""
    p = _persona(nombre)
    if not p:
        return _no_encontrada(nombre)
    rs = leer(_SIMILARES, email=p["email"], k=5)
    mias = [s["n"] for s in leer("MATCH (:Person {email: $e})-[:KNOWS]->(s:Skill) RETURN s.name AS n ORDER BY n",
                                 e=p["email"])]
    return {"persona": p["name"], "skills_de_la_persona": mias, "similares": rs}


@_seguro
def personas_con_habilidades(habilidades: list[str]) -> dict:
    """Busca personas que tengan ciertas skills (máximo 5, por ejemplo ['Python', 'AWS']). Cada skill se amplía por
    significado (skills parecidas cuentan). Ordena por cuántas de las skills pedidas cubre cada persona."""
    terminos, sin_match = [], []
    for h in _acotar(habilidades):
        cercanas = [d["skill"] for d in _skills_cercanas(h)]
        if not cercanas:
            sin_match.append(h)
            continue
        # «principales»: la skill que se llama igual que lo pedido (ignorando mayúsculas y signos: PowerBI = Power BI);
        # si ninguna se llama igual (p. ej. «Cloud Native»), las más cercanas por significado.
        iguales = [s for s in cercanas if _norm(s) == _norm(h)]
        principales = iguales or cercanas
        terminos.append({"termino": h, "principales": principales,
                         "skills": list(dict.fromkeys(cercanas + _relacionadas(cercanas)))})
    if not terminos:
        return {"error": "ninguna de las habilidades pedidas coincide con el grafo", "sin_coincidencia": sin_match}
    # Se ordena primero por cuántas de las skills PEDIDAS tiene la persona de verdad (principales) y recién
    # después por las parecidas: quien tiene Python y AWS va antes que quien tiene Java y Azure.
    rs = leer(
        "UNWIND $t AS t MATCH (p:Person)-[:KNOWS]->(s:Skill) WHERE s.name IN t.skills "
        "WITH p, collect(DISTINCT t.termino) AS cubiertas, "
        "     collect(DISTINCT CASE WHEN s.name IN t.principales THEN t.termino END) AS cubiertas_directo, "
        "     collect(DISTINCT s.name) AS skills "
        "RETURN p.name AS persona, p.email AS email, size(cubiertas_directo) AS cubre_directo, "
        "       size(cubiertas) AS cubre_con_parecidas, skills "
        "ORDER BY cubre_directo DESC, cubre_con_parecidas DESC, size(skills) DESC, persona LIMIT $k",
        t=terminos, k=MAX_RESULTADOS)
    return {"pedidas": [t["termino"] for t in terminos], "sin_coincidencia": sin_match,
            "skills_principales": {t["termino"]: t["principales"] for t in terminos},
            "skills_consideradas": {t["termino"]: t["skills"] for t in terminos}, "personas": rs}


HERRAMIENTAS = [habilidades_de_persona, habilidades_similares, personas_similares, personas_con_habilidades]
