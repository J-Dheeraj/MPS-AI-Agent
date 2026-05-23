#!/bin/bash
# weekly-skill-update.sh
# Exports anonymised feedback patterns from nanoClaw to Hermes GEPA.
# Run every Sunday. Takes ~20 minutes including manual review.
#
# Security rule: constituent data never crosses to Hermes.
# Only anonymised correction patterns (no NRIC, no names, no case IDs).

set -e

NANOCLAW_DIR="$HOME/nanoclaw"
HERMES_DIR="$HOME/mps-hermes-agent"
FEEDBACK_LOG="$NANOCLAW_DIR/groups/main/feedback-log.md"
FEEDBACK_INPUT="$HERMES_DIR/feedback-input.md"
SKILLS_AUTO="$HERMES_DIR/skills/auto"
DATE=$(date +%Y-%m-%d)

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "================================================="
echo "  MPS Agent — Weekly Skill Update"
echo "  $(date '+%A, %d %B %Y')"
echo "================================================="
echo ""

# ── Phase 1: Check feedback log exists and has content ──────────────────────

if [ ! -f "$FEEDBACK_LOG" ]; then
  echo -e "${RED}ERROR: feedback-log.md not found at $FEEDBACK_LOG${NC}"
  echo "Has any feedback been logged this week? Exiting."
  exit 1
fi

ENTRY_COUNT=$(grep -c "^-" "$FEEDBACK_LOG" 2>/dev/null || echo 0)
echo -e "${GREEN}✓${NC} Found feedback log with $ENTRY_COUNT entries"

if [ "$ENTRY_COUNT" -lt 1 ]; then
  echo -e "${YELLOW}WARN: No feedback entries found. Nothing to evolve. Exiting.${NC}"
  exit 0
fi

# ── Phase 2: PII check — must pass before export ────────────────────────────

echo ""
echo -e "${YELLOW}SECURITY CHECK — Scanning feedback log for potential PII...${NC}"

# Check for NRIC patterns (S/T/F/G followed by 7 digits and a letter)
if grep -qiE '[STFG][0-9]{7}[A-Z]' "$FEEDBACK_LOG"; then
  echo -e "${RED}ERROR: Possible NRIC detected in feedback log.${NC}"
  echo "Remove all NRICs before exporting. Exiting."
  exit 1
fi

# Check for phone number patterns (8-digit Singapore numbers)
if grep -qE '\b[689][0-9]{7}\b' "$FEEDBACK_LOG"; then
  echo -e "${RED}ERROR: Possible phone number detected in feedback log.${NC}"
  echo "Remove all phone numbers before exporting. Exiting."
  exit 1
fi

echo -e "${GREEN}✓${NC} No NRIC or phone number patterns detected"
echo ""
echo "--- MANUAL REVIEW REQUIRED ---"
echo "Open $FEEDBACK_LOG and confirm:"
echo "  1. No constituent names"
echo "  2. No addresses"
echo "  3. No case reference numbers traceable to individuals"
echo "  4. Only anonymised policy corrections and patterns"
echo ""
echo "Press Enter when confirmed clean, Ctrl+C to abort."
read -r

# ── Phase 3: Export to Hermes ────────────────────────────────────────────────

echo -e "${GREEN}✓${NC} Exporting anonymised patterns to Hermes..."

cp "$FEEDBACK_LOG" "$FEEDBACK_INPUT"
echo "# Exported: $DATE" >> "$FEEDBACK_INPUT"

# ── Phase 4: Run GEPA evolution cycle ───────────────────────────────────────

echo ""
echo "Running Hermes GEPA skill evolution..."
echo "(This may take 2–5 minutes)"
echo ""

cd "$HERMES_DIR"

# Check if hermes CLI is available
if command -v hermes &>/dev/null; then
  # Bug 14 fixed: correct Hermes CLI syntax — --profile precedes the subcommand.
  # --input is not a valid flag; Hermes reads from feedback-input.md by convention.
  hermes --profile mps-main skills evolve --now
else
  echo -e "${YELLOW}WARN: hermes CLI not found in PATH.${NC}"
  echo "Start Hermes manually and run: run skills evolve now"
  echo "Then press Enter to continue with review."
  read -r
fi

# ── Phase 5: Show GEPA output ────────────────────────────────────────────────

echo ""
echo "================================================="
echo "  GEPA OUTPUT — Review before applying"
echo "================================================="

if [ -d "$SKILLS_AUTO" ] && [ "$(ls -A "$SKILLS_AUTO" 2>/dev/null)" ]; then
  echo ""
  echo "Generated/updated files in skills/auto/:"
  ls -la "$SKILLS_AUTO/"
  echo ""
  echo "--- REVIEW EACH FILE ---"
  echo "Check for:"
  echo "  ✅ Threshold corrections matching your feedback log"
  echo "  ✅ New case patterns from real session types"
  echo "  ❌ Fabricated policy (anything you don't recognise)"
  echo "  ❌ Any text resembling constituent details"
  echo ""
  echo "Press Enter when review is complete."
  read -r
else
  echo -e "${YELLOW}No new files generated in skills/auto/${NC}"
  echo "GEPA may need more feedback entries (aim for 5+ before first cycle)."
fi

# ── Phase 6: Apply approved changes ─────────────────────────────────────────

echo ""
echo "================================================="
echo "  APPLY APPROVED CHANGES"
echo "================================================="
echo ""
echo "Manually merge approved content from:"
echo "  $SKILLS_AUTO/"
echo "Into:"
echo "  $NANOCLAW_DIR/groups/main/CLAUDE.md"
echo ""
echo "When done, press Enter to restart nanoClaw."
read -r

# Restart nanoClaw
echo "Restarting nanoClaw..."
if systemctl --user is-active --quiet nanoclaw-v2-main 2>/dev/null; then
  systemctl --user restart nanoclaw-v2-*
  echo -e "${GREEN}✓${NC} nanoClaw restarted"
else
  echo -e "${YELLOW}systemd service not found. Restart nanoClaw manually.${NC}"
fi

# ── Phase 7: Archive this week's feedback ───────────────────────────────────

ARCHIVE_DIR="$NANOCLAW_DIR/groups/main/feedback-archive"
mkdir -p "$ARCHIVE_DIR"
cp "$FEEDBACK_LOG" "$ARCHIVE_DIR/feedback-$DATE.md"

# Clear current week's log (keep the header)
cat > "$FEEDBACK_LOG" << 'EOF'
# MPS Agent — Feedback Log

Log anonymised correction patterns here after each MPS session.
Format: `- agency: X | wrong: Y | correct: Z`
No NRIC, no names, no addresses, no case reference numbers.

EOF

echo ""
echo -e "${GREEN}✓${NC} This week's feedback archived to feedback-archive/$DATE.md"
echo -e "${GREEN}✓${NC} feedback-log.md reset for next week"
echo ""
echo "================================================="
echo -e "  ${GREEN}Weekly skill update complete.${NC}"
echo "================================================="
echo ""
