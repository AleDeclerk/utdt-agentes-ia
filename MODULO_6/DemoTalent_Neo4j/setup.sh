#!/usr/bin/env bash
# Setup de la demo de talento: crea el venv, instala dependencias y arma .env si no existe.
# Se corre una sola vez por máquina.
set -euo pipefail
cd "$(dirname "$0")"

# Python: se probó con 3.12; las dependencias publican paquetes de 3.10 a 3.13.
PY=""
for c in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 \
     && "$c" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)'; then
    PY="$c"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Hace falta Python entre 3.10 y 3.13 (se probó con 3.12). Instalalo y volvé a correr ./setup.sh" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creando entorno virtual (.venv) con $($PY --version)..."
  "$PY" -m venv .venv
fi

source .venv/bin/activate

echo "Instalando dependencias..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "Se creó .env a partir de .env.example."
  echo "Abrilo y pegá tu GOOGLE_API_KEY (gratis en https://aistudio.google.com/apikey)."
else
  echo ".env ya existe — no se tocó."
fi

echo
if ! command -v docker >/dev/null 2>&1; then
  echo "AVISO: no encontré Docker. El Neo4j de la demo corre en un contenedor: instalá Docker (https://docs.docker.com/get-docker/)." >&2
fi
echo "Setup listo. Siguiente:  ./run.sh up  ·  ./run.sh check  ·  ./run.sh 01"
