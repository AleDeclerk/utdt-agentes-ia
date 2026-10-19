"""APÉNDICE OPCIONAL (no forma parte de la demo) — de texto libre a grafo: un LLM extrae personas y skills de biografías y se cargan al grafo.

Las dos biografías son las del workshop de Neo4j en el que se basa la demo (datos públicos de colegas de Neo4j, con sus correos del trabajo).
Se extrae con Gemini en modo salida estructurada (esquema Pydantic) y el resultado se cachea en disco (.cache/):
la segunda corrida no llama al modelo.

Detalle importante: al modelo se le da la lista de skills que YA existen en el grafo y se le pide
usar exactamente ese nombre cuando corresponda. Sin eso, «Power BI», «PowerBI» y «Microsoft Power BI» serían
tres nodos distintos y la identidad de las skills se rompería. Las skills nuevas se aceptan igual.

  python 03_extraccion.py            # extrae (o lee del caché) y carga; recalcula similitudes y comunidades
  python 03_extraccion.py --sin-cache  # fuerza la llamada al modelo

Se corre con ./run.sh 03. Suma 2 personas al grafo (102): las cifras de guia_demo_KG.md ya no coinciden.
Para volver a las 100 de la guía: ./run.sh reset, ./run.sh up y ./run.sh 01.
"""
import argparse
import hashlib
import json

from google.genai import types
from pydantic import BaseModel, Field

import comun
import grafo_talento as g
from comun import DEMO_MODEL, RAIZ, con_reintentos, escribir, leer

BIOS = [
    # Las dos biografías del workshop de Neo4j (datos públicos de colegas de Neo4j), textuales.
    # (texto libre, correo esperado, skills que un lector humano marcaría)
    (""" 
    Kristof "speedy gonzales" Neys, Graph Data Science Director at Neo4j. Kristof excel at Machine 
    Learning and has written more Quantified Path Patterns in Cypher than anyone else. Want to know more,
    drop him an email at kristof.neys@neo4j.com
    """,
     "kristof.neys@neo4j.com", {"Machine Learning", "Cypher"}),
    (""" 
    Håkan Löfqvist, Solutions Engineer at Neo4j. Håkan prefer using java 
    over python, but nothing beats hacking cypher queries and using Graph Technology 
    to deliver insane success :) Email: hakan.lofqvist@neo4j.com
    """,
     "hakan.lofqvist@neo4j.com", {"Java", "Cypher"}),
]


class Persona(BaseModel):
    name: str = Field(description="Nombre completo, sin apodos ni títulos")
    email: str = Field(description="Correo electrónico de la persona")
    skills: list[str] = Field(description="Skills técnicas de la persona, con nombre corto")


_CACHE = RAIZ / ".cache" / "extraccion.json"


def _prompt(vocabulario: list[str]) -> str:
    return (
        "Extraé de la biografía el nombre completo, el correo y las skills técnicas de la persona. "
        "Ignorá apodos, cargos y empresas. Sé conciso con las skills. "
        "Estas skills YA existen en el grafo; si una skill de la biografía es la misma, usá EXACTAMENTE ese "
        f"nombre: {', '.join(vocabulario)}. Si no está en la lista, usá un nombre corto en inglés técnico habitual."
    )


def extraer(bio: str, vocabulario: list[str], usar_cache: bool = True) -> tuple[dict, bool]:
    """Devuelve (datos, uso_modelo)."""
    prompt = _prompt(vocabulario)
    clave = hashlib.sha256(json.dumps([DEMO_MODEL, prompt, bio]).encode()).hexdigest()
    cache = json.loads(_CACHE.read_text()) if _CACHE.exists() else {}
    if usar_cache and clave in cache:
        return cache[clave], False
    cliente = comun.cliente_gemini()  # en una variable: un Client temporal se cierra al recolectarse y falla el envío
    r = con_reintentos(
        lambda: cliente.models.generate_content(
            model=DEMO_MODEL, contents=f"{prompt}\n\nBIOGRAFÍA:\n{bio}",
            config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json",
                                               response_schema=Persona)),
        "extracción")
    datos = Persona.model_validate_json(r.text).model_dump()
    cache[clave] = datos
    _CACHE.parent.mkdir(exist_ok=True)
    _CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return datos, True


def cargar(personas: list[dict]) -> None:
    escribir(
        "UNWIND $rows AS row MERGE (p:Person {email: row.email}) SET p.name = row.name "
        "WITH p, row UNWIND row.skills AS sk MERGE (s:Skill {name: sk}) MERGE (p)-[:KNOWS]->(s)",
        rows=personas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-cache", action="store_true")
    a = ap.parse_args()
    comun.esperar_neo4j()
    if not leer("MATCH (s:Skill) RETURN s.name LIMIT 1"):
        raise SystemExit("El grafo está vacío. Corré primero:  ./run.sh 01")
    antes = g.resumen_del_grafo()
    vocabulario = [r["n"] for r in leer("MATCH (s:Skill)<-[:KNOWS]-(:Person) WHERE s.description IS NOT NULL "
                                        "RETURN DISTINCT s.name AS n ORDER BY n")]
    extraidas, llamadas = [], 0
    for bio, email_esperado, oro in BIOS:
        d, uso = extraer(bio, vocabulario, usar_cache=not a.sin_cache)
        llamadas += uso
        d["skills"] = sorted({s.strip() for s in d["skills"] if s.strip()})
        faltan = sorted(oro - set(d["skills"]))
        print(f"\n{d['name']} <{d['email']}>  ({'modelo' if uso else 'caché'})")
        print(f"  skills extraídas: {d['skills']}")
        print(f"  correo esperado: {'OK' if d['email'] == email_esperado else 'DISTINTO (' + email_esperado + ')'}"
              f" · skills del oro que faltan: {faltan or 'ninguna'}")
        print(f"  skills nuevas (no estaban en el grafo): {sorted(set(d['skills']) - set(vocabulario)) or 'ninguna'}")
        extraidas.append(d)
    cargar(extraidas)
    g.cargar_embeddings_de_skills()   # las skills nuevas se embeben por nombre
    g.recalcular_similitudes()
    g.comunidades_leiden()
    despues = g.resumen_del_grafo()
    print(f"\nLlamadas al modelo: {llamadas} (0 = todo salió del caché)")
    print("Antes: ", antes)
    print("Después:", despues)
    print("429 durante la corrida:", comun.AVISOS_429 or "ninguno")


if __name__ == "__main__":
    main()
