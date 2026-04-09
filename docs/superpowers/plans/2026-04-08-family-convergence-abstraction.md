# Family Convergence Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate family convergence rules into explicit registries without changing the current run/artifact model or regressing proven `sample_project` family outcomes.

**Architecture:** Keep behavior stable while moving repeated convergence knowledge into data-driven registries. Split one-to-one strategy mappings from generic strategies, centralize family scope data for `sample_project`, and verify against sentinel real runs plus full regression.

**Tech Stack:** Python, pytest, existing `sample_project` fixture runs, SQL optimizer convergence layer, patch family registry.

---

### Task 1: Freeze Current Behavior With Regression Tests

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/patch/test_patch_selection.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`

- [ ] **Step 1: Add a failing test for one-to-one strategy mappings**

Add assertions for strategy-family pairs that are safe to auto-map, such as:

```python
assert derive_patch_target_family(
    original_sql="SELECT id FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id)",
    rewritten_sql="SELECT id FROM users u",
    rewrite_facts={},
    rewrite_materialization=None,
    selected_patch_strategy={"strategyType": "SAFE_EXISTS_REWRITE"},
) == "STATIC_EXISTS_REWRITE"
```

- [ ] **Step 2: Add a failing test for generic wrapper strategy handling**

Add an explicit regression asserting:

```python
assert derive_patch_target_family(
    original_sql="SELECT id FROM (SELECT id FROM users) u",
    rewritten_sql="SELECT id FROM users",
    rewrite_facts={},
    rewrite_materialization=None,
    selected_patch_strategy={"strategyType": "SAFE_WRAPPER_COLLAPSE"},
) == "STATIC_WRAPPER_COLLAPSE"
```

- [ ] **Step 3: Add a failing test for plain static JOIN shape inference**

Add a test that a plain join statement remains `STATIC_STATEMENT`, not a join family:

```python
assert infer_shape_family_from_sql_unit(
    _sql_unit(sql="SELECT u.id, o.order_no FROM users u JOIN orders o ON o.user_id = u.id")
) == "STATIC_STATEMENT"
```

- [ ] **Step 4: Add a failing test for family scope registry stability**

Add a script-level test that one known scope still resolves its expected SQL keys:

```python
args = _build_sqlopt_cli_args(scope="groupby-family", ...)
assert "--sql-key" in args
```

- [ ] **Step 5: Run the targeted tests and confirm they fail before refactor**

Run:

```bash
python3 -m pytest tests/unit/verification/test_validate_convergence.py tests/unit/patch/test_patch_selection.py tests/ci/test_run_sample_project_script.py -q
```

Expected: at least one new regression test fails before the implementation work starts.


### Task 2: Extract a Convergence Registry Module

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/convergence_registry.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`

- [ ] **Step 1: Create a new registry module for family convergence data**

Move pure data declarations into a new module:

```python
TARGET_SHAPE_FAMILY = "IF_GUARDED_FILTER_STATEMENT"
SUPPORTED_STATIC_SHAPE_FAMILIES = {...}
RECOVERED_PATCH_FAMILY_BY_STRATEGY = {...}
SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES = {...}
SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES = {...}
```

- [ ] **Step 2: Keep generic strategy logic out of the registry**

Do **not** place generic strategies like `SAFE_WRAPPER_COLLAPSE` into a one-to-one generated map. Keep those in explicit code paths.

- [ ] **Step 3: Update `validate_convergence.py` imports**

Replace local duplicated constants/tables with imports from `convergence_registry.py`.

- [ ] **Step 4: Keep shape inference local**

Do not move the actual `infer_shape_family_from_sql_unit()` logic yet. Only move data and lookup tables so the refactor remains behavior-preserving.

- [ ] **Step 5: Run the targeted convergence tests**

Run:

```bash
python3 -m pytest tests/unit/verification/test_validate_convergence.py -q
```

Expected: PASS.


### Task 3: Make Strategy-to-Family Resolution Explicit

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/patch_families/registry.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_utils.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/patch/test_patch_selection.py`

- [ ] **Step 1: Restrict generated strategy-family maps to one-to-one cases**

Update the registry helper so it only exports specific strategy mappings, for example:

```python
if strategy not in {"EXACT_TEMPLATE_EDIT", "DYNAMIC_STATEMENT_TEMPLATE_EDIT", "EXISTING_PIPELINE", "SAFE_WRAPPER_COLLAPSE"}:
    strategy_to_family[strategy.upper()] = spec.family
```

- [ ] **Step 2: Keep explicit fallback logic in `derive_patch_target_family()`**

Retain explicit handling for generic strategies:

```python
if strategy_type == "SAFE_WRAPPER_COLLAPSE":
    return "STATIC_WRAPPER_COLLAPSE"
```

- [ ] **Step 3: Remove dead or misleading helper logic**

If `build_shape_family_to_patch_family_map()` is still unused or generates keys that do not match runtime shape values, either delete it or rewrite it to match real runtime identifiers. Do not keep a misleading helper.

- [ ] **Step 4: Run patch selection tests**

Run:

```bash
python3 -m pytest tests/unit/patch/test_patch_selection.py -q
```

Expected: PASS.


### Task 4: Normalize `sample_project` Family Scope Data

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/run_sample_project.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`

- [ ] **Step 1: Extract family scope constants into a dedicated module**

Move the large family scope tuples and registry into a dedicated data module:

```python
FAMILY_SCOPE_SQL_KEYS = {
    "groupby-family": (...),
    "having-family": (...),
}
```

- [ ] **Step 2: Keep `run_sample_project.py` as a thin adapter**

Import the family scope registry and keep CLI argument handling in the script. The script should still own command-line parsing, but not the growing data blob.

- [ ] **Step 3: Preserve current scope names exactly**

Do not rename scopes. Existing commands such as:

```bash
python3 scripts/run_sample_project.py --scope groupby-family
```

must continue to work unchanged.

- [ ] **Step 4: Run script tests**

Run:

```bash
python3 -m pytest tests/ci/test_run_sample_project_script.py -q
```

Expected: PASS.


### Task 5: Sentinel Real-Run Verification

**Files:**
- Verify only:
  - `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/runs/`

- [ ] **Step 1: Re-run one dynamic sentinel**

Run:

```bash
PYTHONPATH=python python3 scripts/run_sample_project.py --scope family
```

Expected: previously ready `IF_GUARDED_FILTER_STATEMENT` samples stay ready.

- [ ] **Step 2: Re-run one wrapper sentinel**

Run:

```bash
PYTHONPATH=python python3 scripts/run_sample_project.py --scope wrapper-family
```

Expected: wrapper-family sample still produces a patch and remains in the correct family.

- [ ] **Step 3: Re-run one alias/aggregation sentinel**

Run:

```bash
PYTHONPATH=python python3 scripts/run_sample_project.py --scope having-alias-family
```

Expected: the statement remains `AUTO_PATCHABLE` and keeps the correct patch family.

- [ ] **Step 4: Re-run one blocked sentinel**

Run:

```bash
PYTHONPATH=python python3 scripts/run_sample_project.py --scope union-family
```

Expected: the plain `UNION` sample remains blocked with `SHAPE_FAMILY_NOT_TARGET`.

- [ ] **Step 5: Inspect artifacts**

Check:

```bash
python3 scripts/ci/if_guarded_progress.py <run_dir> --mode observe --format text
```

and inspect `artifacts/statement_convergence.jsonl` plus `artifacts/patches.jsonl`.


### Task 6: Full Regression and Closeout

**Files:**
- Verify only

- [ ] **Step 1: Run focused abstraction regression**

Run:

```bash
python3 -m pytest \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/patch/test_patch_selection.py \
  tests/ci/test_run_sample_project_script.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Prepare a before/after summary**

Summarize:

- which files became thinner
- which registries were centralized
- which sentinel family runs were re-verified
- whether any ready/blocked behavior changed

- [ ] **Step 4: Commit**

```bash
git add \
  python/sqlopt/stages/convergence_registry.py \
  python/sqlopt/stages/validate_convergence.py \
  python/sqlopt/platforms/sql/patch_utils.py \
  python/sqlopt/patch_families/registry.py \
  python/sqlopt/devtools/sample_project_family_scopes.py \
  scripts/run_sample_project.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/patch/test_patch_selection.py \
  tests/ci/test_run_sample_project_script.py \
  docs/superpowers/specs/2026-04-08-family-convergence-abstraction-design.md \
  docs/superpowers/plans/2026-04-08-family-convergence-abstraction.md
git commit -m "refactor: consolidate family convergence registries"
```
