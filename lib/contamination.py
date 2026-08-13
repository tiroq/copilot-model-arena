#!/usr/bin/env python3
"""Contamination detection for benchmark isolation verification."""

import difflib
import hashlib
import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ContaminationEvidence:
    """Evidence of potential contamination."""
    type: str  # "log_reference", "file_hash", "similarity", "path_access"
    severity: str  # "definite", "high", "medium", "low"
    description: str
    details: dict[str, Any]


@dataclass
class ContaminationReport:
    """Complete contamination analysis for a single run."""
    run_id: str
    model_id: str
    task_id: str
    is_contaminated: bool
    evidence: list[ContaminationEvidence]
    allowed_paths: list[str]
    accessed_paths: list[str]
    created_files: list[str]
    modified_files: list[str]


def sanitize_model_id(model_id: str) -> str:
    """Sanitize model ID for use in directory names."""
    # Replace spaces with underscores, remove special characters
    sanitized = re.sub(r"[^\w\-.]", "_", model_id)
    sanitized = re.sub(r"_+", "_", sanitized)  # Collapse multiple underscores
    return sanitized.strip("_")


def compute_file_hash(path: pathlib.Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def normalize_source(content: str) -> str:
    """Normalize source code for similarity comparison.
    
    Removes comments, collapses whitespace, normalizes formatting.
    """
    # Remove single-line comments
    content = re.sub(r"#.*$", "", content, flags=re.MULTILINE)
    # Remove docstrings
    content = re.sub(r'""".*?"""', "", content, flags=re.DOTALL)
    content = re.sub(r"'''.*?'''", "", content, flags=re.DOTALL)
    # Collapse whitespace
    content = re.sub(r"\s+", " ", content)
    # Remove leading/trailing whitespace
    content = content.strip()
    return content


def compute_similarity(file1: pathlib.Path, file2: pathlib.Path) -> float:
    """Compute similarity ratio between two files (0.0 to 1.0).
    
    Uses normalized content (comments/whitespace removed).
    """
    if not file1.exists() or not file2.exists():
        return 0.0
    
    content1 = file1.read_text(errors="ignore")
    content2 = file2.read_text(errors="ignore")
    
    norm1 = normalize_source(content1)
    norm2 = normalize_source(content2)
    
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def scan_log_for_references(
    log_path: pathlib.Path,
    forbidden_patterns: list[str],
) -> list[ContaminationEvidence]:
    """Scan agent log for references to forbidden paths or patterns.
    
    Args:
        log_path: Path to agent log file
        forbidden_patterns: List of regex patterns that should not appear
        
    Returns:
        List of contamination evidence found
    """
    if not log_path.exists():
        return []
    
    evidence = []
    content = log_path.read_text(errors="ignore")
    
    for pattern in forbidden_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Get line number
            line_num = content[:match.start()].count("\n") + 1
            # Get context (50 chars before and after)
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end].replace("\n", " ")
            
            evidence.append(ContaminationEvidence(
                type="log_reference",
                severity="high",
                description=f"Log references forbidden pattern: {pattern}",
                details={
                    "pattern": pattern,
                    "line": line_num,
                    "match": match.group(0),
                    "context": context,
                },
            ))
    
    return evidence


def compare_implementations(
    results_dir: pathlib.Path,
    run_id: str,
    task_id: str,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Compare all implementations of a task to detect suspicious similarity.
    
    Returns list of (model1, model2, comparison_data) tuples for suspicious pairs.
    """
    suspicious = []
    
    task_results = []
    run_path = results_dir / run_id
    if not run_path.exists():
        return suspicious
    
    # Find all model results for this task
    for model_dir in run_path.iterdir():
        if not model_dir.is_dir():
            continue
        task_path = model_dir / task_id / "source"
        if task_path.exists():
            task_results.append((model_dir.name, task_path))
    
    # Compare each pair
    for i, (model1, path1) in enumerate(task_results):
        for model2, path2 in task_results[i + 1:]:
            comparison = compare_implementations_pair(path1, path2)
            
            # Flag if any file is identical or highly similar
            if comparison["max_similarity"] > 0.95 or comparison["identical_files"] > 0:
                suspicious.append((model1, model2, comparison))
    
    return suspicious


def compare_implementations_pair(
    impl1_dir: pathlib.Path,
    impl2_dir: pathlib.Path,
) -> dict[str, Any]:
    """Compare two implementation directories for similarity.
    
    Returns comparison statistics including similarity ratios and identical files.
    """
    result = {
        "identical_files": 0,
        "similar_files": 0,
        "max_similarity": 0.0,
        "avg_similarity": 0.0,
        "file_comparisons": [],
    }
    
    # Get all source files from both implementations
    files1 = {f.relative_to(impl1_dir): f for f in impl1_dir.rglob("*.py")}
    files2 = {f.relative_to(impl2_dir): f for f in impl2_dir.rglob("*.py")}
    
    # Compare files with same relative path
    common_files = set(files1.keys()) & set(files2.keys())
    
    similarities = []
    for rel_path in common_files:
        file1 = files1[rel_path]
        file2 = files2[rel_path]
        
        # Byte-for-byte comparison
        hash1 = compute_file_hash(file1)
        hash2 = compute_file_hash(file2)
        is_identical = hash1 == hash2
        
        # Similarity comparison
        similarity = compute_similarity(file1, file2)
        similarities.append(similarity)
        
        if is_identical:
            result["identical_files"] += 1
        elif similarity > 0.85:
            result["similar_files"] += 1
        
        result["file_comparisons"].append({
            "path": str(rel_path),
            "identical": is_identical,
            "similarity": similarity,
            "hash1": hash1[:16],
            "hash2": hash2[:16],
        })
    
    if similarities:
        result["max_similarity"] = max(similarities)
        result["avg_similarity"] = sum(similarities) / len(similarities)
    
    return result


def detect_contamination(
    run_id: str,
    model_id: str,
    task_id: str,
    result_dir: pathlib.Path,
    allowed_workspace: pathlib.Path,
    results_base: pathlib.Path,
) -> ContaminationReport:
    """Detect contamination for a single implementation run.
    
    Args:
        run_id: Unique run identifier
        model_id: Model that performed the implementation
        task_id: Task that was implemented
        result_dir: Directory containing this specific result
        allowed_workspace: The isolated workspace path that was allowed
        results_base: Base results directory (should never be accessed)
        
    Returns:
        ContaminationReport with evidence
    """
    evidence = []
    
    # Check for log file
    log_path = result_dir / "agent.log"
    
    # Build forbidden patterns
    forbidden_patterns = [
        r"results/",  # Any reference to results directory
        r"results\\",  # Windows-style
    ]
    
    # Add other model IDs to forbidden patterns
    # (We'd need to pass these in, but for now use a heuristic)
    other_model_patterns = [
        r"claude[-_]haiku",
        r"claude[-_]sonnet",
        r"gpt[-_]\d",
        r"mai[-_]code",
    ]
    forbidden_patterns.extend(other_model_patterns)
    
    # Add other task IDs
    forbidden_patterns.extend([
        r"\d{2}[-_]json[-_]store",
        r"\d{2}[-_]retry",
        r"\d{2}[-_]cli",
    ])
    
    # Scan log for forbidden references
    if log_path.exists():
        log_evidence = scan_log_for_references(log_path, forbidden_patterns)
        evidence.extend(log_evidence)
    
    # Check if agent accessed paths outside allowed workspace
    # (This would require more detailed logging of file access)
    # For now, we rely on log scanning
    
    # Get list of created/modified files
    source_dir = result_dir / "source"
    created_files = []
    modified_files = []
    
    if source_dir.exists():
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(source_dir))
                # All files in a fresh workspace are "created"
                created_files.append(rel_path)
    
    # Determine contamination status
    is_contaminated = len(evidence) > 0
    
    return ContaminationReport(
        run_id=run_id,
        model_id=model_id,
        task_id=task_id,
        is_contaminated=is_contaminated,
        evidence=evidence,
        allowed_paths=[str(allowed_workspace)],
        accessed_paths=[],  # Would need detailed file access logging
        created_files=created_files,
        modified_files=modified_files,
    )


def save_contamination_report(report: ContaminationReport, output_path: pathlib.Path) -> None:
    """Save contamination report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(report), f, indent=2, sort_keys=True)
        f.write("\n")


def load_contamination_report(report_path: pathlib.Path) -> ContaminationReport:
    """Load contamination report from JSON file."""
    with open(report_path) as f:
        data = json.load(f)
    
    # Convert evidence dicts to ContaminationEvidence objects
    evidence = [ContaminationEvidence(**e) for e in data.get("evidence", [])]
    data["evidence"] = evidence
    
    return ContaminationReport(**data)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: contamination.py {sanitize|scan_log|compare} <args>")
        print("  sanitize <model_id>")
        print("  scan_log <log_path> <pattern1> [pattern2...]")
        print("  compare <results_dir> <run_id> <task_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "sanitize":
        model_id = sys.argv[2]
        print(sanitize_model_id(model_id))
    elif command == "scan_log":
        log_path = pathlib.Path(sys.argv[2])
        patterns = sys.argv[3:]
        evidence = scan_log_for_references(log_path, patterns)
        print(json.dumps([asdict(e) for e in evidence], indent=2))
    elif command == "compare":
        results_dir = pathlib.Path(sys.argv[2])
        run_id = sys.argv[3]
        task_id = sys.argv[4]
        suspicious = compare_implementations(results_dir, run_id, task_id)
        print(json.dumps(suspicious, indent=2))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
