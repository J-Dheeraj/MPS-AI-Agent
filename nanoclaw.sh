#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[nanoclaw]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- 1. Check WSL2 ----------
info "Checking WSL2..."
if [ -f /proc/version ] && grep -qi microsoft /proc/version; then
  info "Running in WSL2 ✓"
else
  warn "Not detected in WSL2 — continuing anyway"
fi

# ---------- 2. Check Node 22 via nvm ----------
info "Checking Node.js 22..."
export NVM_DIR="${HOME}/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  source "$NVM_DIR/nvm.sh"
else
  info "Installing nvm..."
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  source "$NVM_DIR/nvm.sh"
fi

nvm install 22 --lts 2>/dev/null || true
nvm use 22
info "Node $(node --version) ✓"

# ---------- 3. Install pnpm ----------
info "Checking pnpm..."
if ! command -v pnpm &>/dev/null; then
  npm install -g pnpm@10
fi
info "pnpm $(pnpm --version) ✓"

# ---------- 4. Install project dependencies ----------
info "Installing dependencies..."
cd "$SCRIPT_DIR"
pnpm install

# ---------- 5. OneCLI Agent Vault ----------
info "Setting up OneCLI Agent Vault..."
if ! command -v onecli &>/dev/null; then
  # Bug 5 fixed: OneCLI absence is fatal — without it, containers would hold raw API keys,
  # which violates the core security model. Do not allow setup to continue.
  error "OneCLI not found. Install it first from: https://github.com/onecli/onecli
       OneCLI is mandatory — it is the only way API keys are kept out of containers.
       Re-run this installer after OneCLI is installed."
fi
info "OneCLI found ✓"
read -rsp "Paste your Anthropic API key (sk-ant-...): " ANTHROPIC_KEY
echo
onecli vault set ANTHROPIC_API_KEY "$ANTHROPIC_KEY"
unset ANTHROPIC_KEY  # clear from shell environment immediately after storing
info "API key stored in OneCLI vault ✓ (NanoClaw will never see this key directly)"

# ---------- 5b. Install pre-commit PII hook ----------
# Bug 17: installs a git hook that blocks commits containing NRICs or phone numbers
# in feedback-log.md, preventing constituent data from reaching the public repo.
if [ -d "$SCRIPT_DIR/.git" ]; then
  cp "$SCRIPT_DIR/hooks/pre-commit" "$SCRIPT_DIR/.git/hooks/pre-commit"
  chmod +x "$SCRIPT_DIR/.git/hooks/pre-commit"
  info "Pre-commit PII scan hook installed ✓"
fi

# ---------- 6. Build Docker image ----------
info "Building agent container image..."
bash "$SCRIPT_DIR/container/build.sh"

# ---------- 7. Security config ----------
info "Setting up security configuration..."
mkdir -p "$HOME/.config/nanoclaw"

if [ ! -f "$HOME/.config/nanoclaw/mount-allowlist.json" ]; then
  cat > "$HOME/.config/nanoclaw/mount-allowlist.json" << 'EOF'
{
  "allowedPaths": [
    "~/nanoclaw/groups",
    "~/nanoclaw/data",
    "~/Documents/nanoclaw-ingest"
  ],
  "blockedPatterns": [
    ".ssh", ".aws", ".gnupg", ".config/gh", ".config/nanoclaw",
    "*.pem", "*.key", "*.p12", "*.pfx",
    "id_rsa", "id_ed25519", "credentials", ".netrc"
  ]
}
EOF
  info "mount-allowlist.json created ✓"
fi

if [ ! -f "$HOME/.config/nanoclaw/sender-allowlist.json" ]; then
  read -rp "Your phone number in international format (e.g. 6591234567): " PHONE
  cat > "$HOME/.config/nanoclaw/sender-allowlist.json" << EOF
{
  "defaultMode": "drop",
  "groups": {
    "main": {
      "mode": "drop",
      "allowedSenders": ["${PHONE}@s.whatsapp.net"]
    }
  }
}
EOF
  info "sender-allowlist.json created ✓"
fi

# ---------- 8. systemd service ----------
if command -v systemctl &>/dev/null && systemctl --user daemon-reload &>/dev/null; then
  SERVICE_FILE="$HOME/.config/systemd/user/nanoclaw-v2.service"
  mkdir -p "$(dirname "$SERVICE_FILE")"
  cat > "$SERVICE_FILE" << EOF
[Unit]
Description=NanoClaw v2 Personal AI Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$(which node) dist/index.js
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable nanoclaw-v2
  systemctl --user start nanoclaw-v2
  info "systemd service started: nanoclaw-v2 ✓"
else
  info "systemd not available — use: bash start-nanoclaw.sh"
fi

info ""
info "NanoClaw v2 installation complete!"
info "Web UI: http://localhost:3080"
info ""
info "Next steps:"
info "  1. Run the security verification checklist (see README.md)"
info "  2. Add channels: /add-whatsapp or /add-telegram in the web UI"
info "  3. Set up Ollama for local embeddings (see README.md Phase 4)"
