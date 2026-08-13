#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RESULTS_DIR="$ROOT_DIR/results"
SEED_DIR="$ROOT_DIR/seed"
TASKS_DIR="$ROOT_DIR/tasks"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"

usage() {
  cat <<'EOF'
Usage: ./benchmark.sh {run|audit}

  run   Run all configured implementers against every task in isolated copies.
  audit Audit all generated results with the configured judges.
EOF
}

trim() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  elif [[ -f "$ENV_EXAMPLE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_EXAMPLE"
  fi
}

split_csv() {
  local raw="${1:-}"

  if [[ -z "${raw//[[:space:]]/}" ]]; then
    return 0
  fi

  local -a items=()
  IFS=',' read -r -a items <<< "$raw"
  local item
  for item in "${items[@]}"; do
    item=$(trim "$item")
    if [[ -n "$item" ]]; then
      printf '%s\n' "$item"
    fi
  done
}

ensure_requirements() {
  if ! command -v copilot >/dev/null 2>&1; then
    echo "Error: 'copilot' is not installed or not on PATH." >&2
    exit 1
  fi
}

prepare_run_dir() {
  local model="$1"
  local task_id="$2"
  local dir="$RESULTS_DIR/${model// /_}/$task_id"

  rm -rf "$dir"
  mkdir -p "$dir"
  cp -R "$SEED_DIR/." "$dir/"

  printf '%s\n' "$dir"
}

run_model_task() {
  local model="$1"
  local task_file="$2"
  local task_id
  task_id=$(basename "$task_file" .md)
  local dir
  dir=$(prepare_run_dir "$model" "$task_id")

  local start end
  start=$(date +%s)

  copilot --model "$model" --yolo "Read $task_file. Implement only in this directory. Run tests. Write SUMMARY.md with commands and results." >"$dir/agent.log" 2>&1 || true

  end=$(date +%s)
  printf '{"model":"%s","task":"%s","seconds":%s}\n' "$model" "$task_id" "$((end-start))" >"$dir/metrics.json"
}

run() {
  load_env
  ensure_requirements

  local models=()
  while IFS= read -r model; do
    models+=("$model")
  done < <(split_csv "${IMPLEMENTERS:-}")

  if (( ${#models[@]} == 0 )); then
    echo "Error: IMPLEMENTERS is not set or empty. Update .env or .env.example." >&2
    exit 1
  fi

  local tasks=("$TASKS_DIR"/*.md)
  if [[ ! -e "${tasks[0]}" ]]; then
    echo "Error: no task files found in $TASKS_DIR" >&2
    exit 1
  fi

  mkdir -p "$RESULTS_DIR"

  local model task_file
  for model in "${models[@]}"; do
    for task_file in "${tasks[@]}"; do
      run_model_task "$model" "$task_file"
    done
  done
}

audit() {
  load_env
  ensure_requirements

  local judges=()
  while IFS= read -r judge; do
    judges+=("$judge")
  done < <(split_csv "${JUDGES:-}")

  if (( ${#judges[@]} == 0 )); then
    echo "Error: JUDGES is not set or empty. Update .env or .env.example." >&2
    exit 1
  fi

  local judge
  for judge in "${judges[@]}"; do
    copilot --model "$judge" --yolo "Independently audit all implementations under results. For each task/model inspect diff and run tests. Write results/audit-${judge// /_}.md with 0-100 score, correctness, tests, scope, defects, evidence. Do not modify solutions."
  done
}

case "${1:-}" in
  run)
    run
    ;;
  audit)
    audit
    ;;
  -h|--help|help)
    usage
    ;;
  "")
    usage >&2
    exit 2
    ;;
  *)
    usage >&2
    exit 2
    ;;
 esac
