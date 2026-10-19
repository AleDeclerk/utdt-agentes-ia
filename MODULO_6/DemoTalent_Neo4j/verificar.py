"""Verifica la instalación de la demo: dependencias, Neo4j (con GDS y APOC), datos, API key y grafo cargado.

Se corre con  ./run.sh check . Hace UNA llamada mínima de embeddings y UNA de generación para comprobar que tu clave
y los modelos funcionan: consume una fracción insignificante de la cuota.
"""
import importlib
import sys

from google.genai import types

import comun

fallas = 0


def ok(msg: str) -> None:
    print(f"  [OK]        {msg}")


def mal(msg: str) -> None:
    global fallas
    fallas += 1
    print(f"  [FALLA]     {msg}")


def pendiente(msg: str) -> None:
    print(f"  [PENDIENTE] {msg}")


def main() -> int:
    print("Verificando la demo de talento")
    ok(f"Python {sys.version.split()[0]}")
    for modulo in ("google.adk", "google.genai", "neo4j", "dotenv", "graphdatascience"):
        try:
            importlib.import_module(modulo)
            ok(f"import {modulo}")
        except ImportError:
            mal(f"falta {modulo}: corré ./setup.sh")

    # Neo4j: conexión y plugins.
    neo4j_ok = False
    try:
        comun.driver().verify_connectivity()
        neo4j_ok = True
        ok(f"Neo4j responde en {comun.NEO4J_URI}")
        ver = comun.leer("RETURN gds.version() AS g, apoc.version() AS a")[0]
        ok(f"plugins: GDS {ver['g']}, APOC {ver['a']}")
    except Exception as e:  # noqa: BLE001
        if neo4j_ok:
            mal(f"Neo4j responde pero faltan los plugins GDS/APOC ({type(e).__name__}): ./run.sh reset y ./run.sh up")
        else:
            mal(f"Neo4j no responde en {comun.NEO4J_URI} ({type(e).__name__}): ./run.sh up")

    # Datos.
    for nombre in ("expanded_skills.csv", "skills_descripciones.csv"):
        if (comun.DATOS / nombre).exists():
            ok(f"datos/{nombre}")
        else:
            pendiente(f"falta datos/{nombre}: ./run.sh datos (o ./run.sh 01, que los baja)")

    # API key y modelos.
    if not (comun.RAIZ / ".env").exists():
        mal("falta el archivo .env: copiá .env.example a .env y pegá tu GOOGLE_API_KEY")
    else:
        try:
            cliente = comun.cliente_gemini()
            r = comun.con_reintentos(
                lambda: cliente.models.embed_content(
                    model=comun.EMBED_MODEL, contents="prueba",
                    config=types.EmbedContentConfig(task_type=comun.TAREA_EMBEDDING, output_dimensionality=comun.DIM)),
                "embeddings")
            n = len(r.embeddings[0].values)
            (ok if n == comun.DIM else mal)(f"embeddings con {comun.EMBED_MODEL}: {n} dimensiones")
            g = comun.con_reintentos(
                lambda: cliente.models.generate_content(model=comun.DEMO_MODEL, contents="Respondé solo con la palabra: ok"),
                "modelo")
            ok(f"{comun.DEMO_MODEL} responde: {(g.text or '').strip()[:40]!r}")
        except SystemExit as e:
            mal(str(e))
        except Exception as e:  # noqa: BLE001
            mal(f"falló la llamada a Gemini ({type(e).__name__}): {str(e)[:200]}")

    # Grafo.
    if neo4j_ok:
        try:
            n = comun.leer("MATCH (p:Person) RETURN count(p) AS n")[0]["n"]
            (ok if n >= 100 else pendiente)(f"grafo cargado: {n} personas" if n >= 100 else "grafo vacío: ./run.sh 01")
        except Exception as e:  # noqa: BLE001
            mal(f"no se pudo leer el grafo ({type(e).__name__})")

    print()
    print("Todo listo." if fallas == 0 else f"{fallas} verificación(es) fallaron.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
