#!/usr/bin/env bash
# Start the MPS FastAPI server
# Usage: bash start-server.sh [--prod]
set -euo pipefail

cd ""/usr/bin"

# Load .env if present
if [ -f mps_server/.env ]; then
  set -a
  source mps_server/.env
  set +a
fi

RELOAD_FLAG="--reload"
if [ "" = "--prod" ]; then
  RELOAD_FLAG=""
  export DISABLE_DOCS=1
fi

echo "Starting mps-server on 127.0.0.1:8000"
exec python3 -m uvicorn mps_server.main:app   --host "127.0.0.1"   --port "8000"   
