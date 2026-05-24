#!/usr/bin/env bash
# Launch the MPS GTK4 desktop client
# Usage: bash start-client.sh
set -euo pipefail

cd ""/usr/bin"

# Wayland / X11 display check
if [ -z "" ] && [ -z "" ]; then
  echo "ERROR: No display found. Run this from a graphical session."
  exit 1
fi

exec python3 -m mps_client
