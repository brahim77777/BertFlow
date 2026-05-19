#!/usr/bin/env bash
# Launch the BertFlow WebSocket backend using uv + the backend-env venv.
# Usage: ./run-backend.sh [--host HOST] [--port PORT]
#
# The rag_rust.so is compiled for CPython 3.13 and lives in backend/backend-env.
# We tell uv to use that venv directly (UV_PROJECT_ENVIRONMENT) instead of
# creating its own, so all rag_rust / websockets deps are available.

set -euo pipefail

HOST="${1:---host}"
if [[ "$HOST" == "--host" ]]; then
  shift 2>/dev/null || true
fi

UV_PROJECT_ENVIRONMENT=backend/backend-env \
  uv run --no-sync -- python -m backend "$@"
