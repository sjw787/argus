#!/usr/bin/env bash
# start.sh — Start Argus for Athena frontend + backend
#
# Usage:
#   ./start.sh          # prod mode  (serves built frontend from FastAPI on :8000)
#   ./start.sh dev      # dev mode   (Vite on :5173, FastAPI on :8000 with reload)
#   ./start.sh --help

set -euo pipefail

MODE="${1:-prod}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$SCRIPT_DIR/venv"

# ── Colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[argus]${RESET} $*"; }
success() { echo -e "${GREEN}[argus]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[argus]${RESET} $*"; }
error()   { echo -e "${RED}[argus]${RESET} $*" >&2; }

# ── Help ───────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  echo -e "${BOLD}Argus for Athena start script${RESET}"
  echo ""
  echo "  ./start.sh          Start in prod mode (built frontend served by FastAPI)"
  echo "  ./start.sh dev      Start in dev mode  (Vite dev server + FastAPI with --reload)"
  echo ""
  echo "  Backend:   http://localhost:8000"
  echo "  Frontend:  http://localhost:5173  (dev only)"
  exit 0
fi

if [[ "$MODE" != "dev" && "$MODE" != "prod" ]]; then
  error "Unknown mode: $MODE. Use 'dev' or 'prod'."
  exit 1
fi

# ── Prerequisite checks ────────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  error "Python venv not found at $VENV_DIR"
  error "Run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/package.json" ]]; then
  error "Frontend directory not found at $FRONTEND_DIR"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  warn "node_modules not found — running npm install..."
  npm --prefix "$FRONTEND_DIR" install
fi

# Activate venv so uvicorn/argus are on PATH
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Make sure argus package is importable
export PYTHONPATH="$SCRIPT_DIR/src"

# ── Cleanup on exit ────────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  info "Shutting down..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  success "Stopped."
}
trap cleanup EXIT INT TERM

# ── PROD mode ──────────────────────────────────────────────────────────────────
if [[ "$MODE" == "prod" ]]; then
  STATIC_DIR="$SCRIPT_DIR/src/argus/api/static"

  if [[ ! -f "$STATIC_DIR/index.html" ]]; then
    warn "No production build found — building frontend now..."
    npm --prefix "$FRONTEND_DIR" run build
    success "Frontend built."
  fi

  echo ""
  echo -e "${BOLD}${GREEN}▶  Argus for Athena — Production${RESET}"
  echo -e "   UI + API: ${CYAN}http://localhost:8000${RESET}"
  echo ""

  python -m uvicorn "argus.api.app:create_app" \
    --factory \
    --host 127.0.0.1 \
    --port 8000 &
  PIDS+=($!)

  wait

# ── DEV mode ───────────────────────────────────────────────────────────────────
elif [[ "$MODE" == "dev" ]]; then
  echo ""
  echo -e "${BOLD}${GREEN}▶  Argus for Athena — Development${RESET}"
  echo -e "   Frontend: ${CYAN}http://localhost:5173${RESET}"
  echo -e "   Backend:  ${CYAN}http://localhost:8000${RESET}"
  echo -e "   API docs: ${CYAN}http://localhost:8000/docs${RESET}"
  echo ""

  # Start FastAPI with reload
  ARGUS_VERBOSE_ERRORS=true python -m uvicorn "argus.api.app:create_app" \
    --factory \
    --host 127.0.0.1 \
    --port 8000 \
    --reload \
    --reload-dir "$SCRIPT_DIR/src" &
  PIDS+=($!)

  # Start Vite dev server
  npm --prefix "$FRONTEND_DIR" run dev &
  PIDS+=($!)

  wait
fi
