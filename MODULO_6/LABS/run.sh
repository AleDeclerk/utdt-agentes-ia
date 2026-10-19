#!/usr/bin/env bash
# Corre cualquier ejemplo de los labs del Módulo 6 con el venv activado y las
# variables de .env cargadas. Requiere haber corrido ./setup.sh antes.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "No existe .venv — corré ./setup.sh primero." >&2
  exit 1
fi

source .venv/bin/activate
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
export PYTHONUNBUFFERED=1

uso() {
  cat >&2 <<USO
Uso: ./run.sh <ejemplo> [subcomando o argumentos]

Sin API key (la primera vez descargan el modelo de embeddings; después corren sin red):
  1            Retrieval con FAISS y scores engañosos (Ej. 1 C-D)
  2            BM25 vs. semántico vs. híbrido y barrido de alpha (Ej. 3)
  graph        GraphRAG: recorrido por saltos sobre un grafo de 8 tripletas (Ej. 4 B)
  graph-adk2   GraphRAG como Workflow de ADK 2
  offline      Los cuatro anteriores en secuencia

Con GOOGLE_API_KEY (llaman a Gemini):
  1e           RAG completo: recuperar, armar el prompt y generar (Ej. 1 E)
  1f           RAG semántico vs. BM25 con una paráfrasis (Ej. 1 F)
  4a           Self-note: el modelo anota el contexto antes de responder (Ej. 4 A)
  4b           GraphRAG con síntesis de Gemini, con 3 y 5 saltos (Ej. 4 B)
  agentic      Agentic RAG: el agente elige herramientas, el código fija los topes (acepta --repeticiones N)
  memoria      Memoria de sesión y de largo plazo con ADK (Ej. 2 A-C)
  2d           El agente escribe en session.state con una tool (Ej. 2 D)
  faiss  [reset|guardar|recordar|todo]   Memoria de largo plazo local (FAISS + SQLite); por defecto: todo
  bank   [reset|guardar|recordar|todo]   Memory Bank (réplica del patrón): hechos y consolidación; por defecto: todo
  all          Todo lo anterior, en ese orden (son muchas llamadas: con la capa gratuita puede tardar)
USO
  exit 1
}

necesita_key() {
  if [ -z "${GOOGLE_API_KEY:-}" ] || [ "$GOOGLE_API_KEY" = "tu-api-key" ]; then
    echo "Este ejemplo llama a Gemini y falta la API key." >&2
    echo "Pegala en .env (GOOGLE_API_KEY=...). Se genera gratis en https://aistudio.google.com/apikey" >&2
    exit 1
  fi
}

# Corre un ejemplo; si falla, lo anota y sigue (para `all` y `offline`).
FALLARON=()
correr() {
  echo
  echo "################ $* ################"
  python "$@" || FALLARON+=("$*")
}

ejemplo() {
  case "$1" in
    1)          correr rag_pipeline.py ;;
    2)          correr comparar_metodos.py ;;
    graph)      correr graphrag.py ;;
    graph-adk2) correr graphrag_adk2.py ;;
    1e)         necesita_key; correr ejercicio_1e_rag_generacion.py ;;
    1f)         necesita_key; correr ejercicio_1f_rag_vs_bm25.py ;;
    4a)         necesita_key; correr ejercicio_4a_self_note.py ;;
    4b)         necesita_key; correr ejercicio_4b_graphrag_gemini.py ;;
    agentic)    necesita_key; correr agentic_rag.py "${@:2}" ;;
    memoria)    necesita_key; correr memoria_adk.py ;;
    2d)         necesita_key; correr ejercicio_2d_estado_registrar_dato.py ;;
    faiss)      necesita_key; correr memoria_faiss.py "${2:-todo}" ;;
    bank)       necesita_key; correr memory_bank.py "${2:-todo}" ;;
    *)          uso ;;
  esac
}

case "${1:-}" in
  "") uso ;;
  offline)
    for e in 1 2 graph graph-adk2; do ejemplo "$e"; done
    ;;
  all)
    necesita_key
    for e in 1 2 graph graph-adk2 1e 1f 4a 4b agentic memoria 2d faiss bank; do ejemplo "$e"; done
    ;;
  *) ejemplo "$@" ;;
esac

if [ "${#FALLARON[@]}" -gt 0 ]; then
  echo
  echo "Terminaron con error: ${FALLARON[*]}" >&2
  exit 1
fi
