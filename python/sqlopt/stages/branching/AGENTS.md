# AGENTS.md - branching/

**OVERVIEW:** Expands MyBatis XML dynamic SQL tags (`<if>`, `<choose>`, `<foreach>`, `<bind>`, `<include>`) into concrete executable SQL branches for analysis.

## STRUCTURE

```
branching/
├── sql_node.py              # SqlNode ABC + 12 implementations (IfSqlNode, ChooseSqlNode, etc.)
├── xml_script_builder.py    # Parses XML into SqlNode tree (mirrors MyBatis XMLScriptBuilder)
├── xml_language_driver.py  # Entry point: XMLLanguageDriver.create_sql_source()
├── branch_generator.py      # Main class: generates all SQL branch combinations
├── branch_context.py        # Tracks active conditions, bindings, path during generation
├── branch_validator.py      # Deduplicates + validates rendered SQL (empty IN, malformed)
├── branch_strategy.py       # Strategy pattern: AllCombinations, EachCondition, Boundary, LadderSampling
├── dimension_extractor.py   # Extracts BranchDimension from SqlNode tree for planning
├── planner.py               # RiskGuidedLadderPlanner: budget-aware branch selection
├── risk_scorer.py           # SQLDeltaRiskScorer: delegates to RiskRuleRegistry
├── dynamic_context.py       # DynamicContext: bindings + SQL fragment accumulator
├── expression_evaluator.py # OGNL expression evaluation
├── fragment_registry.py     # FragmentRegistry: resolves <include refid="...">
├── mutex_branch_detector.py # Detects mutually exclusive branch conditions
└── strategies/
    ├── __init__.py         # AllCombinationsStrategy, EachConditionStrategy, BoundaryStrategy
    └── (strategies duplicated in branch_strategy.py root)
```

## WHERE TO LOOK

| Task | File | Key Class/Function |
|------|------|-------------------|
| Add new SqlNode type | `sql_node.py` | Subclass `SqlNode`, implement `apply(DynamicContext)` |
| Parse new XML tag | `xml_script_builder.py` | Add entry to `NODE_HANDLER_MAP` |
| New generation strategy | `branch_strategy.py` | Subclass `BranchGenerationStrategy` |
| Risk detection logic | `risk_scorer.py` | Delegates to `RiskRuleRegistry.evaluate_phase1/phase2` |
| Ladder planning | `planner.py` + `dimension_extractor.py` | `RiskGuidedLadderPlanner`, `BranchDimension` |

## KEY CONCEPTS

- **SqlNode tree**: Parsed representation of MyBatis dynamic SQL, each node knows how to render itself
- **Branch**: One concrete SQL variant resulting from specific condition TRUE/FALSE assignments
- **Mutex detection**: `ChooseSqlNode` branches are mutually exclusive (only one when fires)
- **Risk flags**: `prefix_wildcard`, `suffix_wildcard_only`, `concat_wildcard`, `function_wrap`
- **Strategies**: `all_combinations` (2^n), `each` (n), `boundary` (2), `ladder` (risk-weighted sampling)

## CONVENTIONS

- SqlNode `apply()` appends SQL to `DynamicContext.sql_fragments` via `context.append_sql()`
- Strategies return `List[List[str]]`: outer = branches, inner = conditions activated per branch
- Branch context tracks `current_path` as `">"` joined node stack for debugging
