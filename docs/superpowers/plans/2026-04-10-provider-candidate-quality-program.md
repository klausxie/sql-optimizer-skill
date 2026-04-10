# Provider Candidate Quality Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve provider-side candidate quality for the choose-local primary sentinel without widening semantic or patch boundaries.

**Architecture:** Keep the engineering substrate fixed and treat this as a narrow optimize-stage shaping program. Changes should be limited to prompt wording, replay fingerprinting inputs when prompt shape changes, and candidate-quality diagnostics needed to truthfully score provider output.

**Tech Stack:** Python, pytest, optimize-stage cassette replay, sample-project generalization refresh

---

### Task 1: Freeze Provider Baseline Truth

**Files:**
- Create: `docs/superpowers/specs/2026-04-10-provider-candidate-quality-baseline-audit.md`
- Modify: `docs/superpowers/plans/2026-04-10-provider-candidate-quality-program.md`
- Test: `tests/unit/sql/test_optimize_proposal.py`
- Test: `tests/unit/sql/test_llm_cassette.py`
- Test: `tests/unit/sql/test_candidate_generation_engine.py`
- Test: `tests/unit/verification/test_validate_convergence.py`
- Test: `tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Verify the current targeted provider baseline**

Run:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_optimize_proposal.py \
  tests/unit/sql/test_llm_cassette.py \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/ci/test_generalization_summary_script.py \
  -k 'dynamic_surface_contract or choose_local_rewrite_constraints or find_users_by_keyword_candidate_pool_classification or keeps_choose_guarded_safe_baseline_gap_without_branch_identity or choose_guarded_low_value_only_after_identity_reseed or batch9_only_exposes_safe_baseline_focus_and_sentinels or batch13_returns_to_safe_baseline_focus'
```

Expected: PASS

- [ ] **Step 2: Record the current provider truth**

Capture in the audit document:

- primary sentinel
- guardrails
- current choose-local contract
- current cassette id
- returned candidate strategies
- current stop condition

- [ ] **Step 3: Commit the frozen baseline**

```bash
git add docs/superpowers/specs/2026-04-10-provider-candidate-quality-baseline-audit.md \
        docs/superpowers/plans/2026-04-10-provider-candidate-quality-program.md
git commit -m "docs: freeze provider candidate quality baseline"
```

### Task 2: Tighten Choose-Local Prompt Contract

**Files:**
- Modify: `python/sqlopt/platforms/sql/optimizer_sql.py`
- Test: `tests/unit/sql/test_optimize_proposal.py`
- Test: `tests/unit/sql/test_llm_cassette.py`

- [ ] **Step 1: Write or update the failing prompt-contract test**

Add a test asserting the choose-local prompt explicitly instructs:

- local branch cleanup only
- no index advisory / no index-seek style rewrites
- no predicate reduction to default branch
- no set operations
- no branch merge
- no whole-statement rewrite
- return no candidate when the contract cannot be met

- [ ] **Step 2: Run the prompt-contract test and confirm failure if new assertions are added**

Run:

```bash
python3 -m pytest -q tests/unit/sql/test_optimize_proposal.py -k choose_local
```

- [ ] **Step 3: Implement the prompt-contract tightening**

Update `build_optimize_prompt(...)` so the choose-local contract carries stricter negative instructions and a clearer preferred outcome.

- [ ] **Step 4: Verify replay fingerprinting changes only when intended**

Run:

```bash
python3 -m pytest -q tests/unit/sql/test_llm_cassette.py -k optimize
```

Expected: PASS

- [ ] **Step 5: Commit the prompt-contract change**

```bash
git add python/sqlopt/platforms/sql/optimizer_sql.py \
        tests/unit/sql/test_optimize_proposal.py \
        tests/unit/sql/test_llm_cassette.py
git commit -m "feat: tighten choose-local optimize prompt contract"
```

### Task 3: Add Truthful Candidate Quality Scoring

**Files:**
- Modify: `python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Test: `tests/unit/sql/test_candidate_generation_engine.py`
- Test: `tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Write a failing test for provider-side choose-local misfires**

Add tests that classify:

- `UNION ALL` choose rewrites as contract-violating low-value
- flattened predicate rewrites as non-local low-value
- default-branch reductions as low-value

- [ ] **Step 2: Run the new targeted tests and confirm failure**

Run:

```bash
python3 -m pytest -q tests/unit/sql/test_candidate_generation_engine.py -k choose
```

- [ ] **Step 3: Implement the narrow choose-local quality diagnostics**

Extend candidate-generation diagnostics so the primary sentinel exposes truthful low-value categories for contract violations.

- [ ] **Step 4: Verify convergence truth remains blocked**

Run:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/verification/test_validate_convergence.py \
  -k 'choose or findUsersByKeyword'
```

Expected: PASS and still blocked

- [ ] **Step 5: Commit the scoring change**

```bash
git add python/sqlopt/platforms/sql/candidate_generation_engine.py \
        tests/unit/sql/test_candidate_generation_engine.py \
        tests/unit/verification/test_validate_convergence.py
git commit -m "feat: score choose-local provider contract violations"
```

### Task 4: Reseed One Coherent Provider Trial

**Files:**
- Modify: `tests/fixtures/llm_cassettes/optimize/raw/*.json`
- Modify: `tests/fixtures/llm_cassettes/optimize/normalized/*.json`
- Test: `tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Record a fresh provider trial for batch9**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --llm-mode record --max-seconds 240
```

- [ ] **Step 2: Replay the refreshed batches**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --max-seconds 240
python3 scripts/ci/generalization_refresh.py --batch generalization-batch13 --max-seconds 240
```

- [ ] **Step 3: Verify summary truth**

Run:

```bash
python3 -m pytest -q tests/ci/test_generalization_summary_script.py -k 'batch9 or batch13 or blocker_inventory'
```

- [ ] **Step 4: Apply the hard stop rule**

If the primary sentinel is still `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`, stop this program and write the review verdict instead of continuing prompt tweaks.

### Task 5: Write Final Review And Decision

**Files:**
- Create: `docs/superpowers/plans/2026-04-10-provider-candidate-quality-review.md`

- [ ] **Step 1: Write the final outcome**

The review must answer:

- Did provider output improve?
- Did the primary sentinel leave the low-value bucket?
- Did any guardrail widen?
- Should this line continue or stop?

- [ ] **Step 2: Commit the review**

```bash
git add docs/superpowers/plans/2026-04-10-provider-candidate-quality-review.md
git commit -m "docs: review provider candidate quality program"
```
