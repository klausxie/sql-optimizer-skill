# Family Registry Small Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce repeated family-specific branching in `run_sample_project.py` and `validate_convergence.py` without changing current `sample_project` behavior.

**Architecture:** Convert stable sample-project family scopes into a single scope registry and convert the repeated static convergence family checks into small data-driven registries/helpers. Keep runtime outputs unchanged by verifying against existing ready/blocked sample statements after the refactor.

**Tech Stack:** Python, pytest, sample-project fixture runs

---

### Task 1: Consolidate `run_sample_project.py` family scope definitions

**Files:**
- Modify: `scripts/run_sample_project.py`
- Test: `tests/ci/test_run_sample_project_script.py`

- [ ] **Step 1: Write the failing test**

Add a test that asserts family scopes are sourced from a single registry and that an existing scope such as `having-alias-family` still expands to the expected SQL key list.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ci/test_run_sample_project_script.py -q`
Expected: FAIL because the new registry-facing assertion does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Refactor `scripts/run_sample_project.py` so:
- family SQL-key tuples are stored in one mapping
- parser `choices` derive from that mapping plus `project/mapper/sql`
- `_build_sqlopt_cli_args()` uses the mapping for family scopes instead of a long branch chain

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/ci/test_run_sample_project_script.py -q`
Expected: PASS

### Task 2: Consolidate static convergence family rules

**Files:**
- Modify: `python/sqlopt/stages/validate_convergence.py`
- Test: `tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Write the failing test**

Add a test that checks the small registries/helpers still map representative sample families correctly:
- `HAVING_WRAPPER`
- `GROUP_BY_WRAPPER`
- `GROUP_BY_HAVING_ALIAS`
- `STATIC_SUBQUERY_WRAPPER`

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/verification/test_validate_convergence.py -q`
Expected: FAIL because the new helper/registry contract does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Refactor `validate_convergence.py` so:
- stable shape-family constants remain, but repeated support checks and strategy-shape mappings are grouped in small registries/helpers
- `target_shape_supported()` and shape-specific family hint logic use those registries
- behavior for existing sample families remains unchanged

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/verification/test_validate_convergence.py -q`
Expected: PASS

### Task 3: Verify sample-project sentinel runs did not regress

**Files:**
- Verify only: `tests/fixtures/projects/sample_project/runs/*`

- [ ] **Step 1: Re-run representative ready/blocked families**

Run:
- `python3 scripts/run_sample_project.py --scope having-family --run-id run_having_wrapper_family_after_abstraction --max-seconds 240`
- `python3 scripts/run_sample_project.py --scope groupby-family --run-id run_groupby_wrapper_family_after_abstraction --max-seconds 240`
- `python3 scripts/run_sample_project.py --scope having-alias-family --run-id run_groupby_having_alias_family_after_abstraction --max-seconds 240`

Expected:
- ready statements remain `AUTO_PATCHABLE`
- blocked neighbors remain blocked
- patch files remain present only for ready statements

- [ ] **Step 2: Run full verification**

Run: `python3 -m pytest -q`
Expected: PASS
