"""Descarga los datos de la demo (personas y descripciones de skills) desde el repositorio público de origen.

Los datos son del workshop «Talent GraphRAG» de Neo4j (datos sintéticos):
  https://github.com/neo4j-product-examples/genai-workshop/tree/main/talent
Ese repositorio no declara una licencia, así que NO los incluimos en este repositorio: cada persona los baja a su
máquina, de una versión fija (commit) y verificando su hash, para usarlos en el curso.

  python descargar_datos.py          # baja lo que falte (no repite si ya está)
  python descargar_datos.py --forzar # vuelve a bajar y reemplaza

Genera, en datos/:
  expanded_skills.csv        email, name, skills de cada persona (tal cual el original)
  skills_descripciones.csv   skill, descripcion (la columna Description del original, sin saltos de línea)
"""
import argparse
import csv
import hashlib
import io
import pathlib
import sys
import urllib.error
import urllib.request

COMMIT = "e9ecdf307c7811d763d756bea89674dee5011fe0"  # versión fija del repo de origen (no `main`, que puede cambiar)
BASE = f"https://raw.githubusercontent.com/neo4j-product-examples/genai-workshop/{COMMIT}/talent/data/"
SHA256 = {
    "expanded_skills.csv": "ee17d22baae4e5f776101711226ec28d07368dba4d96ea8be418a947fbfcc956",
    "skills_embeddings.csv": "f11160e266ec953e3b9b117435ca815ab7884f4bdda8de4d9b3450020628d447",
}
DATOS = pathlib.Path(__file__).resolve().parent / "datos"


def bajar(nombre: str) -> bytes:
    url = BASE + nombre
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            contenido = r.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"No se pudo bajar {url}\n  {e}\nRevisá tu conexión y volvé a correr:  ./run.sh datos")
    sha = hashlib.sha256(contenido).hexdigest()
    if sha != SHA256[nombre]:
        raise SystemExit(f"{nombre}: el contenido bajado no coincide con el esperado (sha256 {sha[:12]}…). No se guardó nada.")
    return contenido


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    forzar = ap.parse_args().forzar
    personas, skills = DATOS / "expanded_skills.csv", DATOS / "skills_descripciones.csv"
    if personas.exists() and skills.exists() and not forzar:
        print("datos/ ya tiene los dos archivos (usá --forzar para bajarlos de nuevo).")
        return
    DATOS.mkdir(exist_ok=True)

    personas.write_bytes(bajar("expanded_skills.csv"))
    print(f"  {personas.relative_to(DATOS.parent)}: {len(personas.read_text(encoding='utf-8').splitlines()) - 1} personas")

    # El CSV de origen trae además un embedding de OpenAI por skill (1536 números) que no usamos: nos quedamos con la descripción.
    csv.field_size_limit(sys.maxsize)
    filas = csv.DictReader(io.StringIO(bajar("skills_embeddings.csv").decode("utf-8"), newline=""))
    with open(skills, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["skill", "descripcion"])
        n = 0
        for r in filas:
            w.writerow([r["Skill"], r["Description"].replace("\n", " ")])
            n += 1
    print(f"  {skills.relative_to(DATOS.parent)}: {n} skills")
    print("Listo. Recordá que estos datos son del repositorio de Neo4j citado arriba (ver el README).")


if __name__ == "__main__":
    main()
