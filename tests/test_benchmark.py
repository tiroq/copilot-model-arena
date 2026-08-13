#!/usr/bin/env python3
"""Tests for benchmark infrastructure."""

import json
import pathlib
import tempfile
import pytest
from lib.baseline import (
    generate_manifest,
    verify_manifest,
    save_manifest,
    load_manifest,
    compute_file_hash,
)
from lib.contamination import (
    sanitize_model_id,
    normalize_source,
    compute_similarity,
    scan_log_for_references,
    ContaminationEvidence,
)
from lib.report import (
    TaskResult,
    ModelSummary,
    compute_model_summaries,
    compute_judge_agreement,
)


class TestBaseline:
    """Tests for baseline manifest generation and verification."""
    
    def test_sanitize_model_id(self):
        """Test model ID sanitization."""
        assert sanitize_model_id("claude-haiku-4.5") == "claude-haiku-4.5"
        assert sanitize_model_id("GPT-5.5") == "GPT-5.5"
        assert sanitize_model_id("MAI Code 1.1 Flash") == "MAI_Code_1.1_Flash"
        assert sanitize_model_id("model/with/slashes") == "model_with_slashes"
        assert sanitize_model_id("model@special#chars") == "model_special_chars"
    
    def test_generate_manifest(self):
        """Test baseline manifest generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            
            # Create test files
            (seed_dir / "file1.txt").write_text("content1")
            (seed_dir / "file2.txt").write_text("content2")
            subdir = seed_dir / "subdir"
            subdir.mkdir()
            (subdir / "file3.txt").write_text("content3")
            
            # Generate manifest
            manifest = generate_manifest(seed_dir)
            
            assert manifest.total_files == 3
            assert manifest.total_bytes == 24  # 8 + 8 + 8
            assert len(manifest.files) == 3
            assert manifest.manifest_sha256 != ""
            
            # Check files are sorted
            paths = [f.path for f in manifest.files]
            assert paths == sorted(paths)
    
    def test_verify_manifest_valid(self):
        """Test manifest verification with valid seed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            (seed_dir / "file.txt").write_text("content")
            
            # Generate and verify
            manifest = generate_manifest(seed_dir)
            is_valid, errors = verify_manifest(seed_dir, manifest)
            
            assert is_valid
            assert len(errors) == 0
    
    def test_verify_manifest_modified_file(self):
        """Test manifest verification detects modified file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            file_path = seed_dir / "file.txt"
            file_path.write_text("original")
            
            # Generate manifest
            manifest = generate_manifest(seed_dir)
            
            # Modify file
            file_path.write_text("modified")
            
            # Verify should fail
            is_valid, errors = verify_manifest(seed_dir, manifest)
            
            assert not is_valid
            assert len(errors) > 0
            assert any("Hash mismatch" in e for e in errors)
    
    def test_verify_manifest_extra_file(self):
        """Test manifest verification detects extra file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            (seed_dir / "file1.txt").write_text("content")
            
            manifest = generate_manifest(seed_dir)
            
            # Add extra file
            (seed_dir / "file2.txt").write_text("extra")
            
            is_valid, errors = verify_manifest(seed_dir, manifest)
            
            assert not is_valid
            assert any("Unexpected file" in e for e in errors)
    
    def test_verify_manifest_missing_file(self):
        """Test manifest verification detects missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            file_path = seed_dir / "file.txt"
            file_path.write_text("content")
            
            manifest = generate_manifest(seed_dir)
            
            # Remove file
            file_path.unlink()
            
            is_valid, errors = verify_manifest(seed_dir, manifest)
            
            assert not is_valid
            assert any("Missing file" in e for e in errors)
    
    def test_save_load_manifest(self):
        """Test manifest save and load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = pathlib.Path(tmpdir) / "seed"
            seed_dir.mkdir()
            (seed_dir / "file.txt").write_text("content")
            
            manifest_path = pathlib.Path(tmpdir) / "manifest.json"
            
            # Generate and save
            original = generate_manifest(seed_dir)
            save_manifest(original, manifest_path)
            
            # Load
            loaded = load_manifest(manifest_path)
            
            assert loaded.total_files == original.total_files
            assert loaded.total_bytes == original.total_bytes
            assert loaded.manifest_sha256 == original.manifest_sha256
            assert len(loaded.files) == len(original.files)


class TestContamination:
    """Tests for contamination detection."""
    
    def test_normalize_source(self):
        """Test source code normalization."""
        source = '''
        # This is a comment
        def foo():
            """Docstring"""
            return 42  # inline comment
        '''
        normalized = normalize_source(source)
        
        # Comments and docstrings should be removed
        assert "#" not in normalized
        assert "comment" not in normalized.lower()
        assert "docstring" not in normalized.lower()
        # Code should remain
        assert "def" in normalized
        assert "foo" in normalized
        assert "return" in normalized
    
    def test_compute_similarity_identical(self):
        """Test similarity computation for identical files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = pathlib.Path(tmpdir) / "file1.py"
            file2 = pathlib.Path(tmpdir) / "file2.py"
            
            content = "def foo(): return 42"
            file1.write_text(content)
            file2.write_text(content)
            
            similarity = compute_similarity(file1, file2)
            assert similarity == 1.0
    
    def test_compute_similarity_different(self):
        """Test similarity computation for different files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = pathlib.Path(tmpdir) / "file1.py"
            file2 = pathlib.Path(tmpdir) / "file2.py"
            
            file1.write_text("def foo(): return 42")
            file2.write_text("def bar(): return 'hello'")
            
            similarity = compute_similarity(file1, file2)
            assert 0.0 < similarity < 1.0
    
    def test_compute_similarity_with_comments(self):
        """Test that comments are ignored in similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = pathlib.Path(tmpdir) / "file1.py"
            file2 = pathlib.Path(tmpdir) / "file2.py"
            
            # Same code, different comments
            file1.write_text("# Comment A\ndef foo(): return 42")
            file2.write_text("# Comment B\ndef foo(): return 42")
            
            similarity = compute_similarity(file1, file2)
            # Should be very high (normalized versions are identical)
            assert similarity > 0.95
    
    def test_scan_log_for_references(self):
        """Test log scanning for forbidden patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = pathlib.Path(tmpdir) / "agent.log"
            log_content = """
            Reading task specification...
            Checking results/claude-haiku-4.5/01-json-store/src/store.py
            Looking at results/mai-code-1.1-flash/02-retry/src/retry.py
            Implementation complete.
            """
            log_path.write_text(log_content)
            
            patterns = [r"results/", r"claude[-_]haiku", r"mai[-_]code"]
            evidence = scan_log_for_references(log_path, patterns)
            
            # Should find multiple references
            assert len(evidence) >= 3
            assert all(e.type == "log_reference" for e in evidence)
            assert all(e.severity == "high" for e in evidence)
    
    def test_scan_log_no_references(self):
        """Test log scanning with clean log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = pathlib.Path(tmpdir) / "agent.log"
            log_content = """
            Reading task specification from tasks/01-json-store.md
            Implementing src/store.py
            Running tests
            All tests passed
            """
            log_path.write_text(log_content)
            
            patterns = [r"results/", r"other-model"]
            evidence = scan_log_for_references(log_path, patterns)
            
            assert len(evidence) == 0


class TestReport:
    """Tests for report generation."""
    
    def test_task_result_status_valid(self):
        """Test task result status computation."""
        result = TaskResult(
            model_id="test-model",
            task_id="test-task",
            judge_id="test-judge",
            score=85.0,
            scores_by_category={},
            tests_passed=10,
            tests_failed=0,
            tests_total=10,
            defects=[],
            contamination_status="clean",
        )
        assert result.status == "valid"
    
    def test_task_result_status_contaminated(self):
        """Test contaminated status."""
        result = TaskResult(
            model_id="test-model",
            task_id="test-task",
            judge_id="test-judge",
            score=85.0,
            scores_by_category={},
            tests_passed=10,
            tests_failed=0,
            tests_total=10,
            defects=[],
            contamination_status="contaminated",
        )
        assert result.status == "contaminated"
    
    def test_task_result_status_incomplete(self):
        """Test incomplete status (failed tests)."""
        result = TaskResult(
            model_id="test-model",
            task_id="test-task",
            judge_id="test-judge",
            score=50.0,
            scores_by_category={},
            tests_passed=5,
            tests_failed=5,
            tests_total=10,
            defects=[],
            contamination_status="clean",
        )
        assert result.status == "incomplete"
    
    def test_compute_model_summaries(self):
        """Test model summary computation."""
        results = [
            TaskResult(
                model_id="model-a",
                task_id="task-1",
                judge_id="judge-1",
                score=80.0,
                scores_by_category={},
                tests_passed=10,
                tests_failed=0,
                tests_total=10,
                defects=[{"severity": "minor"}],
                contamination_status="clean",
                duration_seconds=120.0,
            ),
            TaskResult(
                model_id="model-a",
                task_id="task-1",
                judge_id="judge-2",
                score=85.0,
                scores_by_category={},
                tests_passed=10,
                tests_failed=0,
                tests_total=10,
                defects=[],
                contamination_status="clean",
                duration_seconds=120.0,
            ),
            TaskResult(
                model_id="model-a",
                task_id="task-2",
                judge_id="judge-1",
                score=90.0,
                scores_by_category={},
                tests_passed=5,
                tests_failed=0,
                tests_total=5,
                defects=[],
                contamination_status="clean",
                duration_seconds=100.0,
            ),
        ]
        
        summaries = compute_model_summaries(results)
        
        assert "model-a" in summaries
        summary = summaries["model-a"]
        assert summary.valid_tasks == 2
        assert summary.contaminated_tasks == 0
        # Mean of task averages: (82.5 + 90) / 2 = 86.25
        assert 86.0 < summary.mean_score < 87.0
        assert summary.total_tests == 15
        assert summary.total_defects == 1
    
    def test_compute_judge_agreement(self):
        """Test judge agreement computation."""
        results = [
            TaskResult(
                model_id="model-a",
                task_id="task-1",
                judge_id="judge-1",
                score=80.0,
                scores_by_category={},
                tests_passed=10,
                tests_failed=0,
                tests_total=10,
                defects=[],
                contamination_status="clean",
            ),
            TaskResult(
                model_id="model-a",
                task_id="task-1",
                judge_id="judge-2",
                score=90.0,
                scores_by_category={},
                tests_passed=10,
                tests_failed=0,
                tests_total=10,
                defects=[],
                contamination_status="clean",
            ),
        ]
        
        agreement = compute_judge_agreement(results)
        
        assert "mean_diff" in agreement
        assert "max_diff" in agreement
        assert agreement["max_diff"] == 10.0  # 90 - 80
        assert agreement["mean_diff"] == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
