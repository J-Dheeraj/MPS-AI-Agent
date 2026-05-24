#!/usr/bin/env bash
# harden.sh -- Run once after initial setup to generate proper secrets
# and tighten file permissions.
set -euo pipefail

ENV_FILE="$(dirname "$0")/mps_server/.env"
DB_FILE="$(dirname "$0")/mps_server/mps.db"

echo '=== MPS Server Hardening ==='

# 1. Generate a proper SECRET_KEY
NEW_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NEW_KEY}|" "$ENV_FILE"
echo "[1/5] Generated new SECRET_KEY"

# 2. Restrict .env permissions
chmod 600 "$ENV_FILE"
echo "[2/5] .env permissions set to 600"

# 3. Restrict DB permissions
if [ -f "$DB_FILE" ]; then
  chmod 600 "$DB_FILE"
  echo "[3/5] mps.db permissions set to 600"
else
  echo "[3/5] mps.db not found (will be created on first start)"
fi

# 4. Restrict skill files (read-only for group)
chmod -R 640 "$(dirname "$0")/groups/mps-volunteers/skills/" 2>/dev/null || true
echo "[4/5] Skill files set to 640"

# 5. Remind admin to change default password
echo "[5/5] IMPORTANT: Change the default admin password!"
echo "      Start the server, then POST to /auth/register to create your real accounts."
echo "      The admin/admin123 account must be deleted or password changed."
echo ''
echo '=== Hardening complete ==='
