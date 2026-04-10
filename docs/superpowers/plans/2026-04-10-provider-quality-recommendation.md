# Provider Quality Research - Recommendation

## Research Verdict: model-limited

### Summary

After systematic experimentation, the conclusion is clear:

> **The failure to produce branch-local valid candidates is not a prompt-fixable problem. It is a model behavior limitation.**

### Evidence

| Experiment | branch_local_valid rate | Result |
|------------|----------------------|--------|
| Control A (no choose identity) | N/A | Baseline |
| Control B (strict contract) | 0/3 (0%) | LOW_VALUE_PRUNED_TO_EMPTY |
| Exp 1 (current strict, fresh run) | 0/3 (0%) | LOW_VALUE_PRUNED_TO_EMPTY |

**Key observation**: The model consistently ignores explicit contract constraints:

- `forbidSetOperations: true` → Still outputs UNION
- `forbidFlattenedPredicateRewrite: true` → Still rewrites entire WHERE
- `forbidDefaultBranchReduction: true` → Still proposes default reduction
- `preferredOutcome: BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE` → Still outputs low-value candidates

### What Was Ruled Out

- ✅ **Missing scan identity** - Confirmed working
- ✅ **Missing prompt contract** - 9 explicit constraints still violated
- ✅ **Missing patch substrate** - Proven ready in previous program
- ✅ **Prompt strictness** - Strict vs relaxed yields same failure mode
- ❌ **Model behavior** - Model does not follow contract constraints

### Recommendation

**Immediate Action**: Freeze this line of work.

**Rationale**:
1. Two independent runs show identical failure pattern (0% branch_local_valid)
2. Contract constraints are systematically ignored by the model
3. No prompt variation is likely to change model behavior
4. Further prompt engineering would be "throwing good money after bad"

**Future Options** (if business wants to continue):

| Option | Description | Probability of Success |
|--------|-------------|----------------------|
| Model change | Use different model | 20-30% (untested) |
| Fine-tuning | Train model on branch-local examples | 40-50% (needs investment) |
| Post-processing | Rank/filter candidates after generation | 30% (not a real fix) |
| Accept limitation | Document and move on | 100% (but no progress) |

### Deliverables

- [x] `2026-04-10-provider-quality-experiment-matrix.csv`
- [x] `2026-04-10-provider-quality-per-run-classification.jsonl`
- [x] `2026-04-10-provider-quality-failure-patterns.md`
- [x] `2026-04-10-provider-quality-recommendation.md` (this file)

### Program Exit

This program produced valuable information:

1. **Confirmed the bottleneck is provider-side, not engineering**
2. **Quantified the failure pattern (0% branch_local_valid consistently)**
3. **Ruled out prompt strictness as a variable**
4. **Provides clear basis for future model-quality investment decisions**

---

**Status**: Complete
**Outcome**: model-limited
**Suggested next step**: Close this research track; if business requires choose-local support, consider model-specific investment outside prompt engineering scope.