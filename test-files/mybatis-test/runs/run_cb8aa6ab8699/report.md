# SQL Optimize Report: run_cb8aa6ab8699

## Executive Decision
- Release Readiness: `CONDITIONAL_GO`
- Verdict: `PASS`
- Scope: SQL units `96`, proposals `0`
- Delivery Snapshot: patches `0`, applicable `0`, blocked sql `0`
- Perf Evidence: improved `0`, not improved `0`
- Materialization: `{}`
- Materialization Reasons: `{}`
- Materialization Actions: `{}`

## Top Risks
- None

## Delivery Status
- preflight: `DONE`
- scan: `DONE` (attempts `1`)
- optimize: `PENDING` (attempts `0`)
- validate: `PENDING` (attempts `0`)
- patch_generate: `PENDING` (attempts `0`)
- report: `PENDING`

## Change Portfolio
| SQL Key | Status | Source | Perf | Materialization | Patch Applicable | Patch Decision |
|---|---|---|---|---|---|---|
| `com.test.mapper.OrderMapper.findOrdersWithCommon#v1` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.OrderMapper.findOrdersConditional#v2` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.OrderMapper.findOrdersByMode#v3` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.OrderMapper.findOrdersComplex#v4` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSingleIf#v1` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testTwoIf#v2` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testThreeIf#v3` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testFourIf#v4` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseWhen#v5` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseOtherwise#v6` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testWhereIf#v7` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSetIf#v8` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testForeachIn#v9` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testTrim#v10` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIfChoose#v11` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testWhereMultipleIf#v12` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseMultipleIf#v13` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIfForeach#v14` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testWhereChooseWhen#v15` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseWithMultipleIf#v16` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testFiveIf#v17` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseNestedChoose#v18` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testComplexConditions#v19` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDynamicOrderBy#v20` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testBindIf#v21` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testTrimPrefixSuffix#v22` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testForeachInsert#v23` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDynamicColumns#v24` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChooseTripleNested#v25` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSetMultipleIf#v26` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIfMultiCondition#v27` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testForeachChoose#v28` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testTrimUpdate#v29` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIfForeachComplex#v30` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeBaseColumns#v31` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeCondition#v32` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultipleInclude#v33` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeComplex#v34` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeInIf#v35` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeInChoose#v36` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultipleBind#v37` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testBindWithInclude#v38` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testEmptyIf#v39` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testOnlyOtherwise#v40` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testNestedTrim#v41` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testNestedForeach#v42` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testIncludeWithProperty#v43` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testLongConditions#v44` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testInsertWithSelectKey#v45` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testInnerJoin#v46` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testLeftJoin#v47` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultiTableJoin#v48` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDynamicJoin#v49` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSubqueryIn#v50` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSubqueryExists#v51` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testScalarSubquery#v52` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDynamicMultiTableJoin#v53` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testUnion#v54` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testNestedSubquery#v55` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCountAll#v56` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCountByStatus#v57` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testSumAmount#v58` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testAvgAmount#v59` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMaxMinAmount#v60` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testGroupBy#v61` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultiGroupBy#v62` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testGroupByHaving#v63` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCaseWhen#v64` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDateFunction#v65` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testStringConcat#v66` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testStringSubstring#v67` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testConditionalSum#v68` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultiAggFunction#v69` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testOrderRank#v70` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testLimit#v71` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testLimitOffset#v72` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDynamicPagination#v73` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDistinctStatus#v74` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDistinctMultipleFields#v75` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testInsertOnDuplicateKeyUpdate#v76` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testReturningSyntax#v77` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testDistinctWithCondition#v78` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCountDistinct#v79` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testOrderByMultipleWithPagination#v80` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testComplexAggregation#v81` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testUnionWithLimit#v82` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileInclude#v83` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileIncludeWithIf#v84` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testLocalFragmentWithCrossFile#v85` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileInChoose#v86` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileWithForeach#v87` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testMultipleCrossFileInclude#v88` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileNestedChoose#v89` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileInTrim#v90` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testCrossFileInSet#v91` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |
| `com.test.mapper.UserMapper.testChainedCrossFileInclude#v92` | `PENDING` | `n/a` | `unknown` | `n/a` | `n/a` | `n/a` |

## Proposal Insights
| SQL Key | Verdict | Issues | LLM Candidates |
|---|---|---|---|
| `n/a` | `n/a` | `n/a` | `0` |

## Technical Evidence
- No PASS items with technical evidence.

## Action Plan (Next 24h)
- Backend: apply generated patches: `PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id run_cb8aa6ab8699`

## Appendix
- report.json: `run_cb8aa6ab8699/report.json`
- proposals: `run_cb8aa6ab8699/proposals/optimization.proposals.jsonl`
- acceptance: `run_cb8aa6ab8699/acceptance/acceptance.results.jsonl`
- patches: `run_cb8aa6ab8699/patches/patch.results.jsonl`
- failures: `run_cb8aa6ab8699/ops/failures.jsonl`
