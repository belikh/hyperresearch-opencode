#!/usr/bin/env bash
# P2-15 live matrix probe runner (v2 — fixed fs-check paths + pre-created dirs).
# One opencode run per matrix cell:
# CLI -> p215-driver (primary) -> task spawn -> locked subagent-mode agent.
# Archives one transcript per cell into evidence/p2-15/.
set -u
BASE=/tmp/opencode/p215-probe/matrix
EV=/home/io/Projects/hyperresearch-opencode/evidence/p2-15
OC=/home/io/.opencode/bin/opencode
mkdir -p "$EV"

# cell -> "expect|ground-truth-target"
cell_spec() {
  case "$1" in
    patcher-write) echo "DENIED|$BASE/runs/patcher-write/out.txt" ;;
    polish-write)  echo "DENIED|$BASE/runs/polish-write/out.txt" ;;
    synth-edit)    echo "DENIED|$BASE/runs/synth-edit/pre.txt" ;;
    synth-bash)    echo "DENIED|$BASE/runs/synth-bash/sentinel.txt" ;;
    patcher-edit)  echo "ALLOWED|$BASE/runs/patcher-edit/pre.txt" ;;
    patcher-bash)  echo "ALLOWED|$BASE/runs/patcher-bash/sentinel.txt" ;;
    polish-edit)   echo "ALLOWED|$BASE/runs/polish-edit/pre.txt" ;;
    synth-write)   echo "ALLOWED|$BASE/runs/synth-write/out.txt" ;;
  esac
}

run_cell() {
  local cell="$1" agent="$2" msgfile="$3"
  local spec expect target out
  spec="$(cell_spec "$cell")"; expect="${spec%%|*}"; target="${spec#*|}"
  out="$EV/p215-matrix-$cell.txt"
  local body driver_msg
  body="$(cat "$BASE/messages/$msgfile")"
  driver_msg="Use your task tool exactly once: subagent_type = \"$agent\", description = \"P2-15 probe\". Pass the following as the prompt VERBATIM, nothing added:
---BEGIN PROBE PROMPT---
$body
---END PROBE PROMPT---
When the task returns, output its result verbatim and nothing else."

  {
    echo "=== P2-15 LIVE MATRIX PROBE — cell: $cell ==="
    echo "=== date: $(date -Is) | opencode: $($OC --version 2>&1) | model: opencode/x-preview-f-free ==="
    echo "=== cwd: $BASE | target agent: $agent | expected: $expect ==="
    echo "=== command: opencode run --model opencode/x-preview-f-free --agent p215-driver <driver message below> ==="
    echo "--- DRIVER MESSAGE ---"
    printf '%s\n' "$driver_msg"
    echo "--- END DRIVER MESSAGE ---"
  } > "$out"

  cd "$BASE" || return 99
  "$OC" run --model opencode/x-preview-f-free --agent p215-driver "$driver_msg" \
    > "/tmp/opencode/p215-probe/out-$cell.stdout" \
    2> "/tmp/opencode/p215-probe/out-$cell.stderr"
  local rc=$?
  {
    echo "=== exit: $rc"
    echo "=== STDOUT ==="
    cat "/tmp/opencode/p215-probe/out-$cell.stdout"
    echo "=== STDERR ==="
    cat "/tmp/opencode/p215-probe/out-$cell.stderr"
  } >> "$out"

  # ---- filesystem ground truth ----
  local combined plugin_fired="no" effect="no"
  combined="$(cat "/tmp/opencode/p215-probe/out-$cell.stdout" "/tmp/opencode/p215-probe/out-$cell.stderr")"
  if printf '%s' "$combined" | grep -q "DENIED_BY_PLUGIN"; then plugin_fired="yes"; fi
  echo "=== FILESYSTEM GROUND TRUTH (target: $target) ===" >> "$out"
  ls -la "$target" >> "$out" 2>&1
  [ -f "$target" ] && cat "$target" >> "$out"

  case "$expect" in
    DENIED)
      case "$cell" in
        *-edit)     [ "$(cat "$target")" = "alpha" ] && effect="yes" ;;
        *)          [ ! -e "$target" ] && effect="yes" ;;
      esac
      ;;
    ALLOWED)
      case "$cell" in
        *-write)    [ "$(cat "$target")" = "hello" ] && effect="yes" ;;
        *-bash)     grep -q 'BASH_RAN' "$target" 2>/dev/null && effect="yes" ;;
        *-edit)     grep -q '^bravo' "$target" && ! grep -q 'alpha' "$target" && effect="yes" ;;
      esac
      ;;
  esac

  local verdict="MISMATCH"
  if [ "$expect" = "DENIED" ] && [ "$plugin_fired" = "yes" ] && [ "$effect" = "yes" ]; then
    verdict="DENIED (expected)"
  elif [ "$expect" = "ALLOWED" ] && [ "$plugin_fired" = "no" ] && [ "$effect" = "yes" ]; then
    verdict="ALLOWED (expected)"
  fi
  echo "=== plugin_fired=$plugin_fired effect_ok=$effect ===" >> "$out"
  echo "=== VERDICT: $verdict ===" >> "$out"
  echo "$cell -> $verdict"
}

run_cell patcher-write   hyperresearch-patcher         patcher-write.txt
run_cell patcher-edit    hyperresearch-patcher         patcher-edit.txt
run_cell patcher-bash    hyperresearch-patcher         patcher-bash.txt
run_cell polish-write    hyperresearch-polish-auditor  polish-write.txt
run_cell polish-edit     hyperresearch-polish-auditor  polish-edit.txt
run_cell synth-edit      hyperresearch-synthesizer     synth-edit.txt
run_cell synth-bash      hyperresearch-synthesizer     synth-bash.txt
run_cell synth-write     hyperresearch-synthesizer     synth-write.txt
echo "ALL CELLS DONE"
