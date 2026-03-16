# SQL 优化报告：run_8c1719c37556

## 执行决策
- 发布就绪度：`CONDITIONAL_GO`
- 优化结论：`PARTIAL`
- 证据置信度：`LOW`
- 范围：SQL 单元 `92`, 优化建议 `92`
- 交付快照：补丁 `5`, 可应用 `5`, 阻塞 SQL `29`
- 性能证据：改进 `0`, 未改进 `0`
- 验证状态：已验证 `245`, 部分 `31`, 未验证 `0`
- 物化模式：`{'UNMATERIALIZABLE': 60, 'STATEMENT_TEMPLATE_SAFE': 1, 'STATEMENT_SQL': 30}`
- 物化原因：`{'DYNAMIC_SUBTREE_PRESENT': 60, 'STATEMENT_INCLUDE_SAFE': 1, 'STATIC_STATEMENT': 30}`
- 物化操作：`{'OTHER': 60, 'PATCH_READY': 31}`

## 优先处理的 SQL
| SQL 键 | 优先级 | 可操作性 | 交付状态 | 补丁可应用 | 当前原因 | 摘要 |
|---|---|---|---|---|---|---|
| `com.test.mapper.UserMapper.testReturningSyntax#v77` | `P0` | `HIGH` | `READY_TO_APPLY` | `true` | 这是最快的安全收益，因为补丁已就绪 | patch is ready to apply |
| `com.test.mapper.UserMapper.testStringConcat#v66` | `P0` | `HIGH` | `READY_TO_APPLY` | `true` | 这是最快的安全收益，因为补丁已就绪 | patch is ready to apply |
| `com.test.mapper.UserMapper.testStringSubstring#v67` | `P0` | `HIGH` | `READY_TO_APPLY` | `true` | 这是最快的安全收益，因为补丁已就绪 | patch is ready to apply |
| `com.test.mapper.UserMapper.testSubqueryExists#v51` | `P0` | `HIGH` | `READY_TO_APPLY` | `true` | 这是最快的安全收益，因为补丁已就绪 | patch is ready to apply |
| `com.test.mapper.UserMapper.testUnion#v54` | `P0` | `HIGH` | `READY_TO_APPLY` | `true` | 这是最快的安全收益，因为补丁已就绪 | patch is ready to apply |
| `com.test.mapper.UserMapper.testLimit#v71` | `P0` | `HIGH` | `BLOCKED` | `n/a` | 具有强大潜力，但仍需更强的下游验证 | automatic patch generation is blocked by current mapper or candidate shape |
| `com.test.mapper.UserMapper.testLimitOffset#v72` | `P0` | `HIGH` | `BLOCKED` | `n/a` | 具有强大潜力，但仍需更强的下游验证 | automatic patch generation is blocked by current mapper or candidate shape |
| `com.test.mapper.UserMapper.testUnionWithLimit#v82` | `P0` | `HIGH` | `BLOCKED` | `n/a` | 具有强大潜力，但仍需更强的下游验证 | automatic patch generation is blocked by current mapper or candidate shape |
| `com.test.mapper.UserMapper.testBindIf#v21` | `P0` | `MEDIUM` | `PATCHABLE_WITH_REWRITE` | `n/a` | 在模板安全的 mapper 重构后立即成为高价值 | patch can likely land after template-aware mapper refactoring |
| `com.test.mapper.UserMapper.testChooseNestedChoose#v18` | `P0` | `MEDIUM` | `PATCHABLE_WITH_REWRITE` | `n/a` | 在模板安全的 mapper 重构后立即成为高价值 | patch can likely land after template-aware mapper refactoring |

## 主要风险
- `VALIDATE_SEMANTIC_ERROR` (`degradable`): 数量 `28`, 影响 SQL `28`
- `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION` (`degradable`): 数量 `1`, 影响 SQL `1`

## 交付状态
- preflight: `DONE`
- scan: `DONE` (尝试 `1`)
- optimize: `DONE` (尝试 `92`)
- validate: `DONE` (尝试 `92`)
- patch_generate: `DONE` (尝试 `92`)
- report: `DONE`

## 变更组合
| SQL 键 | 状态 | 来源 | 性能 | 物化 | 补丁可应用 | 补丁决策 |
|---|---|---|---|---|---|---|
| `com.test.mapper.UserMapper.testSingleIf#v1` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testTwoIf#v2` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testThreeIf#v3` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testFourIf#v4` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseWhen#v5` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseOtherwise#v6` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testWhereIf#v7` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testSetIf#v8` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testForeachIn#v9` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testTrim#v10` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIfChoose#v11` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testWhereMultipleIf#v12` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseMultipleIf#v13` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIfForeach#v14` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testWhereChooseWhen#v15` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseWithMultipleIf#v16` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testFiveIf#v17` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseNestedChoose#v18` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testComplexConditions#v19` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testDynamicOrderBy#v20` | `NEED_MORE_PARAMS` | `rule` | `未知` | `n/a` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testBindIf#v21` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testTrimPrefixSuffix#v22` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testForeachInsert#v23` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testDynamicColumns#v24` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testChooseTripleNested#v25` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testSetMultipleIf#v26` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIfMultiCondition#v27` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testForeachChoose#v28` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testTrimUpdate#v29` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIfForeachComplex#v30` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIncludeBaseColumns#v31` | `PASS` | `llm` | `未知` | `STATEMENT_TEMPLATE_SAFE` | `n/a` | `PATCH_TEMPLATE_MATERIALIZATION_MISSING` |
| `com.test.mapper.UserMapper.testIncludeCondition#v32` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testMultipleInclude#v33` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testIncludeComplex#v34` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testIncludeInIf#v35` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testIncludeInChoose#v36` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testMultipleBind#v37` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testBindWithInclude#v38` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testEmptyIf#v39` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testOnlyOtherwise#v40` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testNestedTrim#v41` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testNestedForeach#v42` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testIncludeWithProperty#v43` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testLongConditions#v44` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testInsertWithSelectKey#v45` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testInnerJoin#v46` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testLeftJoin#v47` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testMultiTableJoin#v48` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testDynamicJoin#v49` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testSubqueryIn#v50` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testSubqueryExists#v51` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `true` | `PATCH_SELECTED_SINGLE_PASS` |
| `com.test.mapper.UserMapper.testScalarSubquery#v52` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testDynamicMultiTableJoin#v53` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testUnion#v54` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `true` | `PATCH_SELECTED_SINGLE_PASS` |
| `com.test.mapper.UserMapper.testNestedSubquery#v55` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testCountAll#v56` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testCountByStatus#v57` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testSumAmount#v58` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testAvgAmount#v59` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testMaxMinAmount#v60` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testGroupBy#v61` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testMultiGroupBy#v62` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testGroupByHaving#v63` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testCaseWhen#v64` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testDateFunction#v65` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testStringConcat#v66` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `true` | `PATCH_SELECTED_SINGLE_PASS` |
| `com.test.mapper.UserMapper.testStringSubstring#v67` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `true` | `PATCH_SELECTED_SINGLE_PASS` |
| `com.test.mapper.UserMapper.testConditionalSum#v68` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testMultiAggFunction#v69` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testOrderRank#v70` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testLimit#v71` | `NEED_MORE_PARAMS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testLimitOffset#v72` | `NEED_MORE_PARAMS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testDynamicPagination#v73` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testDistinctStatus#v74` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testDistinctMultipleFields#v75` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testInsertOnDuplicateKeyUpdate#v76` | `NEED_MORE_PARAMS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testReturningSyntax#v77` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `true` | `PATCH_SELECTED_SINGLE_PASS` |
| `com.test.mapper.UserMapper.testDistinctWithCondition#v78` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCountDistinct#v79` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testOrderByMultipleWithPagination#v80` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testComplexAggregation#v81` | `PASS` | `llm` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_NO_EFFECTIVE_CHANGE` |
| `com.test.mapper.UserMapper.testUnionWithLimit#v82` | `NEED_MORE_PARAMS` | `rule` | `未知` | `STATEMENT_SQL` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testCrossFileInclude#v83` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCrossFileIncludeWithIf#v84` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testLocalFragmentWithCrossFile#v85` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCrossFileInChoose#v86` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCrossFileWithForeach#v87` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testMultipleCrossFileInclude#v88` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testCrossFileNestedChoose#v89` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCrossFileInTrim#v90` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |
| `com.test.mapper.UserMapper.testCrossFileInSet#v91` | `NEED_MORE_PARAMS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_CONFLICT_NO_CLEAR_WINNER` |
| `com.test.mapper.UserMapper.testChainedCrossFileInclude#v92` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` |

## 优化建议分析
| SQL 键 | 结论 | 问题 | LLM 候选 |
|---|---|---|---|
| `com.test.mapper.UserMapper.testSingleIf#v1` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testTwoIf#v2` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testThreeIf#v3` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testFourIf#v4` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseWhen#v5` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseOtherwise#v6` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testWhereIf#v7` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testSetIf#v8` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testForeachIn#v9` | `CAN_IMPROVE` | `SELECT_STAR,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testTrim#v10` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIfChoose#v11` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testWhereMultipleIf#v12` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseMultipleIf#v13` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIfForeach#v14` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testWhereChooseWhen#v15` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseWithMultipleIf#v16` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testFiveIf#v17` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseNestedChoose#v18` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testComplexConditions#v19` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testDynamicOrderBy#v20` | `CAN_IMPROVE` | `DOLLAR_SUBSTITUTION,SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `0` |
| `com.test.mapper.UserMapper.testBindIf#v21` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testTrimPrefixSuffix#v22` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testForeachInsert#v23` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testDynamicColumns#v24` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testChooseTripleNested#v25` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testSetMultipleIf#v26` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testIfMultiCondition#v27` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testForeachChoose#v28` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testTrimUpdate#v29` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testIfForeachComplex#v30` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeBaseColumns#v31` | `NOOP` | `NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeCondition#v32` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMultipleInclude#v33` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeComplex#v34` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeInIf#v35` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeInChoose#v36` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMultipleBind#v37` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testBindWithInclude#v38` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testEmptyIf#v39` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testOnlyOtherwise#v40` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testNestedTrim#v41` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testNestedForeach#v42` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testIncludeWithProperty#v43` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testLongConditions#v44` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testInsertWithSelectKey#v45` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testInnerJoin#v46` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testLeftJoin#v47` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testMultiTableJoin#v48` | `NOOP` | `NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testDynamicJoin#v49` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testSubqueryIn#v50` | `CAN_IMPROVE` | `SELECT_STAR,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testSubqueryExists#v51` | `CAN_IMPROVE` | `SELECT_STAR` | `1` |
| `com.test.mapper.UserMapper.testScalarSubquery#v52` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testDynamicMultiTableJoin#v53` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testUnion#v54` | `CAN_IMPROVE` | `SELECT_STAR,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testNestedSubquery#v55` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testCountAll#v56` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCountByStatus#v57` | `NOOP` | `NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testSumAmount#v58` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testAvgAmount#v59` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMaxMinAmount#v60` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testGroupBy#v61` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMultiGroupBy#v62` | `NOOP` | `NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testGroupByHaving#v63` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCaseWhen#v64` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testDateFunction#v65` | `CAN_IMPROVE` | `FUNCTION_ON_INDEXED_COL` | `1` |
| `com.test.mapper.UserMapper.testStringConcat#v66` | `CAN_IMPROVE` | `SELECT_STAR,FUNCTION_ON_INDEXED_COL,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testStringSubstring#v67` | `CAN_IMPROVE` | `SELECT_STAR,FUNCTION_ON_INDEXED_COL,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testConditionalSum#v68` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMultiAggFunction#v69` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testOrderRank#v70` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testLimit#v71` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testLimitOffset#v72` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testDynamicPagination#v73` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testDistinctStatus#v74` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testDistinctMultipleFields#v75` | `NOOP` | `NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testInsertOnDuplicateKeyUpdate#v76` | `CAN_IMPROVE` | `SENSITIVE_COLUMN_EXPOSED` | `1` |
| `com.test.mapper.UserMapper.testReturningSyntax#v77` | `CAN_IMPROVE` | `SELECT_STAR,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testDistinctWithCondition#v78` | `NOOP` | `FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testCountDistinct#v79` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testOrderByMultipleWithPagination#v80` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK` | `1` |
| `com.test.mapper.UserMapper.testComplexAggregation#v81` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testUnionWithLimit#v82` | `CAN_IMPROVE` | `SELECT_STAR` | `1` |
| `com.test.mapper.UserMapper.testCrossFileInclude#v83` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileIncludeWithIf#v84` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testLocalFragmentWithCrossFile#v85` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileInChoose#v86` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileWithForeach#v87` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testMultipleCrossFileInclude#v88` | `NOOP` | `FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileNestedChoose#v89` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileInTrim#v90` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |
| `com.test.mapper.UserMapper.testCrossFileInSet#v91` | `NOOP` | `无` | `1` |
| `com.test.mapper.UserMapper.testChainedCrossFileInclude#v92` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |

## 技术证据
- `com.test.mapper.UserMapper.testSingleIf#v1`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testSingleIf#v1/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testTwoIf#v2`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testTwoIf#v2/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testThreeIf#v3`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testThreeIf#v3/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testFourIf#v4`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testFourIf#v4/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testChooseWhen#v5`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testChooseWhen#v5/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testChooseOtherwise#v6`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testChooseOtherwise#v6/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIfChoose#v11`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIfChoose#v11/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testWhereMultipleIf#v12`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testWhereMultipleIf#v12/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testWhereChooseWhen#v15`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testWhereChooseWhen#v15/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testFiveIf#v17`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testFiveIf#v17/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testChooseNestedChoose#v18`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testChooseNestedChoose#v18/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testComplexConditions#v19`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testComplexConditions#v19/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testBindIf#v21`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testBindIf#v21/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testTrimPrefixSuffix#v22`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testTrimPrefixSuffix#v22/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDynamicColumns#v24`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDynamicColumns#v24/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIfMultiCondition#v27`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIfMultiCondition#v27/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeBaseColumns#v31`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_TEMPLATE_SAFE` / `STATEMENT_INCLUDE_SAFE`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeBaseColumns#v31/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeCondition#v32`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeCondition#v32/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMultipleInclude#v33`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMultipleInclude#v33/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeComplex#v34`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeComplex#v34/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeInIf#v35`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeInIf#v35/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeInChoose#v36`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeInChoose#v36/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMultipleBind#v37`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMultipleBind#v37/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testBindWithInclude#v38`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testBindWithInclude#v38/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testEmptyIf#v39`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testEmptyIf#v39/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testOnlyOtherwise#v40`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testOnlyOtherwise#v40/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testIncludeWithProperty#v43`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testIncludeWithProperty#v43/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testLongConditions#v44`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testLongConditions#v44/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testInnerJoin#v46`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testInnerJoin#v46/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testLeftJoin#v47`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testLeftJoin#v47/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMultiTableJoin#v48`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMultiTableJoin#v48/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDynamicJoin#v49`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDynamicJoin#v49/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testSubqueryExists#v51`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testSubqueryExists#v51/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testScalarSubquery#v52`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testScalarSubquery#v52/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testUnion#v54`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testUnion#v54/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testNestedSubquery#v55`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testNestedSubquery#v55/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCountAll#v56`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCountAll#v56/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCountByStatus#v57`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCountByStatus#v57/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testSumAmount#v58`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testSumAmount#v58/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testAvgAmount#v59`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testAvgAmount#v59/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMaxMinAmount#v60`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMaxMinAmount#v60/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testGroupBy#v61`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testGroupBy#v61/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMultiGroupBy#v62`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMultiGroupBy#v62/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testGroupByHaving#v63`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testGroupByHaving#v63/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCaseWhen#v64`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCaseWhen#v64/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDateFunction#v65`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDateFunction#v65/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testStringConcat#v66`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testStringConcat#v66/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testStringSubstring#v67`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testStringSubstring#v67/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testConditionalSum#v68`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testConditionalSum#v68/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testMultiAggFunction#v69`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testMultiAggFunction#v69/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testOrderRank#v70`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testOrderRank#v70/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDistinctStatus#v74`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDistinctStatus#v74/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDistinctMultipleFields#v75`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDistinctMultipleFields#v75/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testReturningSyntax#v77`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testReturningSyntax#v77/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testDistinctWithCondition#v78`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testDistinctWithCondition#v78/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCountDistinct#v79`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCountDistinct#v79/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testComplexAggregation#v81`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`STATEMENT_SQL` / `STATIC_STATEMENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testComplexAggregation#v81/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCrossFileInclude#v83`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCrossFileInclude#v83/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testLocalFragmentWithCrossFile#v85`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testLocalFragmentWithCrossFile#v85/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCrossFileInChoose#v86`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCrossFileInChoose#v86/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCrossFileNestedChoose#v89`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCrossFileNestedChoose#v89/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testCrossFileInTrim#v90`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testCrossFileInTrim#v90/candidate_1/equivalence.json`
- `com.test.mapper.UserMapper.testChainedCrossFileInclude#v92`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_8c1719c37556/evidence/com.test.mapper.UserMapper.testChainedCrossFileInclude#v92/candidate_1/equivalence.json`

## 行动计划（未来 24 小时）
- 后端：移除 ${} 动态 SQL: `rg -n "\$\{" src/main/resources/**/*.xml`
- 平台：恢复运行: `PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id run_8c1719c37556`

## 验证警告
- OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR: 26 sql(s) hit SQL syntax errors during optimize DB evidence collection

## 验证覆盖
- 阶段覆盖：`{'optimize': {'recorded': 92, 'expected': 92, 'ratio': 1.0}, 'validate': {'recorded': 92, 'expected': 92, 'ratio': 1.0}, 'patch_generate': {'recorded': 92, 'expected': 92, 'ratio': 1.0}}`
- 主要差距：`[{'reason_code': 'PATCH_ACCEPTANCE_NOT_PASS', 'count': 29}, {'reason_code': 'OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR', 'count': 26}, {'reason_code': 'OPTIMIZE_ANALYSIS_MISSING', 'count': 10}, {'reason_code': 'OPTIMIZE_ANALYSIS_PARTIAL', 'count': 5}, {'reason_code': 'RISKY_DOLLAR_SUBSTITUTION', 'count': 1}]`
- 阻塞 SQL: `[]`

## 附录
- report.json: `run_8c1719c37556/report.json`
- proposals: `run_8c1719c37556/proposals/optimization.proposals.jsonl`
- acceptance: `run_8c1719c37556/acceptance/acceptance.results.jsonl`
- patches: `run_8c1719c37556/patches/patch.results.jsonl`
- verification: `run_8c1719c37556/verification/ledger.jsonl`
- failures: `run_8c1719c37556/ops/failures.jsonl`
