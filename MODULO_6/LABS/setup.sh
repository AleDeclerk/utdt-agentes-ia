#!/usr/bin/env bash
# Setup de los labs del Módulo 6: crea el venv, instala dependencias y
# arma .env si no existe. Se corre una sola vez por máquina.
set -euo pipefail
cd "$(dirname "$0")"

# Python: se probó con 3.12; sirve de 3.10 a 3.13 (con 3.14 no hay wheels de algunas dependencias).
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

# En Linux, torch de PyPI trae CUDA (varios GB). Estos labs corren en CPU: se instala la versión CPU primero,
# y el requirements.txt la da por buena porque coincide la versión.
TORCH_VERSION="$(grep -E '^torch==' requirements.txt | cut -d= -f3)"
if [ "$(uname -s)" = "Linux" ] && ! python -c "import torch" >/dev/null 2>&1; then
  echo "Instalando PyTorch en su versión CPU..."
  pip install --quiet "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
    || echo "No se pudo instalar la versión CPU de torch; se usa la de PyPI (más pesada)."
fi

pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "Se creó .env a partir de .env.example."
  echo "Completalo con tu GOOGLE_API_KEY para los ejemplos que llaman a Gemini."
else
  echo ".env ya existe — no se tocó."
fi

echo
echo "Setup listo. Probá con: ./run.sh 1   (no necesita API key)"
echo "La primera vez se descarga el modelo de embeddings (alrededor de 450 MB)."
