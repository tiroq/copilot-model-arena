#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || source .env.example
root=$(cd "$(dirname "$0")" && pwd); mkdir -p "$root/results"
run(){ IFS=, read -ra ms <<< "$IMPLEMENTERS"; for m in "${ms[@]}"; do for t in "$root"/tasks/*.md; do id=$(basename "$t" .md); dir="$root/results/${m// /_}/$id"; mkdir -p "$dir"; cp -R "$root/seed/." "$dir/"; start=$(date +%s); copilot --model "$m" --yolo "Read $t. Implement only in this directory. Run tests. Write SUMMARY.md with commands and results." >"$dir/agent.log" 2>&1 || true; end=$(date +%s); printf '{"model":"%s","task":"%s","seconds":%s}\n' "$m" "$id" "$((end-start))" >"$dir/metrics.json"; done; done; }
audit(){ IFS=, read -ra js <<< "$JUDGES"; for j in "${js[@]}"; do copilot --model "$j" --yolo "Independently audit all implementations under results. For each task/model inspect diff and run tests. Write results/audit-${j// /_}.md with 0-100 score, correctness, tests, scope, defects, evidence. Do not modify solutions."; done; }
case "${1:-}" in run) run;; audit) audit;; *) echo 'run|audit'; exit 2;; esac
