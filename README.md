# MPS-AI-Agent — nanoClaw (Production System)

A self-hosted AI agent purpose-built for Singapore Members of Parliament conducting **Meet-the-People Sessions (MPS)** and constituency casework.

Volunteers use a **native GTK4 desktop app** to draft formal appeal letters with AI assistance. Vetters review drafts in the same app. The MP approves in the MPS case management platform the next day. All AI inference runs fully **on-premises via Ollama** — no Anthropic API key, no cloud calls, no constituent data ever leaves the LAN.

> **Companion repo:** [MPS-AI-Agent-Hermes](https://github.com/J-Dheeraj/MPS-AI-Agent-Hermes) runs offline weekly to improve agent skill files via GEPA (Generalised Experience-driven Policy Adaptation, ICLR 2026).

---

## Architecture

```
┌─────────────────────────────── LAN only ─────────────────────────────────┐
│                                                                            │
│  [Volunteer laptop]      [Vetter laptop]       [Central server]           │
│   GTK4 client             GTK4 client           FastAPI  (mps_server)     │
│   start-client.sh    ──── REST + WebSocket ───► port 8000                 │
│                                                     │                      │
│                                                     ▼                      │
│                                              Ollama  :11434                │
│                                              llama3.2:3b  (or 3.1:8b)     │
│                                              nomic-embed-text              │
│                                                     │                      │
│                                                     ▼                      │
│                                              SQLite  (mps.db)             │
│                                              Append-only audit log         │
└────────────────────────────────────────────────────────────────────────────┘

MP reviews letters next day in MPS case management platform (separate system).
MPS platform auto-sends approved letters to agencies.
```

---

## MPS Night workflow

```
1. Admin opens session → mps_server /sessions/open
2. Volunteers log in to GTK4 client
3. For each resident:
   a. Search / register resident (NRIC stored masked: S****567A)
   b. Create case (agency, case type, urgency, re-appeal?)
   c. Enter case notes
   d. Click Generate Draft → Ollama streams letter in real-time
   e. Edit draft if needed → Copy to Clipboard
   f. Paste into MPS case management platform
   g. Submit for vetting
4. Vetters review queue → Approve or Return with comment
5. Volunteer revises if returned → resubmits
6. Admin closes session when all cases done (can run past midnight)
7. Next day: MP reviews in MPS platform → approves → platform auto-sends
```

---

## What we are deliberately NOT doing

| Skipped | Why |
|---------|-----|
| Anthropic API / OneCLI vault | Fully replaced by Ollama on-premises |
| WhatsApp / Telegram for core workflow | GTK4 native app is faster and safer on old Linux laptops |
| Browser UI for volunteers | Old laptops struggle; native GTK4 uses ~50–80 MB RAM |
| Receptionist data entry screen | Volunteers enter directly during the interview |
| MP using nanoClaw | MP reviews and approves in the MPS platform only |
| Internet access from server | Air-gapped — all inference is local |

---

## Component overview

### `mps_server/` — FastAPI backend (Python)

REST + WebSocket API. Runs on the central server, LAN-only (127.0.0.1:8000).

| Module | Purpose |
|--------|---------|
| `database.py` | SQLAlchemy models: User, Session, Resident, Case, Letter, FeedbackEntry, AuditLog |
| `auth.py` | JWT tokens, bcrypt passwords, RBAC (volunteer / vetter / admin), lockout after 5 failures |
| `main.py` | FastAPI app entry point, auto-creates DB tables, seeds default admin |
| `services/audit.py` | Append-only SHA-256 hash-chained audit log — tamper-evident |
| `services/ollama_client.py` | LLM queue (max 3 concurrent), streaming via Ollama, LETTER / REAPPEAL / QA system prompts |
| `routers/auth_router.py` | POST /auth/login (OAuth2 form), /logout, /register |
| `routers/sessions_router.py` | Open / close MPS session lifecycle |
| `routers/residents_router.py` | Search + create residents (full NRIC never stored) |
| `routers/cases_router.py` | Case CRUD, volunteer submit, vetter-pass, vetter-return |
| `routers/letters_router.py` | WebSocket /letters/ws/draft (streaming), /letters/ws/qa, save, freeze |
| `routers/feedback_router.py` | Log corrections → vetter validates → Hermes GEPA receives approved only |

### `mps_client/` — GTK4 native desktop app (Python + PyGObject)

Runs on each volunteer and vetter laptop. ~50–80 MB RAM. Works on old Linux hardware.

| File | Purpose |
|------|---------|
| `api_client.py` | Async REST + WebSocket client (httpx + websockets) |
| `async_bridge.py` | Background asyncio loop, GTK-thread-safe callbacks via GLib.idle_add |
| `login_window.py` | Adwaita login screen with lockout messaging |
| `main_window.py` | Split-pane main: case list (left) + letter view or vetter panel (right). Role-based. |
| `widgets/case_form.py` | New Case dialog — resident search/register, agency, urgency, re-appeal toggle |
| `widgets/letter_view.py` | **Core tool** — notes entry, Generate, streaming draft, edit, **Copy to Clipboard**, submit |
| `widgets/vetter_view.py` | Vetter queue, letter read-only view, Approve / Return-with-comment |

### Data model

```
Resident (permanent across sessions)
  └── Cases (one per session visit)
        └── Letters (versioned drafts)
              └── FeedbackEntry (vetter-validated corrections → Hermes GEPA)

Session (one per MPS night)
  └── Cases

AuditLog (append-only, SHA-256 hash chain)
```

**NRIC handling:** masked at point of entry (`S****567A`). Full NRIC never stored, never logged.

---

## Roles

| Role | What they can do |
|------|-----------------|
| `volunteer` | Create cases, generate drafts, edit, copy, submit for vetting |
| `vetter` | Review queue, approve letters, return with comment, log feedback |
| `admin` | All volunteer + vetter actions, open/close sessions, register users |
| *(MP)* | Reviews and approves in MPS platform — does not use nanoClaw |

---

## Security

All security controls are non-negotiable. No constituent data leaves the LAN.

| Control | Implementation |
|---------|---------------|
| **No cloud AI** | Ollama runs on-premises; llama3.2:3b / llama3.1:8b; no API key |
| **NRIC masking** | Full NRIC never stored — S****567A format enforced at API layer |
| **JWT auth** | 60-minute tokens, bcrypt passwords, account lockout after 5 failures |
| **RBAC** | Volunteers cannot access vetter queue; vetters cannot open sessions |
| **Append-only audit log** | SHA-256 hash chain — every action logged, tampering detectable |
| **LAN-only binding** | Server binds to 127.0.0.1 — not reachable from internet |
| **Feedback isolation** | Only vetter-validated, anonymised corrections reach Hermes GEPA |
| **No full-NRIC storage** | Validated at `POST /residents/` — API rejects unmasked NRICs |
| **Frozen letters** | Once vetted, letters are frozen — no further edits |
| **Docker isolation** | WhatsApp/Telegram groups (if used) still get per-group containers |

> **On prompt injection:** Acknowledged open problem. The sender allowlist and RBAC reduce blast radius. Do not connect the agent to systems whose compromise would be severe.

---

## Installation

### Server (central machine)

```bash
# Prerequisites
sudo apt-get install -y python3 python3-pip

# Clone
cd ~
git clone https://github.com/J-Dheeraj/MPS-AI-Agent-_nanoClaw.git nanoclaw
cd nanoclaw

# Install Python dependencies
pip3 install -r mps_server/requirements.txt --user

# Run hardening (generates SECRET_KEY, sets file permissions)
bash harden.sh

# Install and start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b          # fast, works on most hardware
# ollama pull llama3.1:8b        # better quality, needs 8GB+ RAM
ollama pull nomic-embed-text

# Start the server
bash start-server.sh
# OR as systemd service (recommended):
systemctl --user start mps-server
systemctl --user enable mps-server
```

### Create user accounts

The server starts with a default `admin / admin123` account. **Change it immediately.**

Open `http://127.0.0.1:8000/docs` (Swagger UI) and use `POST /auth/register`:

```bash
# Example: create a volunteer account
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"ali","password":"STRONG_PW","role":"volunteer","full_name":"Ali Bin Ahmad"}'
```

Roles: `volunteer`, `vetter`, `admin`.

### Open a session (admin, on MPS night)

```bash
curl -X POST http://127.0.0.1:8000/sessions/open \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-05-24"}'
```

### Volunteer / Vetter laptops

```bash
# Install GTK4 (once per laptop)
sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
pip3 install httpx websockets --user

# Point client at the server IP
# Edit mps_client/api_client.py:
#   SERVER    = "http://192.168.X.X:8000"
#   WS_SERVER = "ws://192.168.X.X:8000"

# Launch
cd ~/nanoclaw
bash start-client.sh
```

---

## Connecting to Hermes GEPA

After each MPS session, vetters validate corrections in the GTK4 client (`Feedback` tab).

Every Sunday, Hermes GEPA reads approved corrections from `/feedback/approved` and improves the skill files. No constituent data is ever sent.

```yaml
# profiles/mps-volunteers/hermes-config.yaml
llm:
  provider: ollama
  model: llama3.2:3b
gepa:
  schedule: "0 2 * * 0"    # Sunday 2am
  feedback_endpoint: http://127.0.0.1:8000/feedback/approved
  data_isolation: strict    # never stores raw feedback — extracts policy corrections only
```

Full Hermes setup: [MPS-AI-Agent-Hermes](https://github.com/J-Dheeraj/MPS-AI-Agent-Hermes)

---

## Security verification checklist

Run before every MPS night:

```bash
# 1. No API keys in any process
grep -r "sk-ant" ~/nanoclaw/ 2>/dev/null
# Expected: no output

# 2. Ollama is local only
curl http://localhost:11434/api/tags | grep llama
# Expected: model listed — no external calls

# 3. Server is LAN-only
ss -tlnp | grep 8000
# Expected: 127.0.0.1:8000 (not 0.0.0.0)

# 4. DB permissions
ls -la mps_server/mps.db
# Expected: -rw------- (600)

# 5. SECRET_KEY changed from default
grep "CHANGE_THIS" mps_server/.env
# Expected: no output

# 6. Audit log is append-only (spot check)
curl http://127.0.0.1:8000/audit -H "Authorization: Bearer <admin_token>" | head -5
# Expected: hash chain entries

# 7. No full NRIC in DB
sqlite3 mps_server/mps.db "SELECT nric_masked FROM residents;" | grep -v '\*'
# Expected: no output (all entries are masked)
```

---

## Project structure

```
nanoclaw/
├── mps_server/                    ← FastAPI backend (NEW)
│   ├── main.py                    # App entry point
│   ├── database.py                # SQLAlchemy models
│   ├── auth.py                    # JWT + RBAC
│   ├── requirements.txt
│   ├── .env                       # Secrets (not committed)
│   ├── services/
│   │   ├── audit.py               # Hash-chained audit log
│   │   └── ollama_client.py       # LLM queue + streaming
│   └── routers/
│       ├── auth_router.py
│       ├── sessions_router.py
│       ├── residents_router.py
│       ├── cases_router.py
│       ├── letters_router.py
│       └── feedback_router.py
├── mps_client/                    ← GTK4 native desktop app (NEW)
│   ├── __main__.py                # Entry point (python3 -m mps_client)
│   ├── api_client.py              # Async REST + WebSocket client
│   ├── async_bridge.py            # asyncio ↔ GTK thread bridge
│   ├── login_window.py            # Login screen
│   ├── main_window.py             # Main split-pane window
│   └── widgets/
│       ├── case_form.py           # New Case dialog
│       ├── letter_view.py         # Streaming draft + Copy button
│       └── vetter_view.py         # Vetter review panel
├── groups/
│   ├── main/                      # MP private channel (WhatsApp/Telegram)
│   │   ├── CLAUDE.md
│   │   ├── singapore-knowledge-ingestion.md
│   │   ├── singapore-historical-policies.md
│   │   └── singapore-auto-update-tasks.md
│   ├── mps-volunteers/            # NEW — Hermes GEPA config + skill stubs
│   │   ├── hermes-config.yaml
│   │   └── skills/
│   │       ├── HDB.md
│   │       ├── CPF.md
│   │       ├── MSF.md
│   │       ├── MOH.md
│   │       ├── MOM.md
│   │       ├── ICA.md
│   │       └── letter-format.md
│   └── mps-vetters/
│       └── CLAUDE.md
├── start-server.sh                ← Launch FastAPI server
├── start-client.sh                ← Launch GTK4 client
├── harden.sh                      ← Generate secrets, set permissions
├── MPS_DEPLOY.md                  ← Full deployment guide
├── INTEGRATION.md                 ← nanoClaw + Hermes combined workflow
├── mcp-crm-server.py              ← CRM Bridge (optional, for WhatsApp/Telegram)
├── weekly-skill-update.sh         ← Hermes GEPA weekly pipeline
├── src/                           ← NanoClaw host process (WhatsApp/Telegram channels)
├── container/                     ← Docker agent image
└── nanoclaw.sh                    ← Original installer
```

---

## Important notes

1. **No cloud AI.** Ollama runs entirely on-premises. `llama3.2:3b` works on laptops with 4GB RAM. Use `llama3.1:8b` for better letter quality if the server has 8GB+ RAM.

2. **Sessions run until all cases are done.** No fixed end time. Common to run past midnight.

3. **MP does not use this system.** The MP reviews and approves letters in the MPS platform the next day. MPS platform auto-sends.

4. **Copy-paste is intentional.** Volunteers generate the draft in the GTK4 client, copy it, and paste it into the MPS platform. This avoids any API integration between systems and keeps the workflow simple.

5. **Old laptops are fine.** GTK4 + Python uses ~50–80 MB RAM. No browser engine. Tested on Ubuntu 22.04.

6. **Policy accuracy.** Always verify policy thresholds with the agency before sending a letter under the MP's name. Singapore policies change at Budget (February) and COS (March).

---

## References

- [MPS-AI-Agent-Hermes](https://github.com/J-Dheeraj/MPS-AI-Agent-Hermes) — companion GEPA skill engine
- [INTEGRATION.md](./INTEGRATION.md) — combined system workflow
- [MPS_DEPLOY.md](./MPS_DEPLOY.md) — full deployment guide
- [Ollama](https://ollama.com) — local LLM inference
- [HDB](https://www.hdb.gov.sg) · [CPF](https://www.cpf.gov.sg) · [MOM](https://www.mom.gov.sg) · [MOH](https://www.moh.gov.sg) · [MSF](https://www.msf.gov.sg) · [ICA](https://www.ica.gov.sg)
- [SupportGoWhere](https://supportgowhere.life.gov.sg)

---

## License

MIT
