# nanoClaw + Hermes Integration

## What this is

nanoClaw handles all live constituent interactions (production).
Hermes runs offline as a skill improvement engine (weekly cycle).
They never connect directly. A human review step sits between them.

```
nanoClaw (live) → anonymised patterns → Hermes GEPA → reviewed skills → nanoClaw CLAUDE.md
```

---

## Security boundary — non-negotiable

**Constituent data never crosses to Hermes.**

Only anonymised correction patterns flow from nanoClaw to Hermes:
- ✅ Policy threshold corrections
- ✅ Case type patterns (generic)
- ✅ Letter structure improvements
- ❌ NRIC numbers
- ❌ Constituent names or addresses
- ❌ Case reference numbers
- ❌ Financial details tied to any individual
- ❌ Anything from the CRM

---

## What each system does

| Capability | nanoClaw | Hermes |
|---|---|---|
| WhatsApp constituent intake | ✅ | ❌ |
| Telegram channels | ✅ | ❌ (offline) |
| Web UI for caseworkers | ✅ | ❌ |
| API key isolation (OneCLI vault) | ✅ | ❌ |
| Docker container isolation | ✅ | ❌ |
| Local voice transcription | ✅ | ❌ |
| Local embeddings (Ollama) | ✅ | ❌ |
| Knowledge graph (mnemon) | ✅ | ❌ |
| CRM case management | ✅ | ❌ |
| Automated policy monitoring | ✅ | ❌ |
| GEPA self-improving skills | ❌ | ✅ |
| Structured feedback correction | ✅ (log) | ✅ (process) |
| Weekly skill curation | ❌ | ✅ |

---

## Weekly workflow

### During MPS sessions (nanoClaw side)
Log corrections in the main group chat:
```
/feedback [wrong] → [correct] | agency: [X]
```
The agent appends anonymised entries to `groups/main/feedback-log.md`.

### Every Sunday (~20 minutes)
```bash
cd ~/nanoclaw
bash weekly-skill-update.sh
```

The script:
1. Scans feedback-log.md for NRIC/phone patterns (auto-rejects if found)
2. Prompts manual review of the log before export
3. Copies anonymised patterns to Hermes as `feedback-input.md`
4. Triggers Hermes GEPA evolution cycle
5. Shows generated skill changes in `skills/auto/` for review
6. Prompts manual merge of approved changes into nanoClaw CLAUDE.md
7. Restarts nanoClaw
8. Archives the week's log and resets for next week

### Review checklist before applying GEPA output
- [ ] Threshold figures match your feedback log entries
- [ ] No fabricated policy (anything you don't recognise from real sessions)
- [ ] No text resembling constituent details
- [ ] Changes are improvements, not regressions

---

## Repository layout

```
MPS-AI-Agent-_nanoClaw/          MPS-AI-Agent-Hermes/
├── groups/main/                  ├── profiles/mps-main/
│   ├── CLAUDE.md                 │   └── config.yaml  ← offline mode
│   └── feedback-log.md          ├── skills/
├── weekly-skill-update.sh        │   ├── SKILL-*.md
└── INTEGRATION.md                │   └── auto/        ← GEPA output
                                  └── OFFLINE-MODE.md
```

---

## Hermes offline mode

Hermes must be configured with **no live connections**:
- Telegram token: empty
- CRM MCP servers: none
- `auto_capture: false` (no live sessions to capture from)
- `curator.enabled: true` with 7-day interval

See `MPS-AI-Agent-Hermes/OFFLINE-MODE.md` for full config.

---

## First run checklist

Before running `weekly-skill-update.sh` for the first time:

- [ ] nanoClaw is live and handling real MPS sessions
- [ ] At least 5 feedback entries logged in `feedback-log.md`
- [ ] Hermes repo cloned to `~/mps-hermes-agent/`
- [ ] Hermes configured in offline mode (no bot tokens)
- [ ] `hermes` CLI available in PATH (or manual GEPA trigger ready)
- [ ] `~/mps-hermes-agent/skills/auto/` directory exists

```bash
mkdir -p ~/mps-hermes-agent/skills/auto
chmod +x ~/nanoclaw/weekly-skill-update.sh
```

---

## References

- nanoClaw repo: https://github.com/J-Dheeraj/MPS-AI-Agent-_nanoClaw
- Hermes repo: https://github.com/J-Dheeraj/MPS-AI-Agent-Hermes
- nanoClaw docs: https://docs.nanoclaw.dev
- Hermes GEPA: SKILL-feedback.md in the Hermes repo
