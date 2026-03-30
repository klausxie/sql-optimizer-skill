## Harness Plan

> Review handoff: pair this `Harness Plan` with a completed copy of `docs/governance/harness/templates/patch-harness-review-checklist.md` in the review summary or PR description.

### Proof Obligations

- What boundary contracts must be proven?
- What runtime claims require replay, artifact, or workflow proof?

### Harness Layers

#### L1 Unit Harness

- Goal:
- Scope:
- Allowed Mocks:
- Artifacts Checked:
- Budget:

#### L2 Fixture / Contract Harness

- Goal:
- Scope:
- Allowed Mocks:
- Artifacts Checked:
- Budget:

#### L3 Scoped Workflow Harness

- Goal:
- Scope:
- Allowed Mocks:
- Artifacts Checked:
- Budget:

#### L4 Full Workflow Harness

- Goal:
- Scope:
- Allowed Mocks:
- Artifacts Checked:
- Budget:

### Shared Classification Logic

- Which classifications must reuse production logic?
- Which duplicated mappings, if any, remain temporary exceptions?

### Artifacts And Diagnostics

- Which artifacts are authoritative for this capability?
- Which diagnostics should be inspected first on failure?

### Execution Budget

- What should run in normal PR validation?
- What should run in broader integration validation?
- What is intentionally slower or less frequent?

### Regression Ownership

- Which future families, refactors, or report changes must update this harness?
