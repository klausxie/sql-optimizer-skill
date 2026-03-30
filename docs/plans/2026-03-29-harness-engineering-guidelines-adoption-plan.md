# Harness Engineering Guidelines Adoption Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the new harness engineering guideline in the `patch` subsystem by making harness layers, proof obligations, artifact checks, and rollout expectations explicit in patch-facing specs and review surfaces before any broader implementation rollout.

**Architecture:** Treat the guideline as a governing design document, then thread it into patch-specific design and review entry points. The rollout should first normalize terminology and required sections in patch specs, then add a reusable patch `Harness Plan` template, and finally define an explicit adoption checklist for future patch-family onboarding and workflow refactors.

**Tech Stack:** Markdown specs and plans, existing patch subsystem docs under `docs/designs/patch/` and `docs/governance/harness/`, patch fixture/workflow harness concepts already present in the repository

---

### Task 1: Map the patch-spec adoption surface

**Files:**
- Modify: `docs/governance/harness/guidelines.md`
- Review: `docs/designs/patch/2026-03-25-patch-system-design.md`
- Review: `docs/project/10-sql-patchability-architecture.md`
- Review: patch-related specs under `docs/designs/patch/2026-03-26-*` to `2026-03-28-*`

- [ ] **Step 1: Write the failing documentation checklist**

```md
- patch specs must define explicit L1-L4 harness layers
- patch specs must name required artifacts
- patch specs must identify shared classification logic
- patch specs must state scoped vs full workflow expectations
```

- [ ] **Step 2: Run the checklist against current patch specs**

Run: `rg -n "Harness Plan|L1|L2|L3|L4|shared classification|Artifacts And Diagnostics|Execution Budget" docs/designs/patch docs/governance/harness docs/project/10-sql-patchability-architecture.md`
Expected: missing or inconsistent coverage across current patch specs.

- [ ] **Step 3: Add an adoption-surface section to the guideline spec**

```md
## Patch Adoption Surface

The first rollout updates:
1. patch-system design
2. patchability architecture summary
3. family onboarding specs going forward
```

- [ ] **Step 4: Re-run the checklist search**

Run: `rg -n "Patch Adoption Surface|Harness Plan|L1|L2|L3|L4" docs/governance/harness/guidelines.md`
Expected: the governing guideline now explicitly identifies the first patch adoption surface.

- [ ] **Step 5: Commit**

```bash
git add docs/governance/harness/guidelines.md
git commit -m "docs: define patch harness adoption surface"
```

### Task 2: Add a reusable patch Harness Plan template

**Files:**
- Create: `docs/governance/harness/templates/patch-harness-plan-template.md`
- Modify: `docs/governance/harness/guidelines.md`

- [ ] **Step 1: Write the failing template expectations**

```md
Required headings:
- Proof Obligations
- Harness Layers
- Shared Classification Logic
- Artifacts And Diagnostics
- Execution Budget
- Regression Ownership
```

- [ ] **Step 2: Verify the template file does not yet exist**

Run: `test -f docs/governance/harness/templates/patch-harness-plan-template.md`
Expected: non-zero exit because the template has not been created yet.

- [ ] **Step 3: Create the minimal reusable template**

```md
## Harness Plan

### Proof Obligations
### Harness Layers
#### L1 Unit Harness
#### L2 Fixture / Contract Harness
#### L3 Scoped Workflow Harness
#### L4 Full Workflow Harness
### Shared Classification Logic
### Artifacts And Diagnostics
### Execution Budget
### Regression Ownership
```

- [ ] **Step 4: Reference the template from the guideline spec**

```md
Patch-facing specs should start from `docs/governance/harness/templates/patch-harness-plan-template.md`.
```

- [ ] **Step 5: Validate the template headings**

Run: `rg -n "^## Harness Plan|^### Proof Obligations|^#### L1 Unit Harness|^#### L4 Full Workflow Harness|^### Regression Ownership" docs/governance/harness/templates/patch-harness-plan-template.md`
Expected: all required headings are present exactly once.

- [ ] **Step 6: Commit**

```bash
git add docs/governance/harness/templates/patch-harness-plan-template.md docs/governance/harness/guidelines.md
git commit -m "docs: add patch harness plan template"
```

### Task 3: Normalize the patch system design onto the new harness model

**Files:**
- Modify: `docs/designs/patch/2026-03-25-patch-system-design.md`

- [ ] **Step 1: Write the failing structural expectation**

```md
The patch system design must include a `Harness Plan` section aligned with the repository guideline.
```

- [ ] **Step 2: Confirm the section is absent**

Run: `rg -n "^## Harness Plan|^### Proof Obligations|^### Harness Layers" docs/designs/patch/2026-03-25-patch-system-design.md`
Expected: no matching section in the current document.

- [ ] **Step 3: Add a patch-specific Harness Plan section**

```md
## Harness Plan

### Proof Obligations
- patch target uniqueness
- replay proof
- syntax proof
- applicability proof
- report aggregation consistency
```

- [ ] **Step 4: Fill in L1-L4 patch harness layers using current repository reality**

```md
#### L1 Unit Harness
- patch decision engine
- replay and formatting proofs

#### L2 Fixture / Contract Harness
- fixture scenario matrix
- patch/report aggregate assertions

#### L3 Scoped Workflow Harness
- selected SQL workflow slices

#### L4 Full Workflow Harness
- full fixture-project golden baselines
```

- [ ] **Step 5: Re-run the structural check**

Run: `rg -n "^## Harness Plan|^### Shared Classification Logic|^### Artifacts And Diagnostics|^### Execution Budget|^### Regression Ownership" docs/designs/patch/2026-03-25-patch-system-design.md`
Expected: all required sections are present.

- [ ] **Step 6: Commit**

```bash
git add docs/designs/patch/2026-03-25-patch-system-design.md
git commit -m "docs: add patch harness plan to patch system design"
```

### Task 4: Align patchability architecture documentation with the harness stack

**Files:**
- Modify: `docs/project/10-sql-patchability-architecture.md`

- [ ] **Step 1: Write the failing doc expectation**

```md
The architecture summary must identify which current artifacts and harness layers prove the patch chain.
```

- [ ] **Step 2: Confirm the current summary stops short of an explicit harness stack**

Run: `rg -n "Harness|L1|L2|L3|L4|scoped workflow|full workflow" docs/project/10-sql-patchability-architecture.md`
Expected: little or no explicit harness-stack terminology.

- [ ] **Step 3: Add a short section mapping architecture layers to harness layers**

```md
## Harness Mapping

1. Unit harnesses prove internal engines and proof helpers
2. Fixture harnesses prove contract alignment
3. Scoped workflow harnesses prove selected real runs
4. Full workflow harnesses govern broad regression
```

- [ ] **Step 4: Add the artifact comparison surface explicitly**

```md
Primary artifact surfaces:
1. acceptance.results.jsonl
2. patch.results.jsonl
3. verification/ledger.jsonl
4. report.json
```

- [ ] **Step 5: Re-run the grep check**

Run: `rg -n "Harness Mapping|scoped workflow|full workflow|acceptance.results.jsonl|patch.results.jsonl|report.json" docs/project/10-sql-patchability-architecture.md`
Expected: the summary now exposes the harness model and artifact surfaces.

- [ ] **Step 6: Commit**

```bash
git add docs/project/10-sql-patchability-architecture.md
git commit -m "docs: map patchability architecture to harness stack"
```

### Task 5: Define the review-time adoption checklist for patch work

**Files:**
- Create: `docs/governance/harness/templates/patch-harness-review-checklist.md`
- Modify: `docs/governance/harness/guidelines.md`

- [ ] **Step 1: Write the failing checklist expectation**

```md
Patch reviews need a short, reusable checklist instead of ad-hoc prose.
```

- [ ] **Step 2: Verify no dedicated checklist file exists**

Run: `test -f docs/governance/harness/templates/patch-harness-review-checklist.md`
Expected: non-zero exit because the checklist file is missing.

- [ ] **Step 3: Create the checklist**

```md
1. What boundary contract changed?
2. Which harness layer proves it?
3. Which classifications must reuse production logic?
4. Which artifacts should fail triage inspect?
5. Is the proof burden at the right layer?
6. What future onboarding must update this harness?
```

- [ ] **Step 4: Reference the checklist from the guideline spec**

```md
Patch design and review should use `patch-harness-review-checklist.md`.
```

- [ ] **Step 5: Validate the checklist contents**

Run: `rg -n "^1\\. What boundary contract changed\\?|^6\\. What future onboarding must update this harness\\?" docs/governance/harness/templates/patch-harness-review-checklist.md`
Expected: both the opening and closing checklist questions are present.

- [ ] **Step 6: Commit**

```bash
git add docs/governance/harness/templates/patch-harness-review-checklist.md docs/governance/harness/guidelines.md
git commit -m "docs: add patch harness review checklist"
```

### Task 6: Verify the documentation adoption slice

**Files:**
- Verify only

- [ ] **Step 1: Run the focused grep-based validation for all new sections and templates**

Run: `rg -n "Harness Plan|Harness Mapping|Patch Adoption Surface|patch-harness-plan-template|patch-harness-review-checklist" docs/designs/patch docs/governance/harness docs/project/10-sql-patchability-architecture.md`
Expected: all newly added adoption surfaces and templates are discoverable from the docs tree.

- [ ] **Step 2: Run a markdown lint or structural sanity pass if the repository already has one**

Run: `python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_patch_decision_core.py`
Expected: unrelated patch harness tests remain green, proving the docs-only rollout did not accidentally disturb implementation.

- [ ] **Step 3: Review residual gaps and explicitly list deferred hard gates**

```md
Deferred:
1. CI lane policy
2. repo-wide rollout beyond patch
3. full workflow harness budgets as hard requirements
```
