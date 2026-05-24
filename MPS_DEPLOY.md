# MPS AI Agent — Deployment Guide

## Architecture



## First-time setup (run on the server machine)

### 1. Run hardening script
```bash
cd ~/nanoclaw
bash harden.sh
```

### 2. Start Ollama
```bash
~/.local/bin/ollama serve &
~/.local/bin/ollama pull llama3.2:3b   # or llama3.1:8b for better quality
~/.local/bin/ollama pull nomic-embed-text
```

### 3. Start the server
```bash
bash start-server.sh
# OR as systemd service:
systemctl --user start mps-server
systemctl --user status mps-server
```

### 4. Create user accounts
Open http://127.0.0.1:8000/docs in your browser, authenticate as admin/admin123,
then use POST /auth/register to create volunteer and vetter accounts:

```bash
# Change admin password first
curl -X POST http://127.0.0.1:8000/auth/register   -H "Authorization: Bearer <admin_token>"   -H "Content-Type: application/json"   -d '{"username":"volunteer1","password":"STRONG_PW","role":"volunteer","full_name":"Ali Bin Ahmad"}'
```

### 5. Open a session
```bash
curl -X POST http://127.0.0.1:8000/sessions/open   -H "Authorization: Bearer <admin_token>"   -H "Content-Type: application/json"   -d '{"date":"2026-05-24"}'
```

## On each volunteer/vetter laptop

### Install dependencies (once)
```bash
sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
~/.local/bin/pip3 install httpx websockets
```

### Configure server IP
Edit ~/nanoclaw/mps_client/api_client.py:
```python
SERVER    = "http://192.168.X.X:8000"   # LAN IP of server
WS_SERVER = "ws://192.168.X.X:8000"
```

### Launch the client
```bash
cd ~/nanoclaw
bash start-client.sh
```

## MPS Night workflow

1. Admin opens session via web UI or curl
2. Volunteers log into GTK4 client
3. Each case: New Case → fill resident details → Generate Draft → edit → Copy → paste into MPS platform
4. Volunteers click Submit for Vetting when happy with draft
5. Vetters review queue → Approve or Return with comment
6. Admin closes session when all cases done
7. MP reviews next day in MPS platform → approves → MPS auto-sends letters

## Security checklist (run before every MPS night)

- [ ] Server accessible only on LAN (not internet-facing)
- [ ] Ollama bound to 127.0.0.1 only (`~/.local/bin/ollama serve`)
- [ ] .env has correct SECRET_KEY (not the default)
- [ ] admin/admin123 account deleted or password changed
- [ ] DB backed up from previous session
- [ ] Audit log intact: check /audit endpoint

## Backup
```bash
cp ~/nanoclaw/mps_server/mps.db ~/mps-backup-$(date +%Y%m%d).db
```

## Logs
```bash
journalctl --user -u mps-server -f        # if using systemd
tail -f ~/nanoclaw/logs/mps-server.log    # if using start-server.sh
```
