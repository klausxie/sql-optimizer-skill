# Patch Harness Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the current patch harness engineering gaps by unifying blocker-family accounting, adding engine-level regression tests, aligning fixture harness project roots, and extending full-workflow coverage.

**Architecture:** Keep the patch delivery logic unchanged where possible and strengthen the harness around it. Centralize blocker-family classification in production helpers, make fixture/report tests consume the same production logic, and add orchestration-level tests where refactors are currently under-constrained.

**Tech Stack:** Python, pytest, unittest, existing fixture-project harness, workflow golden E2E harness

---

### Task 1: Lock blocker-family aggregation to production logic

**Files:**
- Modify: `python/sqlopt/stages/report_stats.py`
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the focused patch/report harness tests and confirm blocker-family assertions fail**
- [ ] **Step 3: Add a shared production helper for patch-row blocker-family classification**
- [ ] **Step 4: Route report blocker-family stats through the shared helper**
- [ ] **Step 5: Reuse the shared helper in fixture harness support to remove duplicated mapping logic**
- [ ] **Step 6: Re-run the focused tests until green**

### Task 2: Add patch decision engine orchestration tests

**Files:**
- Modify: `tests/test_patch_decision_core.py`

- [ ] **Step 1: Write failing engine-level tests for gate ordering, shared-context propagation, and skip behavior**
- [ ] **Step 2: Run the focused engine tests and confirm current coverage is insufficient**
- [ ] **Step 3: Add only the minimal imports or production adjustments required by the tests**
- [ ] **Step 4: Re-run the engine tests until green**

### Task 3: Align fixture patch harness project root semantics

**Files:**
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Write a failing test that proves fixture patch applicability checks run against the fixture project root**
- [ ] **Step 2: Run the focused fixture harness test and observe the wrong cwd**
- [ ] **Step 3: Switch the harness patch config to `tests/fixtures/project`**
- [ ] **Step 4: Re-run the focused test until green**

### Task 4: Extend higher-fidelity full workflow coverage

**Files:**
- Modify: `tests/test_workflow_golden_e2e.py`

- [ ] **Step 1: Add a full-workflow regression test that checks patch/report blocker-family and applicability aggregates against emitted patch artifacts**
- [ ] **Step 2: Run the focused golden workflow test**
- [ ] **Step 3: Adjust assertions or shared helpers only if the real workflow exposes a legitimate gap**
- [ ] **Step 4: Re-run the workflow test until green**

### Task 5: Verify the complete patch harness slice

**Files:**
- Verify only

- [ ] **Step 1: Run the focused patch harness test suite**
- [ ] **Step 2: Run the broader workflow/report verification set touching modified files**
- [ ] **Step 3: Review results and report any residual risks**
