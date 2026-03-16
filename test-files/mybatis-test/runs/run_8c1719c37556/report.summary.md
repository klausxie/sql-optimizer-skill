# SQL 优化总结：run_8c1719c37556

- 优化结论：`PARTIAL`
- 发布就绪度：`CONDITIONAL_GO`
- 证据置信度：`LOW`
- SQL 单元数：`92`
- 验证结果：通过 `63`, 失败 `0`, 需更多参数 `29`
- 交付物：补丁 `5`, 可应用 `5`
- 失败统计：致命 `0`, 可重试 `0`, 可降级 `29`
- 验证状态：已验证 `245`, 部分 `31`, 未验证 `0`

## 优先处理的 SQL
- com.test.mapper.UserMapper.testReturningSyntax#v77: 这是最快的安全收益，因为补丁已就绪 (P0, READY_TO_APPLY)
- com.test.mapper.UserMapper.testStringConcat#v66: 这是最快的安全收益，因为补丁已就绪 (P0, READY_TO_APPLY)
- com.test.mapper.UserMapper.testStringSubstring#v67: 这是最快的安全收益，因为补丁已就绪 (P0, READY_TO_APPLY)

## 警告
- OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR: 26 sql(s) hit SQL syntax errors during optimize DB evidence collection

- 阶段状态：preflight `DONE`, scan `DONE`, optimize `DONE`, validate `DONE`, patch_generate `DONE`, report `DONE`
