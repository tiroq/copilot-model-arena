#!/usr/bin/env python3
"""Baseline manifest generation and validation for benchmark isolation."""

import hashlib
import json
import pathlib
import subprocess
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class FileManifest:
    """Manifest entry for a single file."""
    path: str
    size: int
    sha256: str


@dataclass
class BaselineManifest:
    """Complete baseline manifest for the seed directory."""
    version: str = "1.0"
    benchmark_commit: str | None = None
    seed_dir: str = ""
    files: list[FileManifest] = None
    total_files: int = 0
    total_bytes: int = 0
    manifest_sha256: str = ""

    def __post_init__(self):
        if self.files is None:
            self.files = []


def compute_file_hash(path: pathlib.Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_git_commit() -> str | None:
    """Get current git commit SHA, if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def generate_manifest(seed_dir: pathlib.Path) -> BaselineManifest:
    """Generate a complete baseline manifest for the seed directory.
    
    Args:
        seed_dir: Path to the seed directory
        
    Returns:
        BaselineManifest with all files cataloged
        
    Raises:
        FileNotFoundError: If seed_dir does not exist
        ValueError: If seed_dir is not a directory
    """
    if not seed_dir.exists():
        raise FileNotFoundError(f"Seed directory not found: {seed_dir}")
    if not seed_dir.is_dir():
        raise ValueError(f"Seed path is not a directory: {seed_dir}")

    manifest = BaselineManifest(
        seed_dir=str(seed_dir.resolve()),
        benchmark_commit=get_git_commit(),
    )

    # Walk all files in seed directory
    files = []
    total_bytes = 0
    
    for file_path in sorted(seed_dir.rglob("*")):
        if file_path.is_file():
            rel_path = file_path.relative_to(seed_dir)
            size = file_path.stat().st_size
            sha256 = compute_file_hash(file_path)
            
            files.append(FileManifest(
                path=str(rel_path),
                size=size,
                sha256=sha256,
            ))
            total_bytes += size

    manifest.files = files
    manifest.total_files = len(files)
    manifest.total_bytes = total_bytes
    
    # Compute manifest hash (hash of canonical JSON)
    manifest_json = json.dumps(
        {
            "version": manifest.version,
            "seed_dir": manifest.seed_dir,
            "files": [asdict(f) for f in manifest.files],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest.manifest_sha256 = hashlib.sha256(manifest_json.encode()).hexdigest()
    
    return manifest


def verify_manifest(seed_dir: pathlib.Path, manifest: BaselineManifest) -> tuple[bool, list[str]]:
    """Verify that seed directory matches the manifest.
    
    Args:
        seed_dir: Path to the seed directory to verify
        manifest: Expected baseline manifest
        
    Returns:
        (is_valid, errors) where errors is a list of discrepancy descriptions
    """
    errors = []
    
    if not seed_dir.exists():
        errors.append(f"Seed directory does not exist: {seed_dir}")
        return False, errors
    
    if not seed_dir.is_dir():
        errors.append(f"Seed path is not a directory: {seed_dir}")
        return False, errors
    
    # Build map of expected files
    expected = {f.path: f for f in manifest.files}
    
    # Check all files in current seed
    found_paths = set()
    for file_path in seed_dir.rglob("*"):
        if file_path.is_file():
            rel_path = str(file_path.relative_to(seed_dir))
            found_paths.add(rel_path)
            
            if rel_path not in expected:
                errors.append(f"Unexpected file: {rel_path}")
                continue
            
            expected_file = expected[rel_path]
            
            # Check size
            actual_size = file_path.stat().st_size
            if actual_size != expected_file.size:
                errors.append(
                    f"Size mismatch for {rel_path}: "
                    f"expected {expected_file.size}, got {actual_size}"
                )
                continue
            
            # Check hash
            actual_hash = compute_file_hash(file_path)
            if actual_hash != expected_file.sha256:
                errors.append(
                    f"Hash mismatch for {rel_path}: "
                    f"expected {expected_file.sha256[:16]}..., got {actual_hash[:16]}..."
                )
    
    # Check for missing files
    for expected_path in expected:
        if expected_path not in found_paths:
            errors.append(f"Missing file: {expected_path}")
    
    return len(errors) == 0, errors


def save_manifest(manifest: BaselineManifest, output_path: pathlib.Path) -> None:
    """Save manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(manifest), f, indent=2, sort_keys=True)
        f.write("\n")


def load_manifest(manifest_path: pathlib.Path) -> BaselineManifest:
    """Load manifest from JSON file."""
    with open(manifest_path) as f:
        data = json.load(f)
    
    # Convert file dicts to FileManifest objects
    files = [FileManifest(**f) for f in data.get("files", [])]
    data["files"] = files
    
    return BaselineManifest(**data)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: baseline.py {generate|verify} <seed_dir> [manifest.json]")
        sys.exit(1)
    
    command = sys.argv[1]
    seed_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "seed")
    manifest_path = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "baseline-manifest.json")
    
    if command == "generate":
        print(f"Generating manifest for {seed_path}...")
        manifest = generate_manifest(seed_path)
        save_manifest(manifest, manifest_path)
        print(f"Manifest saved to {manifest_path}")
        print(f"  Files: {manifest.total_files}")
        print(f"  Total bytes: {manifest.total_bytes}")
        print(f"  Manifest SHA-256: {manifest.manifest_sha256}")
    elif command == "verify":
        print(f"Verifying {seed_path} against {manifest_path}...")
        manifest = load_manifest(manifest_path)
        is_valid, errors = verify_manifest(seed_path, manifest)
        if is_valid:
            print("✅ Seed directory is valid")
            sys.exit(0)
        else:
            print(f"❌ Seed directory verification failed with {len(errors)} errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
