# Dynamic Filter Envelope Cleanup Design

## Status

- Date: 2026-03-27
- Updated: 2026-03-30
- Scope: harness-aligned design (收敛到 O1-O9 boundary contracts)
- Goal: onboard two dynamic safe-baseline families through the patch family onboarding framework without widening dynamic subtree rewrite scope

## Goal

Onboard two dynamic envelope cleanup families through the patch family onboarding framework:

1. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
2. `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`

The target is not generic dynamic SQL rewriting. The target is a narrow, high-correctness path for dynamic statements whose dynamic behavior remains fully preserved while only the static envelope is cleaned up.

## Non-Goals

This design does not attempt to:

1. rewrite `<if>` predicates
2. reorder dynamic nodes
3. support `<choose>`, `<bind>`, `<foreach>`, or `<set>`
4. support join alias cleanup
5. expand into generic `DYNAMIC_FILTER_SUBTREE` rewriting

---

## Boundary Contracts (O1-O9)

### O1: Shared Obligations Contract (L1)

Both families must share the same acceptance / replay / verification / fixture obligations:

**Acceptance:**
- `semantic_required_status: "PASS"`
- `semantic_min_confidence: "HIGH"`

**Replay:**
- `requires_replay_contract: true`
- `required_template_ops: ["replace_statement_body"]`
- `render_mode: "STATEMENT_TEMPLATE_SAFE"`

**Verification:**
- `require_replay_match: true`
- `require_xml_parse: true`
- `require_render_ok: true`
- `require_sql_parse: true`
- `require_apply_check: true`

**Fixture Obligations:**
- `ready_case_required: true`
- `blocked_neighbor_required: true`
- `replay_assertions_required: true`
- `verification_assertions_required: true`

**Proof (L1)**: Verify both family specs contain identical obligations configuration.

---

### O2: Family-Specific Scope Contract (L1)

Each family has independent scope, classifier, and blocked neighbors:

**SELECT_LIST_CLEANUP:**
- Scope: clean static projection aliases outside dynamic `<where>/<if>` tree
- Allowed: `col AS col`
- Blocked: `u.col AS col`, expression aliases, constant aliases, aggregate aliases
- Classifier: has_select_list_redundant_aliases + IF_GUARDED_FILTER_STATEMENT shape

**FROM_ALIAS_CLEANUP:**
- Scope: clean static FROM aliases around dynamic `<where>/<if>` tree
- Allowed: single-table alias cleanup, subquery shell alias
- Blocked: join alias cleanup, requires rewriting `<if>` predicate references
- Classifier: has_from_alias_redundancy + IF_GUARDED_FILTER_STATEMENT shape

**Proof (L1)**: Unit tests verify classifiers return correct results for respective family-specific inputs.

---

### O3: Combined Case Exclusion Contract (L1)

If a candidate requires BOTH select-list cleanup AND from-alias cleanup, it MUST be blocked with an explicit reason code. It MUST NOT heuristically choose one family.

**Combined Case Definition:**
- Input: sql_unit that needs both:
  - has_select_list_redundant_aliases
  - has_from_alias_redundancy
  - is_if_guarded_filter_shape

**Required Output:**
- `blocked = true`
- `emits explicit blocker (non-heuristic fallback)`

**Forbidden Output:**
- `family = "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"` (or FROM_ALIAS)
- automatically choosing one family without blocking

**Design Change Required**: Need to add combined-case blocker reason code to production if not exists.

**Proof (L1)**: Unit tests construct combined case, verify it's blocked and does not fall into either family.

---

### O4: Blocker Selection Contract (L1)

Blockers must emit for:
- SELECT_LIST: non-trivial aliases (qualified, expression, constant, aggregate)
- FROM_ALIAS: requires rewrite `<if>` predicate references, or join alias
- COMBINED: requires both cleanups

After blocker emits:
- `delivery_class` must reuse existing production classification semantics (no fixture-only semantics)
- `reason_code` must be explicit, non-fallback

**Proof (L1)**: Unit tests verify blocker emission logic returns correct reason codes.

---

### O5: Persisted Reason Code Contract (L2)

Blocked rows in `acceptance.results.jsonl` must contain:
- `reason_code`: explicit blocker reason
- `reason_code` must be in known blocker set (non-generic/unknown)

Reason codes:
- Reuse existing: `DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS`, `DYNAMIC_FILTER_FROM_ALIAS_REQUIRES_PREDICATE_REWRITE`
- Or new: combined case needs production reason code (design change)

**Proof (L2)**: Fixture harness reads acceptance.results.jsonl, verifies blocked rows have explicit reason_code.

---

### O6: Persisted Delivery Class Contract (L2)

Blocked rows in `acceptance.results.jsonl` must contain:
- `delivery_class`: reuse existing production delivery_class semantics
- `delivery_class` must NOT be: `"SAFE_BASELINE_AUTO_PATCH"`, `"SAFE_BASELINE_DELIVERED"`

**Design Constraint**: delivery_class must reuse existing production semantics, cannot create new fixture-only classification.

**Proof (L2)**: Fixture harness reads acceptance.results.jsonl, verifies blocked rows have correct delivery_class.

---

### O7: No-Fallback-to-Generic Contract (L2)

Blocked cases must satisfy:
- `family` NOT in `GENERIC_DYNAMIC_FAMILIES`
- Where `GENERIC_DYNAMIC_FAMILIES = {"DYNAMIC_FILTER_SUBTREE", "DYNAMIC_SUBTREE_REWRITE"}`

Blocked cases can only be:
- Explicit blocker classification
- REVIEW classification
- Explicit non-auto-patch classification

**Proof (L2)**: Fixture harness verifies blocked cases do not fall back to generic family.

---

### O8: Ready/Blocked Artifact Contract (L2)

**READY_CASE must exist in:**
- `acceptance.results.jsonl`: status=PASS, family=target family
- `patch.results.jsonl`: patch_strategy=target strategy
- `verification/ledger.jsonl`: verification checks pass

**BLOCKED_NEIGHBOR must exist in:**
- `acceptance.results.jsonl`: contains explicit reason_code
- Must NOT exist in `patch.results.jsonl` (no patch generated)

**Proof (L2)**: Fixture harness cross-validates multi-stage artifact consistency.

---

### O9: Real Workflow Proof Contract (L3) - REQUIRED

L3 must prove:
- At least one SQL key passes through scan → optimize → validate → patch → verification → report
- Classification result correct in acceptance
- Patch generated successfully
- Verification chain all passed

**This is REQUIRED proof. Family cannot transition from FROZEN_AUTO_PATCH to formal status without passing L3.**

**Proof (L3)**: Run real workflow, verify end-to-end.

---

## Harness Plan

### Proof Obligations with Layer Mapping

| ID | Obligation | Layer | Proof Target |
|----|------------|-------|--------------|
| O1 | Shared Obligations | L1 | Two family specs have identical obligations |
| O2 | Family-Specific Scope | L1 | Classifier returns correct results for respective inputs |
| O3 | Combined Case Exclusion | L1 | Combined case blocked, does not fall into either family |
| O4 | Blocker Selection | L1 | Blocker emits correct reason codes |
| O5 | Persisted Reason Code | L2 | acceptance.jsonl blocked rows have explicit reason_code |
| O6 | Persisted Delivery Class | L2 | acceptance.jsonl blocked rows have correct delivery_class |
| O7 | No-Fallback-to-Generic | L2 | Blocked cases do not fall into generic family |
| O8 | Ready/Blocked Artifact | L2 | Multi-stage artifacts consistency |
| O9 | Real Workflow Proof | L3 | Real workflow end-to-end passes |

### L1 Unit Harness (Required on PR)

- **Goal**: Prove shared obligations alignment, family-specific classifier, combined case exclusion, blocker selection
- **Scope**: Synthetic SQL units with controlled dynamic features
- **Allowed Mocks**: Synthetic inputs acceptable
- **Artifacts Checked**: In-memory family classification results, reason code emission
- **Budget**: <10s

### L2 Fixture / Contract Harness (Required on PR)

- **Goal**: Prove persisted reason_code, persisted delivery_class, no-fallback-to-generic, ready/blocked artifact contract
- **Scope**: Fixture scenarios, acceptance/patch/verification artifacts
- **Allowed Mocks**: Synthetic validate evidence allowed when proving contract alignment
- **Artifacts Checked**:
  - `tests/fixtures/project/fixture_scenarios.json`
  - `pipeline/validate/acceptance.results.jsonl`
  - `pipeline/patch_generate/patch.results.jsonl`
  - `pipeline/verification/ledger.jsonl`
  - `overview/report.json`
- **Budget**: <60s

### L3 Scoped Workflow Harness (REQUIRED before family closes)

- **Goal**: Prove real workflow end-to-end for at least one SQL key per family
- **Scope**: One SQL key representing IF_GUARDED_FILTER_STATEMENT shape
- **Allowed Mocks**: Infrastructure availability patches only
- **Artifacts Checked**: Full run outputs across all stages
- **Budget**: <180s
- **Status**: REQUIRED - family cannot close without L3 proof

### L4 Full Workflow Harness

- **Goal**: Prove dynamic envelope onboarding does not destabilize broader patch portfolio
- **Scope**: Full fixture-project regression
- **Allowed Mocks**: Only workflow-stability patches that preserve patch semantics
- **Artifacts Checked**: Full run outputs and report summaries
- **Budget**: Separately governed

### Execution Budget (Required)

| Scope | Layers | Max Runtime | Trigger |
|-------|--------|------------|---------|
| **PR** | L1 + L2 | <60s | Every PR |
| **Integration** | L1 + L2 + L3 | <180s | **Required before family closes** |
| **Full Regression** | L4 | Separately governed | Nightly |

### Shared Classification Logic

- **Dynamic Baseline Family**: Must reuse production semantics from `patch_families/registry.py`
- **Delivery Class**: Must derive from family spec's delivery_class or fallback logic (no fixture-only semantics)
- **Blocker Family**: Must reuse production semantics from acceptance-side classification

### Regression Ownership

- O1: Any obligations configuration change
- O2: Any family scope / classifier change
- O3: Classification logic change
- O4: Any reason code change
- O5-O6: Any persisted artifact field change
- O7: Family fallback logic change
- O8: Patch/verification chain change
- O9: Any staged workflow change

---

## Design Changes Required

### 1. Combined Case Blocker Reason Code

If current implementation does not emit explicit blocker for combined cases (select-list + from-alias simultaneously), need to add production reason code:

- **Proposed name**: `DYNAMIC_FILTER_COMBINED_ENVELOPE_NOT_SUPPORTED`
- **Behavior**: Explicit blocker, non-fallback, not auto-patch delivery class

This is a design change - the reason code does not currently exist in production.

---

## Summary of Changes from Original Design

### Deleted Requirements

1. **"DYNAMIC_FILTER_ENVELOPE_SCOPE_MISMATCH" reason code** - Removed as it does not exist in current implementation
2. **Minimum blocked neighbor count (2 per family)** - Changed to "core blocked scenarios coverage" to be more practical
3. **Shared skeleton as implementation detail** - Removed from design, replaced with "shared obligations" behavior contract

### Narrowed Scope

1. **Shared shape gate** - Changed from "single `<where>` containing flat sibling `<if>`" (difficult to verify) to "IF_GUARDED_FILTER_STATEMENT" (existing shape family)
2. **Shared skeleton** - Changed from implementation structure requirement to behavior contract (shared obligations)
3. **Design vs implementation 1:1 alignment** - Changed to harness-provable behavior contracts

### Added as Required Harness Proof

1. **L3 is now REQUIRED** - Before family closes, must have real workflow proof
2. **O1-O9 explicit contracts** - Each obligation now mapped to specific layer
3. **Combined case explicit blocker** - Must block, cannot heuristic choose family
4. **No fallback to generic family** - Must be proven in L2
5. **Delivery class must reuse production semantics** - Explicit constraint, no fixture-only logic