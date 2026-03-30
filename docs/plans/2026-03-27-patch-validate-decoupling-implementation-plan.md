# Patch Validate Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strongly decouple `validate` from `patch_generate` so acceptance artifacts stop carrying patch-planning payloads and the patch stage independently derives patch family, strategy, materialization, template ops, and proof.

**Architecture:** Build the new patch-owned pipeline first so `patch_generate` can recompute a full patch plan from thin acceptance input. Once that path is green, delete patch-planning fields from `ValidationResult` and `acceptance_result.schema.json`, then update harnesses and downstream consumers to read patch-owned data from patch outputs instead of acceptance artifacts.

**Tech Stack:** Python 3.9, pytest, JSON schema contracts, existing SQL rewrite analysis helpers, patch verification modules, run-artifact pipeline under `runs/<run_id>/`

---

## File Map

- `python/sqlopt/platforms/sql/validation_models.py`
  Defines `ValidationResult` contract serialization and is the main code-side boundary for thinning acceptance output.
- `contracts/acceptance_result.schema.json`
  Defines the acceptance artifact schema that must stop exporting patch-owned contracts and fields.
- `python/sqlopt/platforms/sql/validator_sql.py`
  Currently assembles `patchTarget`, `selectedPatchStrategy`, `patchability`, `rewriteMaterialization`, and `templateRewriteOps`; this is the upstream ownership that must be removed.
- `python/sqlopt/stages/patch_generate.py`
  Current patch-stage entry point that should become a thin orchestrator over `select -> build -> prove -> finalize`.
- `python/sqlopt/stages/patch_decision_engine.py`
  Current mixed decision/orchestration path that will likely lose acceptance-patch-field dependencies.
- `python/sqlopt/stages/patch_decision.py`
  Current patch diagnostics/degradation logic; must stop reading patch-owned data from acceptance artifacts.
- `python/sqlopt/stages/patch_finalize.py`
  Owns final patch result assembly and is the right place to persist patch-owned metadata after decoupling.
- `python/sqlopt/stages/patching_templates.py`
  Existing template patch builder helpers that should be consumed from the new patch-stage build path.
- `python/sqlopt/platforms/sql/patch_strategy_planner.py`
  Existing planning helper that may be reused, but ownership must become patch-stage-owned.
- `python/sqlopt/platforms/sql/template_materializer.py`
  Existing materialization helper that may be reused, but replay-contract generation should no longer be validate-owned.
- `python/sqlopt/patch_contracts.py`
  Contains current `patchTarget` construction; likely to be reduced or moved so patch-owned persisted payloads are generated in patch stage.
- `python/sqlopt/stages/report_builder.py`
  Downstream report consumer that may still assume patch-related acceptance fields exist.
- `python/sqlopt/stages/report_stats.py`
  Another downstream consumer that may need minimal rewiring away from acceptance patch fields.
- `tests/test_patch_generate_orchestration.py`
  Primary regression suite proving patch generation works from acceptance inputs.
- `tests/test_patch_verification.py`
  Guards verification semantics that must survive the contract move.
- `tests/test_patch_contracts.py`
  Covers patch-target-like contract behavior and will need to move toward patch-result-owned payloads.
- `tests/test_fixture_project_validate_harness.py`
  Must be narrowed to validate-owned expectations only.
- `tests/test_fixture_project_patch_report_harness.py`
  Must prove patch/report still work when acceptance no longer exports patch-planning fields.
- `tests/test_validate_candidate_selection.py`
  Covers validation selection behavior and must remain green after patch logic is removed from validation outputs.

### Task 1: Establish A Patch-Owned Planning Context

**Files:**
- Create: `python/sqlopt/stages/patch_select.py`
- Modify: `python/sqlopt/stages/patch_generate.py`
- Modify: `python/sqlopt/stages/patch_decision_engine.py`
- Test: `tests/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write the failing orchestration test for thin acceptance input**

Add a focused test showing `patch_generate.execute_one()` can still produce an applicable patch when acceptance only carries validate-owned fields:

```python
def test_patch_generate_recomputes_patch_plan_from_thin_acceptance(tmp_path: Path) -> None:
    acceptance = {
        "sqlKey": sql_unit["sqlKey"],
        "status": "PASS",
        "selectedCandidateId": "candidate-1",
        "rewrittenSql": "SELECT ...",
        "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
        "perfComparison": {"checked": True, "improved": True},
        "securityChecks": {},
    }
    patch_row = execute_one(sql_unit, acceptance, run_dir, validator, config={})
    assert patch_row["applicable"] is True
    assert patch_row["strategyType"] == "EXACT_TEMPLATE_EDIT"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py -k thin_acceptance`
Expected: FAIL because `patch_generate` and `patch_decision_engine` still read `patchTarget`, `selectedPatchStrategy`, `rewriteMaterialization`, or `templateRewriteOps` from acceptance.

- [ ] **Step 3: Add a patch-owned selection context**

Create `python/sqlopt/stages/patch_select.py` with a focused entry point:

```python
@dataclass(frozen=True)
class PatchSelectionContext:
    rewritten_sql: str
    selected_candidate_id: str
    semantic_gate_status: str
    semantic_gate_confidence: str
    family: str | None
    patchability: dict[str, Any]
    strategy_candidates: list[dict[str, Any]]
    selected_strategy: dict[str, Any] | None


def build_patch_selection_context(*, sql_unit: dict[str, Any], acceptance: dict[str, Any], fragment_catalog: dict[str, Any]) -> PatchSelectionContext:
    ...
```

Implementation constraints:
- do not read `patchTarget` from acceptance
- recompute family/patchability/strategy from `sql_unit + rewrittenSql`
- keep gate enforcement in patch stage

- [ ] **Step 4: Rewire `patch_generate.py` and `patch_decision_engine.py` to consume the new selection context**

Minimal target shape:

```python
selection = build_patch_selection_context(...)
patch, decision_ctx = decide_patch_result(..., selection=selection, ...)
```

`decide_patch_result()` should stop assuming patch-owned acceptance fields exist.

- [ ] **Step 5: Re-run the focused orchestration test**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py -k thin_acceptance`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/stages/patch_select.py python/sqlopt/stages/patch_generate.py python/sqlopt/stages/patch_decision_engine.py tests/test_patch_generate_orchestration.py
git commit -m "refactor: build patch plans from thin acceptance input"
```

### Task 2: Move Materialization And Template-Op Planning Into Patch Stage

**Files:**
- Create: `python/sqlopt/stages/patch_build.py`
- Modify: `python/sqlopt/stages/patch_generate.py`
- Modify: `python/sqlopt/stages/patching_templates.py`
- Modify: `python/sqlopt/platforms/sql/template_materializer.py`
- Test: `tests/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write the failing test for patch-owned template planning**

Add a test showing patch generation can build statement or fragment template operations without `rewriteMaterialization` or `templateRewriteOps` in acceptance:

```python
def test_patch_generate_builds_template_ops_without_acceptance_materialization(tmp_path: Path) -> None:
    acceptance = thin_acceptance(...)
    patch_row = execute_one(sql_unit, acceptance, run_dir, validator, config={})
    assert patch_row["applicable"] is True
    assert patch_row["patchTarget"]["templateRewriteOps"]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py -k template_ops_without_acceptance_materialization`
Expected: FAIL because current patch builders still expect materialization/template ops to be precomputed in acceptance.

- [ ] **Step 3: Add a patch-stage build module**

Create `python/sqlopt/stages/patch_build.py`:

```python
@dataclass(frozen=True)
class PatchBuildResult:
    rewrite_materialization: dict[str, Any]
    template_rewrite_ops: list[dict[str, Any]]
    patch_text: str
    changed_lines: int


def build_patch_plan(*, sql_unit: dict[str, Any], selection: PatchSelectionContext, run_dir: Path, fragment_catalog: dict[str, Any]) -> PatchBuildResult:
    ...
```

Implementation rules:
- derive materialization mode from selected strategy inside patch stage
- generate template ops inside patch stage
- keep using existing low-level helpers where possible
- do not persist replay contracts here yet

- [ ] **Step 4: Rewire `patch_generate.py` to use the build result**

Pattern:

```python
selection = build_patch_selection_context(...)
build = build_patch_plan(...)
patch = finalize_generated_patch(..., patch_text=build.patch_text, ...)
```

Keep `patch_generate.py` orchestration-only.

- [ ] **Step 5: Re-run the focused test**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py -k template_ops_without_acceptance_materialization`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/stages/patch_build.py python/sqlopt/stages/patch_generate.py python/sqlopt/stages/patching_templates.py python/sqlopt/platforms/sql/template_materializer.py tests/test_patch_generate_orchestration.py
git commit -m "refactor: move patch materialization planning into patch stage"
```

### Task 3: Move Replay-Contract Construction Into Patch Proof

**Files:**
- Create: `python/sqlopt/stages/patch_proof.py`
- Modify: `python/sqlopt/stages/patch_generate.py`
- Modify: `python/sqlopt/verification/patch_replay.py`
- Modify: `python/sqlopt/verification/patch_syntax.py`
- Test: `tests/test_patch_generate_orchestration.py`
- Test: `tests/test_patch_verification.py`

- [ ] **Step 1: Write the failing proof-path test**

Add a test proving replay and syntax evidence still close when `acceptance` has no `patchTarget` or `replayContract`:

```python
def test_patch_generate_derives_replay_contract_in_patch_stage(tmp_path: Path) -> None:
    acceptance = thin_acceptance(...)
    patch_row = execute_one(sql_unit, acceptance, run_dir, validator, config={})
    assert patch_row["replayEvidence"]["matchesTarget"] is True
    assert patch_row["syntaxEvidence"]["ok"] is True
```

- [ ] **Step 2: Run the focused proof tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py tests/test_patch_verification.py -k replay_contract_in_patch_stage`
Expected: FAIL because replay and syntax still assume proof inputs were frozen upstream.

- [ ] **Step 3: Add a patch-proof module**

Create `python/sqlopt/stages/patch_proof.py`:

```python
@dataclass(frozen=True)
class PatchProofResult:
    patch_target: dict[str, Any]
    replay_evidence: dict[str, Any]
    syntax_evidence: dict[str, Any]
    ok: bool
    reason_code: str | None


def prove_patch_plan(*, sql_unit: dict[str, Any], acceptance: dict[str, Any], selection: PatchSelectionContext, build: PatchBuildResult, fragment_catalog: dict[str, Any]) -> PatchProofResult:
    ...
```

Implementation rules:
- derive replay contract from build result inside patch stage
- materialize artifact and run replay/syntax there
- any `patchTarget`-like payload is now a patch-stage artifact, not an acceptance artifact

- [ ] **Step 4: Rewire `patch_generate.py` to finalize from proof output**

Target shape:

```python
proof = prove_patch_plan(...)
patch["patchTarget"] = proof.patch_target
patch["replayEvidence"] = proof.replay_evidence
patch["syntaxEvidence"] = proof.syntax_evidence
```

Degrade through patch-stage proof failure only.

- [ ] **Step 5: Re-run the focused proof tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py tests/test_patch_verification.py -k replay_contract_in_patch_stage`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/stages/patch_proof.py python/sqlopt/stages/patch_generate.py python/sqlopt/verification/patch_replay.py python/sqlopt/verification/patch_syntax.py tests/test_patch_generate_orchestration.py tests/test_patch_verification.py
git commit -m "refactor: derive replay proof inside patch stage"
```

### Task 4: Remove Patch Planning From Validation Output

**Files:**
- Modify: `python/sqlopt/platforms/sql/validation_models.py`
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Modify: `contracts/acceptance_result.schema.json`
- Test: `tests/test_validate_candidate_selection.py`
- Test: `tests/test_fixture_project_validate_harness.py`

- [ ] **Step 1: Write the failing acceptance-contract tests**

Add or update tests asserting new acceptance rows do not include patch-owned fields:

```python
def test_validation_result_contract_omits_patch_planning_fields() -> None:
    payload = validation_result.to_contract()
    assert "patchTarget" not in payload
    assert "selectedPatchStrategy" not in payload
    assert "rewriteMaterialization" not in payload
    assert "templateRewriteOps" not in payload
```

Also add a schema-oriented fixture expectation that thin acceptance rows still validate.

- [ ] **Step 2: Run the focused validate tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py -k 'omit_patch_planning or thin_acceptance'`
Expected: FAIL because validation still serializes patch-owned fields and the schema still allows or defines them.

- [ ] **Step 3: Remove patch-owned fields from `ValidationResult` and validator assembly**

Delete or stop populating:
- `rewrite_materialization`
- `template_rewrite_ops`
- `patchability`
- `selected_patch_strategy`
- `patch_target`
- `dynamic_template`
- `patch_strategy_candidates`
- `delivery_readiness` if it is patch-owned in practice

Also remove `_build_patch_target()` call sites and patch-owned payload assembly from `validator_sql.py`.

- [ ] **Step 4: Thin the acceptance schema**

Update `contracts/acceptance_result.schema.json` so it no longer defines or exports:
- `PatchTargetContract`
- `PatchReplayContract`
- patch-owned top-level fields removed in Step 3

Keep only validate-owned fields.

- [ ] **Step 5: Re-run the focused validate tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py -k 'omit_patch_planning or thin_acceptance'`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/validation_models.py python/sqlopt/platforms/sql/validator_sql.py contracts/acceptance_result.schema.json tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py
git commit -m "refactor: thin acceptance contracts for patch decoupling"
```

### Task 5: Rewire Patch Diagnostics And Downstream Consumers

**Files:**
- Modify: `python/sqlopt/stages/patch_decision.py`
- Modify: `python/sqlopt/stages/patch_finalize.py`
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `python/sqlopt/stages/report_stats.py`
- Test: `tests/test_fixture_project_patch_report_harness.py`
- Test: `tests/test_patch_contracts.py`

- [ ] **Step 1: Write the failing downstream tests**

Add coverage proving downstream consumers read patch-owned data from patch outputs instead of acceptance rows:

```python
def test_patch_diagnostics_do_not_depend_on_acceptance_patch_fields() -> None:
    patch_row = execute_one(sql_unit, thin_acceptance(...), run_dir, validator, config={})
    assert patch_row["patchability"]["templateSafePath"] is True


def test_patch_report_harness_works_with_thin_acceptance_rows() -> None:
    report = build_report_for_fixture_run(...)
    assert report["patch_stats"]["applicable"] >= 1
```

- [ ] **Step 2: Run the focused downstream tests to verify they fail**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_patch_contracts.py -k 'thin_acceptance or patch_fields'`
Expected: FAIL because patch diagnostics or report code still pull patch planning fields from acceptance artifacts.

- [ ] **Step 3: Rewire downstream readers**

Rules:
- `patch_decision.py` should prefer patch-owned fields produced during patch execution
- `patch_finalize.py` should persist the patch-owned payload in one consistent place
- `report_builder.py` and `report_stats.py` should read patch-owned metadata from patch results when patch semantics are needed
- avoid redesigning report wording or statistics scope beyond what this refactor requires

- [ ] **Step 4: Re-run the focused downstream tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_patch_contracts.py -k 'thin_acceptance or patch_fields'`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/stages/patch_decision.py python/sqlopt/stages/patch_finalize.py python/sqlopt/stages/report_builder.py python/sqlopt/stages/report_stats.py tests/test_fixture_project_patch_report_harness.py tests/test_patch_contracts.py
git commit -m "refactor: move patch consumers off acceptance artifacts"
```

### Task 6: Lock Full Regression Coverage For The New Boundary

**Files:**
- Modify: `tests/test_patch_generate_orchestration.py`
- Modify: `tests/test_patch_verification.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`
- Modify: `tests/test_validate_candidate_selection.py`

- [ ] **Step 1: Add final regression cases**

Explicitly lock:
- acceptance rows without `patchTarget`
- acceptance rows without `selectedPatchStrategy`
- acceptance rows without `rewriteMaterialization`
- statement-path patch generation from thin acceptance
- fragment-path patch generation from thin acceptance
- verification closure still holding under the new boundary

- [ ] **Step 2: Run the focused boundary regression suite**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py`
Expected: PASS

- [ ] **Step 3: Run the broader patch and contract suite**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_applicability.py tests/test_patch_contracts.py tests/test_patch_family_registry.py tests/test_patch_syntax.py tests/test_patch_replay.py tests/test_verification_stage_integration.py`
Expected: PASS

- [ ] **Step 4: Run the full repository suite**

Run: `env PYTHONPATH=python python3 -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_patch_generate_orchestration.py tests/test_patch_verification.py tests/test_validate_candidate_selection.py tests/test_fixture_project_validate_harness.py tests/test_fixture_project_patch_report_harness.py
git commit -m "test: lock patch validate decoupling regressions"
```
