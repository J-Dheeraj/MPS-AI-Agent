# MPS-AI-Agent — Personal AI Agent for Singapore MPs

A self-hosted personal AI agent purpose-built for Singapore Members of Parliament conducting **Meet-the-People Sessions (MPS)** and constituency casework.

The agent acts as a trusted aide — briefing the MP before each constituent meeting, triaging cases to the correct government agency in real time, drafting formal appeal letters, and maintaining a private knowledge graph of policy, cases, and constituent history. All data stays on-device. No constituent information is ever sent to a cloud service.

Built on the NanoClaw v2 platform with Claude (Anthropic Agent SDK).

---

## What the agent does

| Task | Description |
|---|---|
| **Pre-meeting briefing** | Surfaces everything known about a constituent and their case history before the MP walks in |
| **Live case triage** | Given a one-line problem description, identifies the agency, the exact scheme, and the eligibility criteria — instantly |
| **Appeal letter drafting** | Produces a formatted MP appeal letter ready for signature; correct tone, correct agency, correct policy citation |
| **Policy lookup** | Answers questions about HDB, CPF, MOM, MOH, MSF, ICA, IRAS, LTA, MOE, PA schemes — with 2025/2026 Budget updates |
| **Pending case digest** | Weekly summary of cases awaiting agency replies |
| **Scheduled briefings** | Morning or pre-MPS summaries of pending matters and recent policy changes |

---

## Agency coverage

The agent has built-in knowledge of:

- **HDB** — BTO grants, resale eligibility, rental flat appeals, HFE letter, income ceilings
- **CPF** — OA/SA/MA/RA, MediSave claims, CPF LIFE, MRSS, 2026 OW ceiling update
- **MOM** — EP/S Pass/WP/LTVP, salary disputes, TADM, retrenchment
- **MOH** — MediShield Life, CHAS, MediFund, CareShield Life, Pioneer/Merdeka Generation Package
- **MSF** — ComCare (Crisis / SMTA / PA), Silver Support, SSO referrals
- **ICA** — PR appeals, citizenship, LTVP/LTVP+ extensions
- **IRAS** — GST Voucher, S&CC and U-Save rebates, income tax disputes
- **LTA** — Senior concessions, WAV subsidy, disabled parking
- **MOE** — FAS, Edusave, school transfers, DSA
- **PA / CDCs** — CDC Vouchers, grassroots referrals, community disputes

---

## Architecture

```
MP's devices (WhatsApp / Telegram / Web UI / CLI)
        │
        ▼
MPS-AI-Agent host process  (Node.js · src/index.ts)
  ├─ Router          → validates sender → writes to inbound.db
  ├─ Container runner → one isolated Docker container per channel group
  ├─ Delivery        → polls outbound.db → sends replies back to MP
  ├─ Scheduler       → morning briefings, weekly digests, reminders
  └─ OneCLI proxy    → intercepts all container API calls → injects credentials
        │
        ▼  (one container per active group)
Docker container  (Bun runtime)
  ├─ Claude Agent SDK   → reasoning, triage, letter drafting
  ├─ mnemon             → private case + policy knowledge graph (SQLite)
  ├─ whisper.cpp        → on-device voice transcription (voice notes → text)
  ├─ Ollama client      → local semantic search (nomic-embed-text)
  └─ groups/main/       → bind-mounted; CLAUDE.md loaded every session
        │
        ▼
  inbound.db   ← host writes, container reads
  outbound.db  ← container writes, host reads
```

**Key files:**

- `groups/main/CLAUDE.md` — agent identity, agency knowledge base, letter format, behavioural rules
- `~/.config/nanoclaw/sender-allowlist.json` — controls who can trigger the agent (MP's number only)
- `~/.config/nanoclaw/mount-allowlist.json` — controls what the container can access on disk

---

## Security

Constituent data is highly sensitive. Every security control is non-negotiable.

| Control | What it does |
|---|---|
| **API key isolation** | OneCLI Agent Vault proxies all Anthropic API calls — the container never holds a raw key |
| **Sender allowlist** | Only the MP's verified phone number or Telegram ID can trigger the agent; all others are silently dropped |
| **Container isolation** | Each channel group runs in its own Docker container with its own filesystem and Claude session |
| **Mount allowlist** | Containers can only access explicitly permitted directories — `.ssh`, `.aws`, credentials are blocked |
| **Local-only voice** | whisper.cpp transcribes voice notes on-device; audio bytes never leave the machine |
| **Local-only embeddings** | nomic-embed-text runs in Ollama locally; no document content sent to cloud embedding APIs |
| **Web UI binding** | Web UI binds to `127.0.0.1` only — not accessible from the network |
| **Group name validation** | Group folder names are strictly validated (alphanumeric, hyphens, underscores only) |

> **On prompt injection:** This is an acknowledged open problem. The sender allowlist is the primary defence. Do not connect the agent to systems whose compromise would be severe.

---

## Prerequisites

Run in your **WSL2 Ubuntu** terminal:

```bash
# 1. Confirm WSL2
wsl.exe --list --verbose   # VERSION must show 2 for Ubuntu

# 2. Build tools
sudo apt-get update && sudo apt-get install -y build-essential python3 git curl

# 3. Docker reachable from WSL
docker ps
# If not: Docker Desktop → Settings → Resources → WSL Integration → enable Ubuntu

# 4. Clone into Linux filesystem (not /mnt/c/ — 10-100x slower)
cd ~
git clone https://github.com/J-Dheeraj/MPS-AI-Agent nanoclaw
cd nanoclaw

# 5. Anthropic API key ready (sk-ant-...)
# https://console.anthropic.com/settings/api-keys — add $10–20 credit
```

---

## Installation

```bash
cd ~/nanoclaw
bash nanoclaw.sh
```

The installer:

1. Installs Node 22 (nvm) and pnpm 10
2. Installs **OneCLI Agent Vault** and stores your API key — the agent never sees it directly
3. Builds the Docker agent container image
4. Creates `~/.config/nanoclaw/mount-allowlist.json` and `sender-allowlist.json`
5. Registers a systemd user service

---

## First-time setup

### 1. Customise the agent identity

Edit `groups/main/CLAUDE.md` — replace `[MP NAME]` and `[CONSTITUENCY]` with the MP's actual name and constituency before first use.

### 2. Set your sender allowlist

Edit `~/.config/nanoclaw/sender-allowlist.json`:

```json
{
  "defaultMode": "drop",
  "groups": {
    "main": {
      "mode": "drop",
      "allowedSenders": ["6591234567@s.whatsapp.net"]
    }
  }
}
```

Replace `6591234567` with the MP's number in international format. `drop` mode means any message from any other number is silently ignored and not stored.

### 3. Pair your channel

**WhatsApp:**
```
/add-whatsapp
```
Scan the QR code: WhatsApp → Settings → Linked Devices → Link a Device.

**Telegram:**
```
/add-telegram
```
Create a bot via `@BotFather`, paste the token when prompted.

**Web UI:** Available immediately at `http://localhost:3080`.

### 4. Set up local AI

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text

# Connect to NanoClaw
# In the web UI: /add-ollama
```

Voice transcription (whisper.cpp) is included in the container — no extra setup needed.

### 5. Build the policy knowledge base

In any connected chat, ingest key policy documents:

```
ingest this: https://www.hdb.gov.sg/residential/buying-a-flat/understanding-your-eligibility-and-housing-loan-options/flat-and-grant-eligibility
ingest this: https://www.cpf.gov.sg/member/retirement-income/cpf-life
ingest this: https://www.msf.gov.sg/comcare
```

Or attach PDFs of agency circulars, Budget statements, or COS debates directly to the chat.

---

## Using the agent

### Live triage during MPS

```
Constituent: elderly lady, 72, husband passed away, can't afford hospital bill at SGH
```

The agent will identify MediFund, CHAS eligibility, and recommend whether to refer to the hospital's medical social worker or write to MOH directly.

---

### Pre-meeting briefing

```
brief me on [constituent name] before I meet them at 7pm
```

The agent retrieves everything in the knowledge graph about that person — case history, previous letters, pending replies, sensitivity flags.

---

### Draft an appeal letter

```
draft a letter to HDB appealing for [constituent name] who was rejected for a rental flat. Single mother, 2 kids, income $1,800/month.
```

The agent produces a ready-to-sign letter in the correct format, citing the right scheme and eligibility criteria.

---

### Policy lookup

```
what is the income ceiling for CHAS blue card?
has the CPF OW ceiling changed for 2026?
what are the FAS criteria for MOE schools?
```

---

### Scheduled briefings

```
every Tuesday at 6pm, brief me on cases with no reply after 3 weeks
every morning at 8am, summarise any new policy updates relevant to my constituency
```

---

## Security verification checklist

```bash
# 1. No API keys in any container
docker inspect $(docker ps -q) | grep -i "sk-ant\|anthropic_api\|api_key"
# Expected: no output

# 2. Sender allowlist active — send from a number not in your allowlist
# Expected: no response, nothing stored

# 3. Mount allowlist enforced
docker run --rm -v ~/.ssh:/test alpine ls /test
# Expected: permission error

# 4. Voice stays on-device — check container logs during a voice note
docker logs $(docker ps -q --filter name=whatsapp) --tail 20
# Expected: "whisper transcription complete" — no external audio API calls

# 5. Embeddings local only
ollama list | grep nomic-embed-text
# Expected: model listed; no outbound calls to embedding APIs during ingestion

# 6. Web UI localhost only
# From another machine: curl http://YOUR_PC_IP:3080
# Expected: connection refused
```

---

## Project structure

```
nanoclaw/
├── groups/
│   └── main/
│       └── CLAUDE.md              ← Agent identity, agency knowledge, letter format
├── src/
│   ├── index.ts                   # Host process orchestrator
│   ├── router/index.ts            # Message routing + sender validation
│   ├── security/
│   │   ├── groupNames.ts          # Strict name validation
│   │   ├── senderAllowlist.ts     # drop / trigger enforcement
│   │   └── mountAllowlist.ts      # Mount path enforcement
│   ├── channels/
│   │   ├── whatsapp.ts            # Baileys connector
│   │   ├── telegram.ts            # Telegram bot
│   │   ├── webui.ts               # Express on 127.0.0.1:3080
│   │   └── cli.ts                 # Terminal interface
│   ├── container/runner.ts        # Docker spawner (no API keys passed)
│   ├── delivery/index.ts          # outbound.db poller
│   └── scheduler/index.ts         # Cron task runner
├── container/
│   ├── Dockerfile                 # Bun/Alpine agent image
│   ├── build.sh
│   └── agent/
│       ├── index.ts               # Claude agentic loop
│       ├── mnemon/index.ts        # SQLite + FTS5 knowledge graph
│       └── tools/
│           ├── ingest.ts          # URL / document ingestion
│           └── search.ts          # Semantic search
├── public/index.html              # Web chat UI
├── config/examples/               # Example security config files
├── nanoclaw.sh                    # Installer
├── start-nanoclaw.sh              # Manual start (no systemd)
└── .env.example
```

---

## Important caveats

1. **Constituent confidentiality is paramount.** The sender allowlist must be configured before pairing any channel. Default mode is `drop` — all unknown senders are silently ignored.

2. **Policy accuracy.** Singapore policies change with each Budget (February) and Committee of Supply (March). The agent flags when information may be outdated, but always verify with the agency before sending a letter under the MP's name.

3. **Prompt injection is not solved.** Rate limits and the sender allowlist reduce the blast radius but do not eliminate the risk. Do not connect the agent to external systems whose compromise would be severe.

4. **WhatsApp ToS.** Baileys uses the WhatsApp Web protocol, which is against WhatsApp's ToS for automated use. This is for personal/professional use only.

5. **API costs.** Monitor usage at [console.anthropic.com/usage](https://console.anthropic.com/usage). Set a spending limit before going live.

---

## References

- [Anthropic Console](https://console.anthropic.com)
- [OneCLI Agent Vault](https://github.com/onecli/onecli)
- [NanoClaw platform](https://github.com/nanocoai/nanoclaw)
- [HDB](https://www.hdb.gov.sg) · [CPF](https://www.cpf.gov.sg) · [MOM](https://www.mom.gov.sg) · [MOH](https://www.moh.gov.sg) · [MSF](https://www.msf.gov.sg) · [ICA](https://www.ica.gov.sg) · [IRAS](https://www.iras.gov.sg) · [LTA](https://www.lta.gov.sg) · [MOE](https://www.moe.gov.sg)

---

## License

MIT
