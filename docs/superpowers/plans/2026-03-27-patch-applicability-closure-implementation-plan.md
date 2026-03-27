# Patch Applicability Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make statement, fragment, and template patch artifacts follow one delivery lifecycle so `apply-ready` means the same thing across artifact kinds.

**Architecture:** Keep patch build and proof separate, add a dedicated applicability layer, and make `patch_generate` orchestrate `build -> applicability -> proof -> finalize`. Preserve the thin public `patch_result` boundary while exposing only delivery-facing identity and verdicts.

**Tech Stack:** Python 3.9, pytest, existing patch pipeline modules under `python/sqlopt/stages`, JSON schema contracts, verification artifacts under `pipeline/verification`

---

## File Map

- `python/sqlopt/stages/patch_build.py`
  Current build output model; must expose enough artifact identity for applicability checks.
- `python/sqlopt/stages/patch_generate.py`
  Thin orchestrator that must run build, applicability, proof, and finalize in sequence.
- `python/sqlopt/stages/patch_proof.py`
  Proof-only layer; should not decide delivery readiness by itself.
- `python/sqlopt/stages/patch_decision.py`
  Delivery-facing patch result enrichment; likely place to attach thin applicability/failure-class outputs.
- `python/sqlopt/stages/patching_results.py`
  Low-level result constructors; may need thin `patchFamily`/applicability metadata propagation.
- `python/sqlopt/stages/patch_verification.py`
  Must align verification inputs with the new delivery lifecycle without regressing proof semantics.
- `python/sqlopt/stages/patch_applicability.py`
  New module for unified apply-readiness checks and applicability failure classification.
- `contracts/patch_result.schema.json`
  Public patch result schema; may need thin applicability-facing fields only if they are externally valuable.
- `tests/test_patch_delivery_semantics.py`
  New focused delivery-matrix tests for statement/fragment/template artifacts.
- `tests/test_patch_applicability.py`
  Existing applicability regression tests; should move to the new applicability layer and failure taxonomy.
- `tests/test_patch_generate_orchestration.py`
  Main orchestration tests; must prove the delivery lifecycle ordering and downgrade behavior.
- `tests/test_patch_verification.py`
  Proof-layer regression tests; should continue to validate proof independently from applicability.
- `tests/test_fixture_project_patch_report_harness.py`
  Ensures fixture/report consumers remain correct under the new delivery semantics.

### Task 1: Define Delivery Semantics With Focused Tests

**Files:**
- Create: `tests/test_patch_delivery_semantics.py`
- Modify: `tests/test_patch_generate_orchestration.py`
- Modify: `tests/test_patch_applicability.py`

- [ ] **Step 1: Write the failing delivery-matrix tests**

Add a new focused test module covering:

```python
def test_statement_artifact_apply_ready_requires_applicability_and_proof():
    ...

def test_fragment_artifact_applicability_failure_is_not_proof_failure():
    ...

def test_template_artifact_proof_failure_after_applicability_check_is_not_apply_ready():
    ...
```

Also add/update orchestration tests so each artifact kind proves:

1. `materialized`
2. `applicability_checked`
3. `proof_verified`

and lands in the correct failure class when one stage fails.

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_delivery_semantics.py tests/test_patch_generate_orchestration.py tests/test_patch_applicability.py -k 'delivery or applicability or artifact'`

Expected: FAIL because the repo does not yet have a unified delivery model.

- [ ] **Step 3: Commit the test scaffolding**

```bash
git add tests/test_patch_delivery_semantics.py tests/test_patch_generate_orchestration.py tests/test_patch_applicability.py
git commit -m "test: define patch delivery semantics matrix"
```

### Task 2: Introduce A Patch-Owned Applicability Layer

**Files:**
- Create: `python/sqlopt/stages/patch_applicability.py`
- Modify: `python/sqlopt/stages/patch_build.py`
- Modify: `python/sqlopt/stages/patching_results.py`
- Modify: `contracts/patch_result.schema.json`
- Test: `tests/test_patch_delivery_semantics.py`
- Test: `tests/test_patch_applicability.py`

- [ ] **Step 1: Write the failing applicability-layer unit tests**

Add tests for a new applicability result model, for example:

```python
def test_applicability_result_marks_target_mismatch_as_applicability_failure():
    ...

def test_applicability_result_marks_invalid_hunk_as_applicability_failure():
    ...

def test_applicability_result_preserves_artifact_kind_and_target_identity():
    ...
```

- [ ] **Step 2: Run the focused applicability tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_delivery_semantics.py tests/test_patch_applicability.py -k 'applicability'`

Expected: FAIL because `patch_applicability.py` does not exist and build outputs do not yet expose a unified applicability record.

- [ ] **Step 3: Add the applicability module and minimal delivery model**

Implement a new module that returns a thin patch-owned applicability record such as:

```python
@dataclass(frozen=True)
class PatchApplicabilityResult:
    artifact_kind: str
    target_file: str | None
    materialized: bool
    applicability_checked: bool
    apply_ready_candidate: bool
    failure_class: str | None
    reason_code: str | None
```

Keep this model internal. It should classify:

1. target mismatch
2. invalid hunk shape
3. apply-check failure
4. successful applicability checks

- [ ] **Step 4: Extend build outputs just enough for applicability**

Update `patch_build.py` so build results expose:

1. artifact kind
2. target file identity
3. target kind / target ref when relevant

Do not move proof logic into build.

- [ ] **Step 5: Propagate thin delivery-facing fields only if needed**

If a field is valuable externally, keep it thin. Examples that are acceptable:

1. `patchFamily`
2. delivery-facing reason codes

Do not reintroduce internal planning or proof payloads into `patch_result`.

- [ ] **Step 6: Run the applicability tests to verify pass**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_delivery_semantics.py tests/test_patch_applicability.py`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python/sqlopt/stages/patch_applicability.py python/sqlopt/stages/patch_build.py python/sqlopt/stages/patching_results.py contracts/patch_result.schema.json tests/test_patch_delivery_semantics.py tests/test_patch_applicability.py
git commit -m "feat: add patch applicability layer"
```

### Task 3: Rewire Orchestration To Use Build -> Applicability -> Proof

**Files:**
- Modify: `python/sqlopt/stages/patch_generate.py`
- Modify: `python/sqlopt/stages/patch_decision.py`
- Modify: `python/sqlopt/stages/patch_verification.py`
- Modify: `python/sqlopt/stages/patch_proof.py`
- Test: `tests/test_patch_generate_orchestration.py`
- Test: `tests/test_patch_verification.py`
- Test: `tests/test_verification_stage_integration.py`

- [ ] **Step 1: Write the failing orchestration tests**

Add/update tests that explicitly prove:

```python
def test_patch_generate_runs_applicability_before_proof():
    ...

def test_patch_generate_reports_applicability_failure_without_proof_failure_code():
    ...

def test_patch_generate_reports_proof_failure_after_applicability_success():
    ...
```

- [ ] **Step 2: Run the focused orchestration tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_verification_stage_integration.py -k 'applicability or proof or delivery'`

Expected: FAIL because orchestration does not yet treat applicability as its own explicit stage.

- [ ] **Step 3: Rewire `patch_generate.py`**

Make orchestration strictly:

1. build artifact
2. run applicability checks
3. if applicability succeeds, run proof
4. finalize from the two verdicts

Do not let proof stand in for applicability.

- [ ] **Step 4: Keep proof isolated**

Update `patch_proof.py` and `patch_verification.py` only as needed so:

1. proof continues to validate replay/syntax
2. proof verdicts remain meaningful after applicability becomes separate
3. verification rows can represent both applicability and proof outcomes without fallback hacks

- [ ] **Step 5: Re-run the orchestration/proof tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_verification_stage_integration.py`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/stages/patch_generate.py python/sqlopt/stages/patch_decision.py python/sqlopt/stages/patch_verification.py python/sqlopt/stages/patch_proof.py tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_verification_stage_integration.py
git commit -m "refactor: unify patch delivery lifecycle"
```

### Task 4: Align Downstream Consumers And Run Full Regression

**Files:**
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`
- Modify: any targeted report or fixture tests that still assume artifact-kind-specific delivery semantics
- Verify: full test suite

- [ ] **Step 1: Write or update the failing downstream assertions**

Ensure fixture/report consumers prove:

1. auto patches are identified from thin patch outputs plus proof/applicability verdicts
2. dynamic and aggregation fixture obligations still pass
3. no consumer relies on artifact-kind-specific hidden semantics

- [ ] **Step 2: Run the downstream tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py`

Expected: FAIL if any consumer still assumes old delivery behavior.

- [ ] **Step 3: Rewire the remaining consumers**

Update fixture/report helpers so they read:

1. thin patch outputs
2. verification verdicts
3. validate-owned acceptance facts

Do not reintroduce public planning or proof internals to satisfy consumers.

- [ ] **Step 4: Run targeted and full regression**

Run:

```bash
env PYTHONPATH=python python3 -m pytest -q tests/test_patch_delivery_semantics.py tests/test_patch_applicability.py tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_verification_stage_integration.py tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py
env PYTHONPATH=python python3 -m pytest -q
```

Expected:

1. targeted patch/delivery suite passes
2. full suite passes

- [ ] **Step 5: Commit**

```bash
git add tests/fixture_project_harness_support.py tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py
git commit -m "test: align consumers with patch delivery semantics"
```
