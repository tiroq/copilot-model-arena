# Canonical Implementation Prompt

You are implementing a specific task in an isolated workspace as part of a benchmark evaluation.

## Task Specification

Read the task specification file: `{task_file}`

The specification defines:
- Required API and exact function signatures
- Expected behavior and semantics
- Required tests
- Scope restrictions

## Your Responsibilities

1. **Read the task specification carefully**
   - Understand all requirements
   - Note all acceptance criteria
   - Identify all required tests

2. **Implement the requested feature**
   - Follow the API specification exactly
   - Implement all required behavior
   - Handle all specified edge cases
   - Follow Python best practices

3. **Add comprehensive tests**
   - Cover all specified test cases
   - Add tests for edge cases
   - Ensure all tests pass
   - Use pytest framework

4. **Verify your implementation**
   - Run the complete test suite: `pytest tests/ -v`
   - Fix any failing tests
   - Review the diff to ensure only task-relevant changes

5. **Document your work**
   - Create `implementation-summary.md` with:
     - Commands you ran
     - Test results (passed/failed counts)
     - Brief description of your implementation approach
     - Any notes about edge cases or decisions

## Critical Restrictions

❌ **DO NOT**:
- Access or read any files outside this workspace directory
- Reference or copy code from other benchmark results
- Access the `results/` directory or any other model's solutions
- Modify files outside the scope of this task
- Add features not specified in the task
- Use network access unless explicitly required by the task
- Modify benchmark orchestration or infrastructure files

✅ **DO**:
- Work only within this isolated directory
- Read only the task specification and files in this workspace
- Implement exactly what is specified
- Add or update tests as required
- Run tests to verify correctness
- Report test failures honestly
- Stop after implementation and verification

## Workspace Structure

```
.
├── pyproject.toml          # Project metadata
├── src/                    # Source code directory
│   └── (implement here)
└── tests/                  # Test directory
    └── (add tests here)
```

## Expected Deliverables

1. Implementation in `src/` matching the task specification
2. Comprehensive tests in `tests/`
3. All tests passing (or documented failures with explanations)
4. `implementation-summary.md` documenting your work

## Commands to Run

```bash
# Run tests
pytest tests/ -v

# Check diff (if git is available)
git diff --stat
git diff
```

## Integrity Notice

This is an independent implementation task. Your work will be evaluated for:
- Correctness and completeness
- Test quality and coverage
- Adherence to specifications
- Code quality and maintainability
- Independence (no access to other solutions)

Begin implementation now. Read `{task_file}` and implement the required functionality.
