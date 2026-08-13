# Copilot Model Benchmark

A methodologically rigorous benchmark for comparing GitHub Copilot implementation models.

## Overview

This benchmark evaluates models on three programming tasks in isolated workspaces, then uses independent judges to audit the results. The benchmark implements strict isolation, contamination detection, and reproducible scoring to ensure fair comparison.

## Features

- ✅ **Isolated Execution**: Each implementation runs in a fresh temporary workspace
- ✅ **Contamination Detection**: Automatic detection of cross-solution access
- ✅ **Immutable Baseline**: SHA-256 verified seed directory
- ✅ **Independent Judges**: Multiple judges audit with standardized rubric
- ✅ **Comprehensive Metrics**: Duration, test counts, defects, similarity analysis
- ✅ **Reproducible**: Deterministic task order, stable random seeds, versioned manifests

## Quick Start

```bash
# 1. Configure models and judges
cp .env.example .env
# Edit .env to set your IMPLEMENTERS and JUDGES

# 2. Verify baseline
./benchmark.sh verify

# 3. Run implementations
./benchmark.sh run

# 4. Run audits
./benchmark.sh audit

# 5. Generate report
./benchmark.sh report
```

## Requirements

- `copilot` CLI (GitHub Copilot CLI)
- Python 3.11+
- `pytest` for running tests
- `git` (optional, for commit tracking)

## Directory Structure

```
.
├── benchmark.sh              # Main orchestration script
├── lib/                      # Benchmark infrastructure
│   ├── baseline.py          # Baseline manifest generation/verification
│   ├── contamination.py     # Contamination detection
│   └── report.py            # Report generation
├── prompts/                 # Canonical prompts
│   ├── implementation-prompt.md
│   └── audit-prompt.md
├── tasks/                   # Task specifications
│   ├── 01-json-store.md
│   ├── 02-retry.md
│   └── 03-cli.md
├── seed/                    # Immutable baseline project
│   ├── pyproject.toml
│   ├── src/
│   └── tests/
├── results/                 # Execution results (generated)
│   └── <run-id>/
│       ├── <model-id>/
│       │   └── <task-id>/
│       │       ├── source/           # Implementation
│       │       ├── agent.log         # Agent execution log
│       │       ├── metadata.json     # Execution metadata
│       │       ├── metrics.json      # Basic metrics
│       │       ├── contamination.json
│       │       ├── diff.patch
│       │       └── tests.log
│       ├── audit-<judge>.json       # Judge audit (JSON)
│       ├── audit-<judge>.md         # Judge audit (Markdown)
│       ├── benchmark-report.json    # Aggregated report (JSON)
│       └── benchmark-report.md      # Aggregated report (Markdown)
├── tests/                   # Benchmark infrastructure tests
│   └── test_benchmark.py
└── baseline-manifest.json   # Baseline verification manifest
```

## Commands

### Run Implementations

```bash
./benchmark.sh run [options]
```

Runs all configured implementation models on all tasks in isolated workspaces.

**Options:**
- `--run-id ID` - Use specific run ID (default: timestamp)
- `--models "model1,model2"` - Run only specified models
- `--tasks "01-json-store,02-retry"` - Run only specified tasks
- `--keep-workspaces` - Do not delete temporary workspaces
- `--dry-run` - Show what would be done without executing

**Example:**
```bash
./benchmark.sh run --run-id test-001 --models "claude-haiku-4.5"
```

### Run Audits

```bash
./benchmark.sh audit [options]
```

Runs all configured judges to audit implementations.

**Options:**
- `--run-id ID` - Audit specific run (default: most recent)
- `--judges "judge1,judge2"` - Use only specified judges
- `--dry-run` - Show what would be done without executing

**Example:**
```bash
./benchmark.sh audit --run-id test-001
```

### Generate Report

```bash
./benchmark.sh report [options]
```

Generates aggregated benchmark report from audit results.

**Options:**
- `--run-id ID` - Report on specific run (default: most recent)

**Example:**
```bash
./benchmark.sh report --run-id test-001
```

### Verify Baseline

```bash
./benchmark.sh verify
```

Verifies that the seed directory matches the baseline manifest.

## Configuration

Edit `.env` to configure models and judges:

```bash
IMPLEMENTERS="mai-code-1.1-flash,claude-haiku-4.5"
JUDGES="claude-sonnet-4.5,gpt-5.5"
TIMEOUT_SECONDS=7200
```

## Tasks

### Task 01: JSON Store

Implement an append-only JSONL key-value store with:
- `put(key, value)` - Store a value
- `get(key, default=MISSING)` - Retrieve a value
- `list(prefix="")` - List key-value pairs

**Acceptance Criteria:**
- True append-only semantics (no file rewrite)
- Returns (key, value) tuples from `list()`
- Distinguishes stored `None` from missing key
- Corruption-tolerant reads

### Task 02: Async Retry Decorator

Implement an async retry decorator with:
- Exponential backoff
- Configurable jitter
- Exception filtering
- Cancellation propagation

**Acceptance Criteria:**
- Exact retry count semantics
- Proper CancelledError propagation
- Argument validation
- Type-safe with ParamSpec

### Task 03: CLI for JSON Store

Implement a command-line interface with:
- `put <key> <value>` - Store value
- `get <key> [--default VALUE]` - Retrieve value
- `list [--prefix PREFIX]` - List keys

**Acceptance Criteria:**
- Stable JSON output (sorted keys)
- Correct exit codes (0=success, 2=not found)
- JSON value parsing
- Subprocess integration tests

## Scoring Rubric

100-point rubric applied by all judges:

| Category | Points | Description |
|----------|--------|-------------|
| Functional Correctness | 35 | Works correctly for typical inputs |
| Acceptance Criteria | 20 | Meets all specification requirements |
| Test Quality | 15 | Comprehensive, passing tests |
| Robustness | 10 | Edge case handling, error handling |
| Scope Discipline | 10 | Clean code, no scope creep |
| CLI/Integration | 5 | Correct CLI behavior (if applicable) |
| Documentation | 5 | Clear documentation and summary |

## Isolation and Contamination Detection

### Isolation

Each implementation runs in a fresh temporary workspace created from the verified seed:

1. Baseline manifest is verified before execution
2. Temporary workspace is created from seed
3. Implementation agent sees only:
   - Task specification
   - Isolated workspace directory
4. Implementation agent cannot access:
   - `results/` directory
   - Other model solutions
   - Other task workspaces
   - Benchmark infrastructure

### Contamination Detection

After each implementation, the system:

1. Scans agent log for forbidden patterns:
   - References to `results/`
   - Other model IDs
   - Other task IDs
2. Compares implementations for suspicious similarity:
   - Byte-for-byte identical files
   - High normalized similarity (>95%)
3. Marks contaminated results explicitly
4. Excludes contaminated results from primary ranking

## Reproducibility

The benchmark ensures reproducibility through:

- **Immutable Baseline**: SHA-256 verified seed directory
- **Deterministic Order**: Tasks and models processed in sorted order
- **Versioned Prompts**: Canonical prompts versioned with benchmark
- **Comprehensive Logging**: All execution captured in logs
- **Metadata Recording**: Timestamps, versions, commit SHAs

## Limitations

This benchmark is a **controlled engineering comparison**, not a scientific evaluation.

**Limitations:**
- Small sample size (3 tasks)
- Single-run measurements (no statistical significance testing)
- Synthetic tasks (may not represent real-world usage)
- Judge subjectivity (some scoring involves interpretation)

**Validity Threats:**
- Tasks may favor certain coding styles
- Rubric may not capture all quality dimensions
- Isolation may be incomplete if Copilot CLI has system access
- Results are specific to these tasks and prompts

## Testing the Benchmark

Run benchmark infrastructure tests:

```bash
pytest tests/test_benchmark.py -v
```

## Development

### Adding a New Task

1. Create task specification in `tasks/XX-task-name.md`
2. Define exact API, behavior, and acceptance criteria
3. Specify required tests
4. Document scope restrictions
5. Update baseline manifest if seed changes

### Modifying the Rubric

The rubric is defined in `prompts/audit-prompt.md`. Changes affect all future audits but not past results.

### Extending Detection

Contamination detection rules are in `lib/contamination.py`. Add patterns to `scan_log_for_references()` to detect new contamination vectors.

## License

This benchmark is provided as-is for evaluation purposes.

## Contributing

Contributions are welcome! Please ensure:

- All tests pass: `pytest tests/ -v`
- Baseline verification passes: `./benchmark.sh verify`
- Dry-run succeeds: `./benchmark.sh run --dry-run`
- Documentation is updated

## Contact

For questions or issues, please open a GitHub issue.
