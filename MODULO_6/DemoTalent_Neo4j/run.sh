#!/usr/bin/env bash
# Demo de talento (GraphRAG con ADK 2 + Neo4j + Gemini). Corre cada módulo con el venv y el Neo4j de la demo.
# Requiere haber corrido ./setup.sh antes y tener Docker.
set -euo pipefail
cd "$(dirname "$0")"

CONTENEDOR="neo4j-demotalent"
SALIDAS="corridas"   # cada corrida guarda su salida acá
PY=".venv/bin/python"

uso() {
  cat >&2 <<EOT
Uso: ./run.sh {up|down|reset|status|datos|check|calibrar|01|02|03|web|all}

  up        Levanta el Neo4j de esta demo (navegador en http://localhost:7475, bolt en 7688) y espera a que esté sano
  down      Lo apaga conservando los datos
  reset     Lo apaga y BORRA el grafo (el volumen de Docker de esta demo); después: ./run.sh 01
  status    Estado del contenedor
  datos     Descarga los datos de la demo (personas y descripciones de skills) a datos/
  check     Verifica dependencias, Neo4j, datos, API key y grafo (hace 2 llamadas mínimas a Gemini)
  calibrar  Imprime los scores de similitud para elegir umbrales (01_grafo.py --calibrar)
  01        Módulo 1: CSV -> grafo, similitudes, embeddings y comunidades (Leiden)   (01_grafo.py)
  02        Módulo 2: el agente reclutador, 7 preguntas              (02_agente.py [--repeticiones N])
  03        APÉNDICE OPCIONAL: 2 biografías -> Gemini -> grafo (03_extraccion.py). Suma 2 personas (102); para volver
            a las 100 de la guía: ./run.sh reset, ./run.sh up y ./run.sh 01
  web       El agente en el navegador: adk web agentes  (http://localhost:8000, elegir «reclutador»)
  all       01 y 02 en orden

Llama a Gemini (embeddings y modelo): hace falta GOOGLE_API_KEY en .env.
EOT
  exit 1
}

requiere_docker() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 \
    || { echo "Docker no está instalado o no está corriendo. Instalalo/iniciá Docker y volvé a probar." >&2; exit 1; }
}
requiere_venv() { [ -x "$PY" ] || { echo "No existe .venv: corré ./setup.sh primero." >&2; exit 1; }; }
estado() { docker inspect -f '{{.State.Health.Status}}' "$CONTENEDOR" 2>/dev/null || echo "ausente"; }
up() {
  requiere_docker
  if [ "$(estado)" = "healthy" ]; then echo "Neo4j ya está sano ($CONTENEDOR)."; else docker compose up -d --wait; fi
}
datos() { requiere_venv; "$PY" descargar_datos.py "$@"; }
correr() {
  requiere_venv; up; mkdir -p "$SALIDAS"
  "$PY" -u "$1.py" "${@:2}" 2>&1 | tee "$SALIDAS/salida_$1.txt"
}

case "${1:-}" in
  up) up ;;
  down) requiere_docker; docker compose down ;;
  reset)
    requiere_docker
    read -r -p "Esto borra el grafo de la demo (el volumen de Docker de esta demo). ¿Seguro? [s/N] " r
    if [[ "$r" =~ ^[sS]$ ]]; then docker compose down -v; else echo "No se borró nada."; fi ;;
  status) requiere_docker; estado ;;
  datos) shift; datos "$@" ;;
  check) requiere_venv; "$PY" verificar.py ;;
  calibrar) requiere_venv; up; datos; "$PY" -u 01_grafo.py --calibrar ;;
  01) requiere_venv; datos; correr 01_grafo ;;
  02) shift; correr 02_agente "$@" ;;
  03) shift; correr 03_extraccion "$@" ;;
  web) requiere_venv; up; exec .venv/bin/adk web agentes --port "${TALENT_WEB_PORT:-8000}" ;;
  all) requiere_venv; datos; for d in 01_grafo 02_agente; do echo ">>> $d"; correr "$d"; echo "<<< OK $d"; done ;;
  *) uso ;;
esac
