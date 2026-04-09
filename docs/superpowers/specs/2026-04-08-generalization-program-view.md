# Generalization Program View Spec

Goal: turn `generalization_summary.py` into the primary decision view for the stabilization program while preserving statement-level detail.

This view must:
- keep per-statement rows intact
- expose overall metrics for ready/blocked balance
- group blocker reasons into a small, stable decision set
- present a short text conclusion for human decision-making

Required blocker buckets:
- `NO_PATCHABLE_CANDIDATE_SELECTED`
- `SEMANTIC_GATE_NOT_PASS`
- `VALIDATE_STATUS_NOT_PASS`
- `SHAPE_FAMILY_NOT_TARGET`
- `OTHER`

Required overall metrics:
- `auto_patchable_rate`
- `blocked_statement_count`

The textual view should end with a short conclusion block that identifies:
- the current `decision_focus`
- the `recommended_next_step`

The command must continue to accept multiple `--batch-run` inputs and must still report statement-level rows, patch presence, and raw blocker reasons.

Current deliberate `SHAPE_FAMILY_NOT_TARGET` boundary program:
- `keep_blocked`
  - `PLAIN_FOREACH_INCLUDE_PREDICATE`: plain `include + where + foreach IN (...)` statements
  - `AMBIGUOUS_FRAGMENT_CHAIN`: fragment chains that can render unstable SQL text such as `WHERE WHERE ...`
- `promote_next`
  - `CHOOSE_GUARDED_FILTER_EXTENSION`: choose-guarded dynamic filters that are close to the existing `IF_GUARDED_FILTER_STATEMENT` family

Current `generalization-batch5` candidate pool:
- `demo.user.advanced.findUsersByKeyword`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
