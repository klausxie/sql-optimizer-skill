# EXISTS Rewrite Harness Review

- Date: 2026-03-30
- Review Type: patch spec review
- Target Spec: `docs/superpowers/specs/2026-03-28-exists-rewrite-design.md`
- Outcome: changes required during review; spec narrowed to a v1-safe family boundary in the same review cycle

## Completed Checklist

- [x] Boundary contract changed: the review required the spec to narrow v1 from a mixed `EXISTS / NOT EXISTS / JOIN` family into a positive-`EXISTS -> IN` safe family only, with `NOT EXISTS -> NOT IN` and `EXISTS -> JOIN` marked out-of-scope.
- [x] Harness layer proving it now: `L1` proves detection, blocker logic, and safe family gating; `L2` proves ready plus blocked-neighbor fixture coverage and downstream patch or report contracts; `L3` is required before onboarding closes to prove one real workflow slice; `L4` remains the broader regression layer.
- [x] Shared production classifications reused: family readiness, blocker family, and delivery classification should come from production semantics rather than harness-only mappings.
- [x] First artifacts or diagnostics to inspect on failure: `pipeline/validate/acceptance.results.jsonl`, `pipeline/patch_generate/patch.results.jsonl`, `pipeline/verification/ledger.jsonl`, and `overview/report.json`.
- [x] Proof burden is placed at the right layer: yes after the review changes; before the edit, too much safety burden was left to `L1/L2` while `L3` real-workflow proof was only optional.
- [x] Future onboarding or harness updates required: any widening to `NOT EXISTS` or `JOIN` paths, any correlation or placeholder handling change, and any report fields derived from the family must update the harness surface.

## Findings Raised In Review

1. `NOT EXISTS -> NOT IN` was specified as a normal supported path despite incompatible `NULL` semantics.
2. `EXISTS -> JOIN` was treated as in-scope without a contract for duplicate or cardinality safety.
3. `L3 Scoped Workflow Harness` was only a "should", which allowed onboarding to pass without any required real workflow proof.

## Review-Driven Changes

1. The spec status was annotated to show that the 2026-03-30 harness review narrowed the v1 boundary.
2. `2.1` and `2.3` now define a positive-`EXISTS -> IN` family and explicitly exclude `NOT EXISTS -> NOT IN` and `EXISTS -> JOIN`.
3. The safety section now blocks negated `EXISTS` and unsafe projection keys instead of describing broader rewrite paths.
4. Test design, risk mitigation, and acceptance criteria now require blocked or out-of-scope coverage for the excluded paths.
5. The `Harness Plan` now requires `L3` scoped workflow proof before family onboarding closes.

## Why This Is A Useful Sample

This review shows the intended harness engineering behavior:

1. the checklist is answered concretely rather than referenced abstractly
2. findings are framed in terms of boundary contracts and proof burden, not just missing tests
3. the spec is narrowed until the family boundary matches the harness that can actually prove it
4. workflow-level proof is required before onboarding closes when local and synthetic proof are not enough
