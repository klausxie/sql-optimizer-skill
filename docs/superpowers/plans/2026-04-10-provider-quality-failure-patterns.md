# Top Failure Patterns

## Pattern 1: Set Operations in Branch Rewrite

**Frequency**: 2/3 runs (100% of runs with candidates)

**Description**: Model outputs queries using `UNION ALL` or similar set operations when contract explicitly forbids set operations.

**Example**:
```sql
-- Original branch
name ILIKE #{keywordPattern}

-- Model output (violates contract)
SELECT ... FROM (...) t1
UNION ALL
SELECT ... FROM (...) t2
UNION ALL
SELECT ... FROM (...) t3
```

**Contract violation**:
- `forbidSetOperations: true` (ignored)
- `targetSurface: CHOOSE_BRANCH_BODY` (ignored)
- `branchLocalOnly: true` (ignored)

**Root cause**: Model prioritizes general SQL optimization patterns over contract constraints.

---

## Pattern 2: Flattened Predicate Rewrite

**Frequency**: 2/3 runs

**Description**: Model rewrites the entire WHERE clause instead of isolating the specific branch being rendered.

**Example**:
```sql
-- Expected: only modify branch 0
name ILIKE #{keywordPattern}

-- Model output: rewrites entire WHERE
WHERE (name ILIKE #{keywordPattern} OR status = #{status})
```

**Contract violation**:
- `allowedTemplateRewriteOps: ["replace_choose_branch_body"]` (not followed)
- `preferredOutcome: BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE` (not followed)

**Root cause**: Model treats constraint as general guidance, not strict requirement.

---

## Pattern 3: Canonical Noop / No Change

**Frequency**: 2/3 runs

**Description**: Model returns candidate that is essentially identical to original SQL.

**Example**:
```sql
-- Original
WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED')

-- Model output (identical)
WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED')
```

**Classification**: `low_value` - no material optimization.

---

## Pattern 4: Default Branch Reduction

**Frequency**: 1/3 runs (previous cassette only)

**Description**: Model proposes removing non-default branches entirely, reducing to just the default branch.

**Example**:
```sql
-- Original: 3 branches (2 when + 1 otherwise)
-- Model output: only default branch
WHERE status != 'DELETED'
```

**Contract violation**:
- `forbidDefaultBranchReduction: true` (ignored)

---

## Summary

| Pattern | Frequency | Contract Violation | Model Behavior |
|---------|-----------|-------------------|----------------|
| Set operations | 100% | forbidSetOperations | Ignored |
| Flattened rewrite | 100% | allowedTemplateRewriteOps | Ignored |
| Canonical noop | ~67% | N/A | No improvement |
| Default reduction | ~33% | forbidDefaultBranchReduction | Ignored |

## Key Insight

The model consistently ignores explicit contract constraints regardless of prompt strictness level. This is not a prompt-tuning problem - it's a model behavior limitation.

**Evidence**: Strict contract with 9 explicit constraints still produces the same violation patterns as hypothetical relaxed contract would.