#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RESULTS_DIR="$ROOT_DIR/results"
SEED_DIR="$ROOT_DIR/seed"
TASKS_DIR="$ROOT_DIR/tasks"
PROMPTS_DIR="$ROOT_DIR/prompts"
LIB_DIR="$ROOT_DIR/lib"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
BASELINE_MANIFEST="$ROOT_DIR/baseline-manifest.json"

# Default configuration
DRY_RUN=false
RUN_ID=""
MODELS_FILTER=""
JUDGES_FILTER=""
TASKS_FILTER=""
KEEP_WORKSPACES=false
ALLOW_NETWORK=false
RERUN_CONTAMINATED=false
AUDIT_ONLY=false
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-7200}"

usage() {
  cat <<'EOF'
Usage: ./benchmark.sh {run|audit|report|verify} [options]

Commands:
  run      Run implementations for all models and tasks
  audit    Audit all implementations with configured judges
  report   Generate aggregated benchmark report
  verify   Verify baseline manifest matches seed directory

Options:
  --dry-run              Show what would be done without executing
  --run-id ID            Use specific run ID (default: timestamp)
  --models MODEL1,MODEL2 Run only specified models
  --judges JUDGE1,JUDGE2 Use only specified judges
  --tasks TASK1,TASK2    Run only specified tasks
  --keep-workspaces      Do not delete temporary workspaces
  --allow-network        Allow network access (disabled by default)
  --rerun-contaminated   Re-run contaminated implementations
  --audit-only           Only run audits (skip implementations)
  -h, --help             Show this help message

Examples:
  ./benchmark.sh run
  ./benchmark.sh run --run-id test-001 --models "claude-haiku-4.5"
  ./benchmark.sh audit --run-id test-001
  ./benchmark.sh report --run-id test-001
  ./benchmark.sh verify

Environment variables (set in .env):
  IMPLEMENTERS     Comma-separated list of implementation models
  JUDGES           Comma-separated list of judge models
  TIMEOUT_SECONDS  Timeout for each implementation (default: 7200)
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
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: 'python3' is not installed or not on PATH." >&2
    exit 1
  fi
  if ! command -v pytest >/dev/null 2>&1; then
    echo "Warning: 'pytest' is not on PATH. Tests may fail." >&2
  fi
}

generate_run_id() {
  date +%Y%m%d-%H%M%S
}

sanitize_model_id() {
  local model="$1"
  python3 "$LIB_DIR/contamination.py" sanitize "$model"
}

verify_baseline() {
  echo "=== Verifying baseline manifest ==="
  
  if [[ ! -f "$BASELINE_MANIFEST" ]]; then
    echo "Baseline manifest not found. Generating..."
    python3 "$LIB_DIR/baseline.py" generate "$SEED_DIR" "$BASELINE_MANIFEST"
  fi
  
  python3 "$LIB_DIR/baseline.py" verify "$SEED_DIR" "$BASELINE_MANIFEST"
  local exit_code=$?
  
  if (( exit_code != 0 )); then
    echo "Error: Baseline verification failed. Seed directory has changed." >&2
    echo "Run: python3 lib/baseline.py generate seed baseline-manifest.json" >&2
    exit 1
  fi
  
  echo "✅ Baseline verified"
}

create_isolated_workspace() {
  local run_id="$1"
  local model_id="$2"
  local task_id="$3"
  
  # Create temporary isolated workspace
  local workspace
  workspace=$(mktemp -d "/tmp/benchmark-${run_id}-${model_id}-${task_id}.XXXXXX")
  
  # Copy seed to workspace
  cp -R "$SEED_DIR/." "$workspace/"
  
  echo "$workspace"
}

prepare_result_dir() {
  local run_id="$1"
  local model_id="$2"
  local task_id="$3"
  
  local safe_model
  safe_model=$(sanitize_model_id "$model_id")
  local result_dir="$RESULTS_DIR/$run_id/$safe_model/$task_id"
  
  mkdir -p "$result_dir"
  
  echo "$result_dir"
}

run_model_task() {
  local run_id="$1"
  local model="$2"
  local task_file="$3"
  local task_id
  task_id=$(basename "$task_file" .md)
  
  echo "\n=== Running ${model} on ${task_id} (run: ${run_id}) ==="
  
  # Create isolated workspace
  local workspace
  workspace=$(create_isolated_workspace "$run_id" "$model" "$task_id")
  echo "Isolated workspace: $workspace"
  
  # Prepare result directory
  local result_dir
  result_dir=$(prepare_result_dir "$run_id" "$model" "$task_id")
  echo "Result directory: $result_dir"
  
  # Build implementation prompt
  local task_file_abs="$TASKS_DIR/$task_id.md"
  local prompt
  prompt="You are implementing a task in an isolated workspace.

Read the task specification: $task_file_abs

Implement the requested feature according to the specification.
Add comprehensive tests in tests/.
Run tests: pytest tests/ -v
Create implementation-summary.md with:
  - Commands you ran
  - Test results
  - Implementation notes

CRITICAL RESTRICTIONS:
- Work only in this directory
- Do not access results/ or other model solutions
- Do not modify files outside task scope
- Do not use network access
- Implement exactly what is specified

Begin implementation."

  # Record metadata
  local start_time end_time duration copilot_exit
  start_time=$(date +%s)
  local start_iso
  start_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  
  # Run copilot in isolated workspace
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would execute:"
    echo "  cd $workspace"
    echo "  timeout ${TIMEOUT_SECONDS}s copilot --model \"$model\" --allow-all --no-ask-user --prompt \"...\""
    copilot_exit=0
    duration=0
  else
    set +e
    (cd "$workspace" && timeout "${TIMEOUT_SECONDS}s" copilot --model "$model" --allow-all --no-ask-user --prompt "$prompt") 2>&1 | tee "$result_dir/agent.log"
    copilot_exit=${PIPESTATUS[0]}
    set -e
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    # Copy implementation to result directory
    mkdir -p "$result_dir/source"
    cp -R "$workspace/." "$result_dir/source/"
    
    # Generate diff
    diff -Nur "$SEED_DIR" "$result_dir/source" > "$result_dir/diff.patch" || true
    
    # Run tests and capture output
    if [[ -d "$result_dir/source/tests" ]]; then
      (cd "$result_dir/source" && pytest tests/ -v || true) 2>&1 | tee "$result_dir/tests.log"
    fi
    
    # Clean up workspace unless --keep-workspaces
    if [[ "$KEEP_WORKSPACES" == "false" ]]; then
      rm -rf "$workspace"
    else
      echo "Kept workspace: $workspace"
    fi
  fi
  
  # Record metrics
  local end_iso
  end_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local git_commit
  git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
  
  cat > "$result_dir/metadata.json" <<EOF
{
  "run_id": "$run_id",
  "model_id": "$model",
  "task_id": "$task_id",
  "start_time": "$start_iso",
  "end_time": "$end_iso",
  "duration_seconds": $duration,
  "copilot_exit_code": $copilot_exit,
  "benchmark_commit": "$git_commit",
  "isolated_workspace": "$workspace",
  "python_version": "$(python3 --version 2>&1)",
  "hostname": "$(hostname)"
}
EOF
  
  # Compute basic metrics
  local lines_added=0 lines_removed=0 files_changed=0
  if [[ -f "$result_dir/diff.patch" ]]; then
    lines_added=$(grep -c '^+' "$result_dir/diff.patch" || echo 0)
    lines_removed=$(grep -c '^-' "$result_dir/diff.patch" || echo 0)
    files_changed=$(grep -c '^diff' "$result_dir/diff.patch" || echo 0)
  fi
  
  cat > "$result_dir/metrics.json" <<EOF
{
  "model_id": "$model",
  "task_id": "$task_id",
  "duration_seconds": $duration,
  "copilot_exit_code": $copilot_exit,
  "lines_added": $lines_added,
  "lines_removed": $lines_removed,
  "files_changed": $files_changed
}
EOF
  
  # Detect contamination
  python3 "$LIB_DIR/contamination.py" detect \
    "$run_id" "$model" "$task_id" \
    "$result_dir" "$workspace" "$RESULTS_DIR" \
    > "$result_dir/contamination.json" || true
  
  echo "Copilot exit code: $copilot_exit"
  if (( copilot_exit != 0 )); then
    echo "Warning: Copilot exited with non-zero status"
  fi
  echo "=== Completed ${model} on ${task_id} in ${duration}s ==="
}

run() {
  load_env
  ensure_requirements
  verify_baseline
  
  # Generate run ID
  if [[ -z "$RUN_ID" ]]; then
    RUN_ID=$(generate_run_id)
  fi
  echo "Run ID: $RUN_ID"
  
  # Get models to run
  local models=()
  local models_source="${MODELS_FILTER:-$IMPLEMENTERS}"
  while IFS= read -r model; do
    models+=("$model")
  done < <(split_csv "$models_source")
  
  if (( ${#models[@]} == 0 )); then
    echo "Error: No models specified. Set IMPLEMENTERS in .env or use --models" >&2
    exit 1
  fi
  
  echo "Models: ${models[*]}"
  
  # Get tasks to run
  local tasks=()
  if [[ -n "$TASKS_FILTER" ]]; then
    while IFS= read -r task; do
      tasks+=("$TASKS_DIR/${task}.md")
    done < <(split_csv "$TASKS_FILTER")
  else
    tasks=("$TASKS_DIR"/*.md)
  fi
  
  if [[ ! -e "${tasks[0]}" ]]; then
    echo "Error: No task files found" >&2
    exit 1
  fi
  
  echo "Tasks: ${#tasks[@]}"
  
  # Create run directory
  mkdir -p "$RESULTS_DIR/$RUN_ID"
  
  # Run each model on each task
  local model task_file
  for model in "${models[@]}"; do
    for task_file in "${tasks[@]}"; do
      run_model_task "$RUN_ID" "$model" "$task_file"
    done
  done
  
  echo "\n✅ Implementation phase complete"
  echo "Run ID: $RUN_ID"
  echo "Results: $RESULTS_DIR/$RUN_ID"
}

run_judge_audit() {
  local run_id="$1"
  local judge="$2"
  
  local safe_judge
  safe_judge=$(sanitize_model_id "$judge")
  local audit_json="$RESULTS_DIR/$run_id/audit-${safe_judge}.json"
  local audit_md="$RESULTS_DIR/$run_id/audit-${safe_judge}.md"
  local audit_log="$RESULTS_DIR/$run_id/audit-${safe_judge}.log"
  
  echo "\n=== Auditing with ${judge} (run: ${run_id}) ==="
  
  # Build audit prompt
  local prompt
  prompt="You are an independent judge auditing implementations from a benchmark.

Read the audit instructions: $PROMPTS_DIR/audit-prompt.md

You will audit implementations in: $RESULTS_DIR/$run_id/

For each model and task:
1. Read the task specification in tasks/
2. Inspect the implementation in results/$run_id/{model}/{task}/source/
3. Run tests: cd results/$run_id/{model}/{task}/source && pytest tests/ -v
4. Review the diff: diff.patch
5. Apply the 100-point rubric
6. Document defects with evidence

Create two reports:
1. $audit_json - Machine-readable JSON with scores and evidence
2. $audit_md - Human-readable markdown report

Follow the exact rubric and output schema from the audit prompt.

CRITICAL: Do not modify any implementation code. Audit only.

Begin audit."

  local start_time end_time duration copilot_exit
  start_time=$(date +%s)
  
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would execute audit with $judge"
    copilot_exit=0
    duration=0
  else
    set +e
    (cd "$ROOT_DIR" && copilot --model "$judge" --allow-all --no-ask-user --prompt "$prompt") 2>&1 | tee "$audit_log"
    copilot_exit=${PIPESTATUS[0]}
    set -e
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
  fi
  
  # Record audit metrics
  cat > "$RESULTS_DIR/$run_id/audit-${safe_judge}-metrics.json" <<EOF
{
  "judge_id": "$judge",
  "run_id": "$run_id",
  "duration_seconds": $duration,
  "exit_code": $copilot_exit,
  "audit_json": "$audit_json",
  "audit_md": "$audit_md",
  "audit_log": "$audit_log"
}
EOF
  
  echo "Audit exit code: $copilot_exit"
  if (( copilot_exit != 0 )); then
    echo "Warning: Audit exited with non-zero status"
  fi
  echo "=== Completed audit with ${judge} in ${duration}s ==="
}

audit() {
  load_env
  ensure_requirements
  
  # Get run ID
  if [[ -z "$RUN_ID" ]]; then
    # Find most recent run
    RUN_ID=$(ls -t "$RESULTS_DIR" | head -n 1)
    if [[ -z "$RUN_ID" ]]; then
      echo "Error: No runs found. Use --run-id or run implementations first." >&2
      exit 1
    fi
    echo "Using most recent run: $RUN_ID"
  fi
  
  # Get judges
  local judges=()
  local judges_source="${JUDGES_FILTER:-$JUDGES}"
  while IFS= read -r judge; do
    judges+=("$judge")
  done < <(split_csv "$judges_source")
  
  if (( ${#judges[@]} == 0 )); then
    echo "Error: No judges specified. Set JUDGES in .env or use --judges" >&2
    exit 1
  fi
  
  echo "Judges: ${judges[*]}"
  
  # Run each judge
  local judge
  for judge in "${judges[@]}"; do
    run_judge_audit "$RUN_ID" "$judge"
  done
  
  echo "\n✅ Audit phase complete"
  echo "Run ID: $RUN_ID"
  echo "Audits: $RESULTS_DIR/$RUN_ID/audit-*.json"
}

report() {
  load_env
  
  # Get run ID
  if [[ -z "$RUN_ID" ]]; then
    RUN_ID=$(ls -t "$RESULTS_DIR" | head -n 1)
    if [[ -z "$RUN_ID" ]]; then
      echo "Error: No runs found. Use --run-id or run implementations first." >&2
      exit 1
    fi
    echo "Using most recent run: $RUN_ID"
  fi
  
  echo "=== Generating report for run: $RUN_ID ==="
  
  python3 "$LIB_DIR/report.py" "$RESULTS_DIR" "$RUN_ID"
  
  echo "\n✅ Report generated"
  echo "Markdown: $RESULTS_DIR/$RUN_ID/benchmark-report.md"
  echo "JSON: $RESULTS_DIR/$RUN_ID/benchmark-report.json"
}

verify() {
  load_env
  verify_baseline
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --run-id)
        RUN_ID="$2"
        shift 2
        ;;
      --models)
        MODELS_FILTER="$2"
        shift 2
        ;;
      --judges)
        JUDGES_FILTER="$2"
        shift 2
        ;;
      --tasks)
        TASKS_FILTER="$2"
        shift 2
        ;;
      --keep-workspaces)
        KEEP_WORKSPACES=true
        shift
        ;;
      --allow-network)
        ALLOW_NETWORK=true
        shift
        ;;
      --rerun-contaminated)
        RERUN_CONTAMINATED=true
        shift
        ;;
      --audit-only)
        AUDIT_ONLY=true
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        # Assume it's a command
        break
        ;;
    esac
  done
}

main() {
  local command="${1:-}"
  shift || true
  
  parse_args "$@"
  
  case "$command" in
    run)
      run
      ;;
    audit)
      audit
      ;;
    report)
      report
      ;;
    verify)
      verify
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      echo "Error: Unknown command: $command" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
    usage >&2
    exit 2
    ;;
  *)
    usage >&2
    exit 2
    ;;
 esac
