"""MÓDULO 1 — del CSV al grafo de talento: Person/Skill, similitudes, embeddings y comunidades (Leiden).

  python 01_grafo.py                 # construye el grafo (idempotente)
  python 01_grafo.py --calibrar      # imprime los scores de similitud para elegir los umbrales
  python 01_grafo.py --idempotencia  # construye dos veces y compara los conteos

Requiere el Neo4j de esta demo (./run.sh up) y los datos (./run.sh datos). Normalmente se corre con ./run.sh 01.
"""
import argparse

import comun
import grafo_talento as g

# Ejemplos para calibrar: skill contra skill, y texto libre contra skills.
SKILLS_EJEMPLO = ["Python", "Power BI", "Data Visualization", "AWS", "Security", "Cloud Native"]
CONSULTAS_EJEMPLO = ["data visualizations and dashboards", "deployments", "API coding",
                     "Machine Learning frameworks", "Cloud expertise", "visualización de datos"]


def calibrar() -> None:
    g.esquema()
    g.cargar_personas_y_skills()
    g.cargar_embeddings_de_skills()
    print("Score de Neo4j = (1 + coseno) / 2. Vecinas de cada skill (sin la propia):")
    for n in SKILLS_EJEMPLO:
        if not comun.leer("MATCH (s:Skill {name: $n}) RETURN s.name", n=n):
            print(f"  {n}: no existe como skill del grafo"); continue
        vs = [v for v in g.vecinas(n, 8) if v["skill"] != n]
        print(f"  {n:<20} " + ", ".join(f"{v['skill']} {v['score']:.3f}" for v in vs))
    print("\nTexto libre contra las skills:")
    for q in CONSULTAS_EJEMPLO:
        v = comun.embed([q])[0]
        rs = comun.leer(
            f"MATCH (d:Skill) SEARCH d IN (VECTOR INDEX {comun.INDICE_SKILLS} FOR $v LIMIT 6) SCORE AS score "
            "RETURN d.name AS skill, score", v=v)
        print(f"  {q:<36} " + ", ".join(f"{r['skill']} {r['score']:.3f}" for r in rs))
    print(f"\nUmbrales vigentes: skill-skill >= {comun.UMBRAL_SKILL_SKILL}, consulta >= {comun.UMBRAL_CONSULTA}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrar", action="store_true")
    ap.add_argument("--idempotencia", action="store_true")
    a = ap.parse_args()
    comun.esperar_neo4j()
    if a.calibrar:
        calibrar()
        return
    r1 = g.construir()
    print("Construcción:", r1)
    print("Grafo:", g.resumen_del_grafo())
    if a.idempotencia:
        estado1 = g.resumen_del_grafo()
        r2 = g.construir()
        estado2 = g.resumen_del_grafo()
        print("Segunda construcción:", r2)
        print("IDEMPOTENTE:", "SÍ" if estado1 == estado2 and r1["tamanos_comunidades"] == r2["tamanos_comunidades"]
              else f"NO\n  1ª: {estado1}\n  2ª: {estado2}")
    print("429 durante la corrida:", comun.AVISOS_429 or "ninguno")


if __name__ == "__main__":
    main()
