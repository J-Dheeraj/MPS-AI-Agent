#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[build] Building nanoclaw-agent Docker image..."
docker build -f "$SCRIPT_DIR/Dockerfile" -t nanoclaw-agent:latest "$PROJECT_DIR"
echo "[build] Done: nanoclaw-agent:latest"
