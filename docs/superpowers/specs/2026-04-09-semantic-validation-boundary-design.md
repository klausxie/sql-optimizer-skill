# Semantic/Validation Boundary Design

## Goal

Define the next post-safe-baseline stage around one bounded product question:

> are the remaining semantic and validation blockers true product boundaries, or are some of them weaknesses in comparator/validator policy that should be clarified or narrowed?

This stage is not about opening new patch families.

It is about deciding whether current `SEMANTIC_PREDICATE_CHANGED`, `VALIDATE_SEMANTIC_ERROR`, and `VALIDATE_STATUS_NOT_PASS` tails are:

- honest final boundaries
- overly broad comparator results
- or validator policy/reporting buckets that should be made more explicit

## Why This Stage Comes Next

The safe-baseline stage is complete:

- choose-aware: re-deferred
- collection-predicate: deferred
- fragment/include: frozen

That means the project is no longer dominated by `NO_SAFE_BASELINE_*` ambiguity.

The remaining high-signal uncertainty is now concentrated in semantic/validation blockers:

- `SEMANTIC_PREDICATE_CHANGED`
- `VALIDATE_SEMANTIC_ERROR`
- `VALIDATE_STATUS_NOT_PASS`

If these are not reviewed now, future capability work will keep colliding with the same unresolved semantic boundary.

## Primary Sentinels

### 1. Semantic predicate canary

- `demo.order.harness.listOrdersWithUsersPaged`

Current truth:

- `MANUAL_REVIEW / SEMANTIC_PREDICATE_CHANGED`

This statement represents the most important “semantic drift vs comparator weakness” question.

### 2. Validate semantic canary

- `demo.test.complex.includeNested`

Current truth:

- `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`

This statement represents nested-include validation behavior that must not be widened accidentally.

### 3. Validate status canary

- `demo.user.findUsers`

Current truth:

- `MANUAL_REVIEW / VALIDATE_STATUS_NOT_PASS`

This statement represents the `${}` / risky substitution path and should remain a hard boundary unless the product scope changes.

## Guardrail Sentinels

- `demo.test.complex.chooseBasic`
  - semantic-risk choose guardrail; must remain blocked
- `demo.test.complex.chooseMultipleWhen`
  - semantic-risk choose guardrail; must remain blocked
- `demo.test.complex.fragmentMultiplePlaces`
  - validate-status guardrail; should not be softened into a semantic/comparator lane
- `demo.test.complex.leftJoinWithNull`
  - unsupported-strategy guardrail; must not drift into semantic allowance
- `demo.test.complex.existsSubquery`
  - unsupported-strategy guardrail; should stay outside semantic promotion

## Design Decision

Use a **boundary-clarification program**, not a capability program.

This stage should:

- clarify remaining semantic/validation truths
- split generic reasons only when the split is product-useful
- preserve existing blocked boundaries
- avoid any attempt to auto-patch semantic-risk statements

This stage should not:

- create new patch families
- widen patch surfaces
- flatten dynamic templates
- weaken validator rules just to reduce blocked counts

## Approaches Considered

### Approach 1: Keep current semantic/validation tails as-is

Pros:

- zero engineering risk
- no new behavior

Cons:

- leaves a large product question unanswered
- keeps comparator/validator weaknesses indistinguishable from intentional policy

### Approach 2: Clarify semantic and validation tails without widening patchability

Pros:

- converts remaining ambiguity into explicit product truth
- keeps safety intact
- fits current project phase

Cons:

- may not increase `AUTO_PATCHABLE`
- mostly improves honesty and operational clarity

### Approach 3: Try to promote semantic/validation tails directly

Pros:

- best-case immediate green movement

Cons:

- wrong phase
- high risk of accidental semantic widening
- would reintroduce exploratory behavior the project just eliminated

## Recommended Approach

**Approach 2**

The next stage should explicitly answer:

- is `listOrdersWithUsersPaged` a real semantic boundary?
- is `includeNested` a real validation/semantic boundary?
- is `findUsers` a hard validator/non-goal boundary?

If the answer is yes, freeze them more honestly.
If the answer is no, narrow the blocker meaning without changing patchability.

## Expected Output

At the end of this stage:

- semantic/validation sentinels have explicit final truth
- unsupported-strategy and choose guardrails remain blocked
- the project can move on without pretending semantic tails are “almost supported”
