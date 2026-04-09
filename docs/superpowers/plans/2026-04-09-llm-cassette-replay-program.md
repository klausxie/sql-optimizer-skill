# LLM Cassette Replay Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple day-to-day test execution from live LLM latency by introducing a record/replay cassette layer for optimize-stage candidate generation, while preserving the current run/artifact contracts and keeping true provider coverage available for dedicated smoke and acceptance paths.

**Architecture:** Add a thin LLM replay gateway at the optimize-stage provider boundary. The gateway supports three modes:

- `live`: call the real provider
- `record`: call the real provider and persist a replay cassette
- `replay`: return the recorded response and never hit the provider

The first implementation only covers optimize-stage LLM candidate generation:

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/optimize.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/optimizer_sql.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/llm/provider.py`

This program explicitly avoids:

- changing validate-stage LLM semantic-check behavior
- changing patch-generate LLM assist behavior
- making replay silently fall back to live
- keying cassettes only by `sqlKey`
- mixing cassette files into run artifacts

**Tech Stack:** Python, pytest, optimize-stage LLM provider path, `scripts/run_sample_project.py`, `scripts/ci/generalization_refresh.py`, `sample_project` fixture project, JSON cassette files under `tests/fixtures/llm_cassettes`.

---

## Current Problem

The current test/runtime loop is slower than necessary because optimize-stage candidate generation always goes through the live provider path unless tests fully mock the layer. This creates two problems:

1. integration and harness runs are unnecessarily slow
2. logic tests that do not care about provider behavior still depend on LLM latency

The new target operating model is:

- unit tests: keep direct mocks where appropriate
- integration/harness/generalization tests: default to `replay`
- dedicated LLM smoke/acceptance: use `live` or `record`

---

## Program Strategy

Implement the decoupling in five controlled steps:

1. define a stable cassette contract and fingerprint
2. add a replay gateway without changing optimize-stage output shape
3. wire optimize-stage through the gateway
4. record a first cassette set for `sample_project`
5. switch selected scripts/tests to `replay` by default

Success means:

- optimize logic tests can run without a live provider
- replay misses fail explicitly
- existing optimize/proposals/trace contracts remain intact
- dedicated live-provider smoke paths still exist and stay opt-in

---

## Task 1: Freeze the Cassette Contract and Fingerprint

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/llm_cassette.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_llm_cassette.py`

- [ ] **Step 1: Define cassette metadata and storage layout**

Create a cassette helper module with a stable layout:

```text
tests/fixtures/llm_cassettes/optimize/raw/<fingerprint>.json
tests/fixtures/llm_cassettes/optimize/normalized/<fingerprint>.json
```

Each raw cassette must store at minimum:

- `fingerprint`
- `provider`
- `model`
- `promptVersion`
- `sqlKey`
- `request`
- `response`
- `createdAt`

Each normalized cassette must store at minimum:

- `fingerprint`
- `sqlKey`
- `rawCandidateCount`
- `validCandidates`
- `trace`

- [ ] **Step 2: Define a stable fingerprint input**

The fingerprint must include only stable replay-relevant inputs:

- `sqlKey`
- normalized `sql`
- normalized `templateSql`
- `dynamicFeatures`
- stable DB evidence subset
- prompt version
- provider
- model

It must explicitly exclude:

- `run_id`
- timestamps
- temp paths
- machine-local directories

- [ ] **Step 3: Write fingerprint stability tests**

Add unit tests asserting:

- same logical request => same fingerprint
- prompt version change => different fingerprint
- provider/model change => different fingerprint

- [ ] **Step 4: Write cassette read/write roundtrip tests**

Verify that:

- a saved raw cassette can be loaded back exactly
- a saved normalized cassette can be loaded back exactly
- missing cassette returns a typed miss result, not `None` ambiguity

**Success standard:** cassette IO and fingerprinting are deterministic before any provider integration is touched.

---

## Task 2: Add the Replay Gateway at the LLM Boundary

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/llm_replay_gateway.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/llm/provider.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_llm_replay_gateway.py`

- [ ] **Step 1: Introduce a mode-aware gateway**

Add a gateway API along the lines of:

```python
def generate_optimize_candidates_with_replay(..., llm_cfg: dict[str, Any], ...):
    ...
```

Supported modes:

- `live`
- `record`
- `replay`

- [ ] **Step 2: Keep replay strict by default**

When `mode=replay` and no cassette exists:

- raise a clear error
- include `sqlKey`, `fingerprint`, and cassette path in the message

Do not silently fall back to live.

- [ ] **Step 3: Keep provider behavior unchanged in `live` mode**

`live` mode must remain a thin pass-through to the current provider behavior so acceptance/smoke flows do not regress.

- [ ] **Step 4: Add gateway tests**

Cover:

- replay hit does not call provider
- replay miss fails clearly in strict mode
- record mode writes both raw and normalized cassettes
- live mode bypasses cassette storage unless explicitly recording

**Success standard:** replay behavior is fully testable in isolation and provider fallback rules are explicit.

---

## Task 3: Wire Optimize-Stage Candidate Generation Through Replay

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/optimize.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/optimizer_sql.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`

- [ ] **Step 1: Build a stable optimize replay request payload**

At the optimize boundary, create a request object containing the fields used by the fingerprint and cassette record logic.

- [ ] **Step 2: Route `_execute_llm_with_retry()` through the gateway**

Only replace the direct `generate_llm_candidates(...)` call. Do not rewrite the surrounding retry, validation, or feedback logic in this task.

- [ ] **Step 3: Preserve output contracts**

The following outputs must keep their current shape:

- `proposals.jsonl`
- `llmTraceRefs`
- optimize verification artifacts
- candidate generation diagnostics

If replay is used, trace metadata should still clearly indicate replay origin, for example:

- `executor = replay`
- `provider = cassette`

without breaking current consumers.

- [ ] **Step 4: Add integration tests around optimize replay**

Assert that:

- optimize can generate proposals in replay mode without a live provider
- replayed outputs still flow through validation and diagnostics exactly as live outputs do
- retry logic is not spuriously triggered on replay hits

**Success standard:** optimize-stage behavior is contract-compatible while no longer requiring a live provider during replay.

---

## Task 4: Record the First Cassette Set for `sample_project`

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/llm_cassettes/optimize/raw/`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/llm_cassettes/optimize/normalized/`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/run_sample_project.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`

- [ ] **Step 1: Add config/env support for LLM replay mode**

Allow scripts to set:

- `llm.mode`
- `llm.cassette_dir`
- `llm.replay_strict`

Prefer environment or config overlays rather than script-specific branching.

- [ ] **Step 2: Record an initial cassette set for `sample_project`**

Use `record` mode to create the first optimize cassette set for the project statements used by:

- family scopes
- `generalization-batch1..7`

Do this once, then treat those cassettes as fixtures.

- [ ] **Step 3: Add script-level replay tests**

Add targeted tests that confirm:

- `run_sample_project.py` can run in replay mode
- `generalization_refresh.py` can run in replay mode
- replay mode does not require a provider in those tests

**Success standard:** the project has a seeded cassette set and the main local driver scripts can consume it.

---

## Task 5: Switch Default Non-Live Paths to Replay and Guard Live Coverage

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/run_sample_project.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/release_acceptance.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/QUICKSTART.md` or relevant docs if needed
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`

- [ ] **Step 1: Make replay the default for generalization/harness developer flows**

For developer-facing script paths used in:

- generalization refresh
- local sample-project runs

default to `replay` unless explicitly overridden.

- [ ] **Step 2: Keep acceptance/live coverage explicit**

Release acceptance and provider smoke flows must stay live or record-enabled by explicit choice. Do not silently downgrade those to replay.

- [ ] **Step 3: Document the operating model**

Document:

- when to use `live`
- when to use `record`
- when to use `replay`
- how to refresh cassettes after prompt/provider changes

- [ ] **Step 4: Verify the speed path**

Run the targeted script/test slice in replay mode and confirm it no longer depends on a live provider for optimize-stage logic coverage.

**Success standard:** day-to-day development uses replay by default, while live coverage remains intentional and isolated.

---

## Task 6: Final Verification and Guardrails

**Files:**
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_llm_cassette.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_llm_replay_gateway.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`

- [ ] **Step 1: Run the replay-focused targeted suite**

Suggested targeted suite:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_llm_cassette.py \
  tests/unit/sql/test_llm_replay_gateway.py \
  tests/unit/verification/test_verification_stage_integration.py \
  tests/ci/test_run_sample_project_script.py \
  tests/ci/test_generalization_refresh_script.py
```

- [ ] **Step 2: Run a replay-mode sample-project smoke**

Run the minimal `sample_project` scope in replay mode and confirm it succeeds without live provider dependency.

- [ ] **Step 3: Run full pytest only after the replay lane is green**

```bash
python3 -m pytest -q
```

- [ ] **Step 4: Record residual risks**

If anything remains intentionally live-only, document it explicitly so later work does not assume it is already replay-safe.

**Success standard:** replay-mode optimize coverage is proven, full test suite remains green, and residual live-only areas are explicitly documented.

---

## Non-Goals

This program does **not**:

- add replay support for validate-stage LLM semantic checks
- add replay support for patch-generate LLM assist
- redesign optimize prompts
- change current candidate-selection or convergence semantics
- silently rewrite old run artifacts into cassette fixtures

---

## Exit Criteria

This program is complete when all of the following are true:

- optimize-stage LLM candidate generation supports `live`, `record`, and `replay`
- replay uses stable fingerprinted cassettes, not ad-hoc `sqlKey` cache hits
- `sample_project` and generalization developer flows can run without a live provider
- replay misses fail loudly and predictably
- acceptance/live-provider flows remain explicit
- full pytest passes after integration
