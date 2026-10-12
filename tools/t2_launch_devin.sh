#!/usr/bin/env bash
# Launch the Track 2 lanes as headless Devin SWE-2 Max agents (operator-run).
#
#   bash tools/t2_launch_devin.sh            # all lanes in docs/track2/agent_prompts/
#   bash tools/t2_launch_devin.sh L2 L4      # selected lanes
#
# Each agent gets _common.md + its lane prompt, runs in this worktree with
# --permission-mode dangerous, and is detached so this script returns at
# once. Logs + exported transcripts land in $T2_LOG_DIR; each lane writes
# its completion report to docs/track2/agent_reports/<LANE>.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEVIN="${DEVIN_EXE:-/c/Users/Nikhil/AppData/Local/Programs/Devin/resources/app/extensions/windsurf/devin/bin/devin.exe}"
MODEL="${DEVIN_MODEL:-swe-2-max}"
LOG_DIR="${T2_LOG_DIR:-/c/Users/Nikhil/.claude/jobs/5356bf8a/tmp/devin}"
PROMPTS="$ROOT/docs/track2/agent_prompts"
mkdir -p "$LOG_DIR" "$ROOT/docs/track2/agent_reports"

[ -x "$DEVIN" ] || { echo "devin.exe not found at $DEVIN" >&2; exit 1; }

lanes=("$@")
if [ ${#lanes[@]} -eq 0 ]; then
  for f in "$PROMPTS"/L*_*.md; do lanes+=("$(basename "$f" | cut -d_ -f1)"); done
fi

cd "$ROOT"
for lane in "${lanes[@]}"; do
  lane_file=$(ls "$PROMPTS/${lane}"_*.md 2>/dev/null | head -1)
  [ -n "$lane_file" ] || { echo "no prompt for $lane" >&2; exit 1; }
  prompt="$LOG_DIR/${lane}.prompt.md"
  cat "$PROMPTS/_common.md" "$lane_file" > "$prompt"
  nohup "$DEVIN" -p --prompt-file "$prompt" --model "$MODEL" \
    --permission-mode dangerous --respect-workspace-trust false \
    --export "$LOG_DIR/${lane}.transcript.md" \
    > "$LOG_DIR/${lane}.log" 2>&1 < /dev/null &
  echo "$!" > "$LOG_DIR/${lane}.pid"
  echo "launched $lane (pid $!) -> $LOG_DIR/${lane}.log"
done
