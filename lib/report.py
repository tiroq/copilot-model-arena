#!/usr/bin/env python3
"""Generate aggregated benchmark report from audit results."""

import json
import pathlib
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskResult:
    """Result for a single model/task combination."""
    model_id: str
    task_id: str
    judge_id: str
    score: float
    scores_by_category: dict[str, float]
    tests_passed: int
    tests_failed: int
    tests_total: int
    defects: list[dict[str, Any]]
    contamination_status: str
    duration_seconds: float = 0
    
    @property
    def status(self) -> str:
        """Compute status from contamination and test results."""
        if self.contamination_status == "contaminated":
            return "contaminated"
        if self.tests_failed > 0:
            return "incomplete"
        if self.tests_total == 0:
            return "no_tests"
        return "valid"


@dataclass
class ModelSummary:
    """Aggregated summary for a model across all tasks."""
    model_id: str
    valid_tasks: int = 0
    contaminated_tasks: int = 0
    mean_score: float = 0.0
    median_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    mean_duration: float = 0.0
    total_tests: int = 0
    total_defects: int = 0
    scores: list[float] = field(default_factory=list)
    
    def compute_stats(self):
        """Compute statistics from collected scores."""
        if self.scores:
            self.mean_score = statistics.mean(self.scores)
            self.median_score = statistics.median(self.scores)
            self.min_score = min(self.scores)
            self.max_score = max(self.scores)


def load_audit_report(audit_path: pathlib.Path) -> dict[str, Any]:
    """Load a judge's audit report JSON."""
    with open(audit_path) as f:
        return json.load(f)


def load_implementation_metrics(metrics_path: pathlib.Path) -> dict[str, Any]:
    """Load implementation metrics JSON."""
    if not metrics_path.exists():
        return {}
    with open(metrics_path) as f:
        return json.load(f)


def collect_results(results_dir: pathlib.Path, run_id: str) -> tuple[list[TaskResult], dict[str, dict]]:
    """Collect all task results from audit reports.
    
    Returns:
        (task_results, implementation_metrics)
    """
    run_path = results_dir / run_id
    if not run_path.exists():
        return [], {}
    
    task_results = []
    implementation_metrics = {}
    
    # Load all audit reports
    audit_files = list(run_path.glob("audit-*.json"))
    
    for audit_file in audit_files:
        if audit_file.name.startswith("audit-") and audit_file.name.endswith(".json"):
            audit_data = load_audit_report(audit_file)
            judge_id = audit_data.get("judge_id", "unknown")
            
            for result in audit_data.get("results", []):
                model_id = result["model_id"]
                task_id = result["task_id"]
                
                # Load implementation metrics
                metrics_path = run_path / model_id / task_id / "metrics.json"
                metrics = load_implementation_metrics(metrics_path)
                duration = metrics.get("duration_seconds", 0)
                
                # Store implementation metrics
                impl_key = f"{model_id}/{task_id}"
                if impl_key not in implementation_metrics:
                    implementation_metrics[impl_key] = metrics
                
                task_results.append(TaskResult(
                    model_id=model_id,
                    task_id=task_id,
                    judge_id=judge_id,
                    score=result.get("score", 0),
                    scores_by_category=result.get("scores_by_category", {}),
                    tests_passed=result.get("tests_passed", 0),
                    tests_failed=result.get("tests_failed", 0),
                    tests_total=result.get("tests_total", 0),
                    defects=result.get("defects", []),
                    contamination_status=result.get("contamination_status", "unknown"),
                    duration_seconds=duration,
                ))
    
    return task_results, implementation_metrics


def aggregate_by_model_task(results: list[TaskResult]) -> dict[tuple[str, str], list[TaskResult]]:
    """Group results by (model_id, task_id)."""
    grouped = defaultdict(list)
    for result in results:
        grouped[(result.model_id, result.task_id)].append(result)
    return grouped


def compute_model_summaries(results: list[TaskResult]) -> dict[str, ModelSummary]:
    """Compute aggregated summaries for each model."""
    summaries = {}
    
    # Group results by model
    by_model = defaultdict(list)
    for result in results:
        by_model[result.model_id].append(result)
    
    for model_id, model_results in by_model.items():
        summary = ModelSummary(model_id=model_id)
        
        # Group by task to get one score per task (average across judges)
        by_task = defaultdict(list)
        for result in model_results:
            by_task[result.task_id].append(result)
        
        durations = []
        for task_id, task_results in by_task.items():
            # Average score across judges for this task
            task_scores = [r.score for r in task_results]
            avg_score = statistics.mean(task_scores)
            
            # Check if any judge marked it as contaminated
            is_contaminated = any(r.contamination_status == "contaminated" for r in task_results)
            
            if is_contaminated:
                summary.contaminated_tasks += 1
            else:
                summary.valid_tasks += 1
                summary.scores.append(avg_score)
            
            # Collect duration (same for all judges)
            if task_results[0].duration_seconds > 0:
                durations.append(task_results[0].duration_seconds)
            
            # Collect test and defect counts
            summary.total_tests += task_results[0].tests_total
            summary.total_defects += len(task_results[0].defects)
        
        if durations:
            summary.mean_duration = statistics.mean(durations)
        
        summary.compute_stats()
        summaries[model_id] = summary
    
    return summaries


def compute_judge_agreement(results: list[TaskResult]) -> dict[str, Any]:
    """Compute agreement statistics between judges."""
    # Group by (model, task)
    by_model_task = aggregate_by_model_task(results)
    
    variances = []
    max_diffs = []
    
    for (model_id, task_id), task_results in by_model_task.items():
        if len(task_results) >= 2:
            scores = [r.score for r in task_results]
            var = statistics.variance(scores)
            max_diff = max(scores) - min(scores)
            variances.append(var)
            max_diffs.append(max_diff)
    
    return {
        "mean_variance": statistics.mean(variances) if variances else 0,
        "max_variance": max(variances) if variances else 0,
        "mean_diff": statistics.mean(max_diffs) if max_diffs else 0,
        "max_diff": max(max_diffs) if max_diffs else 0,
    }


def generate_markdown_report(
    results: list[TaskResult],
    model_summaries: dict[str, ModelSummary],
    judge_agreement: dict[str, Any],
    run_id: str,
    output_path: pathlib.Path,
):
    """Generate human-readable markdown report."""
    lines = []
    
    lines.append(f"# Benchmark Report")
    lines.append(f"")
    lines.append(f"**Run ID:** {run_id}")
    lines.append(f"**Generated:** {datetime.now().isoformat()}")
    lines.append(f"")
    
    # Executive summary
    lines.append(f"## Executive Summary")
    lines.append(f"")
    lines.append(f"**Models evaluated:** {len(model_summaries)}")
    lines.append(f"**Tasks per model:** {len(set(r.task_id for r in results)) // len(model_summaries) if model_summaries else 0}")
    lines.append(f"**Judges:** {len(set(r.judge_id for r in results))}")
    lines.append(f"")
    
    # Model ranking (contamination-adjusted)
    lines.append(f"## Model Ranking (Valid Tasks Only)")
    lines.append(f"")
    sorted_models = sorted(
        model_summaries.values(),
        key=lambda s: s.mean_score,
        reverse=True,
    )
    
    lines.append("| Rank | Model | Valid Tasks | Mean Score | Median | Duration (s) | Tests | Defects |")
    lines.append("|------|-------|-------------|------------|--------|--------------|-------|---------|")
    
    for rank, summary in enumerate(sorted_models, 1):
        lines.append(
            f"| {rank} | {summary.model_id} | {summary.valid_tasks} | "
            f"{summary.mean_score:.1f} | {summary.median_score:.1f} | "
            f"{summary.mean_duration:.0f} | {summary.total_tests} | {summary.total_defects} |"
        )
    
    lines.append(f"")
    
    # Contamination report
    contaminated = [s for s in model_summaries.values() if s.contaminated_tasks > 0]
    if contaminated:
        lines.append(f"## Contamination Report")
        lines.append(f"")
        lines.append("| Model | Contaminated Tasks | Valid Tasks |")
        lines.append("|-------|--------------------|-------------|")
        for summary in contaminated:
            lines.append(f"| {summary.model_id} | {summary.contaminated_tasks} | {summary.valid_tasks} |")
        lines.append(f"")
    
    # Per-task breakdown
    lines.append(f"## Per-Task Results")
    lines.append(f"")
    
    by_model_task = aggregate_by_model_task(results)
    tasks = sorted(set(r.task_id for r in results))
    
    for task_id in tasks:
        lines.append(f"### Task: {task_id}")
        lines.append(f"")
        lines.append("| Model | Judge 1 | Judge 2 | Mean | Status | Tests |")
        lines.append("|-------|---------|---------|------|--------|-------|")
        
        models = sorted(set(r.model_id for r in results))
        for model_id in models:
            task_results = by_model_task.get((model_id, task_id), [])
            if not task_results:
                continue
            
            scores = [r.score for r in task_results]
            mean_score = statistics.mean(scores)
            status = task_results[0].status
            tests_str = f"{task_results[0].tests_passed}/{task_results[0].tests_total}"
            
            score_strs = [f"{s:.0f}" for s in scores]
            while len(score_strs) < 2:
                score_strs.append("-")
            
            lines.append(
                f"| {model_id} | {score_strs[0]} | {score_strs[1]} | "
                f"{mean_score:.1f} | {status} | {tests_str} |"
            )
        
        lines.append(f"")
    
    # Judge agreement
    lines.append(f"## Judge Agreement")
    lines.append(f"")
    lines.append(f"**Mean score difference:** {judge_agreement['mean_diff']:.1f} points")
    lines.append(f"**Max score difference:** {judge_agreement['max_diff']:.1f} points")
    lines.append(f"**Mean score variance:** {judge_agreement['mean_variance']:.1f}")
    lines.append(f"")
    
    # Limitations
    lines.append(f"## Limitations and Validity")
    lines.append(f"")
    lines.append(f"This benchmark is a controlled engineering comparison, not a scientific evaluation.")
    lines.append(f"")
    lines.append(f"**Limitations:**")
    lines.append(f"- Small sample size (3 tasks)")
    lines.append(f"- Single-run measurements (no statistical significance testing)")
    lines.append(f"- Synthetic tasks (may not represent real-world usage)")
    lines.append(f"- Judge subjectivity (some scoring categories involve interpretation)")
    lines.append(f"- Contamination detection based on log scanning (not foolproof)")
    lines.append(f"")
    lines.append(f"**Validity threats:**")
    lines.append(f"- Tasks may favor certain coding styles or approaches")
    lines.append(f"- Rubric may not perfectly capture all quality dimensions")
    lines.append(f"- Isolation may be incomplete if Copilot CLI has access to system state")
    lines.append(f"- Results are specific to these tasks and prompts")
    lines.append(f"")
    
    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def generate_json_report(
    results: list[TaskResult],
    model_summaries: dict[str, ModelSummary],
    judge_agreement: dict[str, Any],
    run_id: str,
    output_path: pathlib.Path,
):
    """Generate machine-readable JSON report."""
    report = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "model_summaries": {
            model_id: {
                "model_id": summary.model_id,
                "valid_tasks": summary.valid_tasks,
                "contaminated_tasks": summary.contaminated_tasks,
                "mean_score": summary.mean_score,
                "median_score": summary.median_score,
                "min_score": summary.min_score,
                "max_score": summary.max_score,
                "mean_duration": summary.mean_duration,
                "total_tests": summary.total_tests,
                "total_defects": summary.total_defects,
            }
            for model_id, summary in model_summaries.items()
        },
        "judge_agreement": judge_agreement,
        "task_results": [
            {
                "model_id": r.model_id,
                "task_id": r.task_id,
                "judge_id": r.judge_id,
                "score": r.score,
                "status": r.status,
                "tests_passed": r.tests_passed,
                "tests_total": r.tests_total,
                "defects_count": len(r.defects),
                "duration_seconds": r.duration_seconds,
            }
            for r in results
        ],
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")


def main():
    """Generate aggregated report from audit results."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: report.py <results_dir> <run_id> [output_dir]")
        sys.exit(1)
    
    results_dir = pathlib.Path(sys.argv[1])
    run_id = sys.argv[2]
    output_dir = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else results_dir / run_id)
    
    print(f"Generating report for run: {run_id}")
    print(f"Results directory: {results_dir}")
    print(f"Output directory: {output_dir}")
    
    # Collect results
    results, impl_metrics = collect_results(results_dir, run_id)
    
    if not results:
        print("Error: No audit results found")
        sys.exit(1)
    
    print(f"Found {len(results)} task results")
    
    # Compute summaries
    model_summaries = compute_model_summaries(results)
    judge_agreement = compute_judge_agreement(results)
    
    # Generate reports
    markdown_path = output_dir / "benchmark-report.md"
    json_path = output_dir / "benchmark-report.json"
    
    generate_markdown_report(results, model_summaries, judge_agreement, run_id, markdown_path)
    generate_json_report(results, model_summaries, judge_agreement, run_id, json_path)
    
    print(f"✅ Generated reports:")
    print(f"  - {markdown_path}")
    print(f"  - {json_path}")


if __name__ == "__main__":
    main()
