# Scanner SPI（当前约定）

Command:
`java -jar scan-agent.jar --project-root <abs> --config-path <abs-json-or-yaml> --out-jsonl <abs> --dialect <db.platform> --run-id <id>`

Exit codes:
1. `0`: success
2. `10`: degraded success（warnings in stderr）
3. `20`: fatal scan failure

## stderr JSON line
字段：
1. `phase`
2. `severity`
3. `reason_code`
4. `message`
5. 可选：
   - `xml_path`
   - `mapper_path`
   - `statement_id`
   - `exception`
   - `recovery_action`
   - `recovered`

## scanner 职责边界
Current:
1. scanner 必须保留模板视图
2. scanner 可以额外生成逻辑分析视图
3. scanner 不负责生成 patch

模板保留规则：
1. `sql` 可以是渲染后的逻辑分析视图
2. `templateSql` 必须保留动态 mapper statement 的模板结构
3. 执行视图可以存在于下游 validate 内部，但不能替代模板视图成为 patch 源

## fragment catalog（当前默认开启）
当 fragment catalog 内置开关开启（当前默认）时，scanner 还应输出：
1. `pipeline/diagnose/fragments.jsonl`
2. 每条 fragment 的稳定键
3. statement / fragment 的源码 range locator
4. `<include><property>` 绑定信息

## include 相关元信息
scanner 当前需要输出：
1. `includeTrace`
   - 递归片段依赖链
2. `dynamicTrace`
   - statement / fragment 自身及依赖片段的动态特征摘要
3. `includeBindings`
   - `<include><property .../></include>` 的绑定上下文

这些元信息的作用：
1. 让 validate 能做模板物化判定
2. 让 apply 能区分静态 statement patch、模板级 patch、动态保守跳过

## fallback scanner 约束
Current:
1. Python fallback scanner 必须对齐同一套字段语义
2. 即使 Java scanner 不可用，`templateSql / dynamicFeatures / includeTrace / includeBindings` 也要尽量保持兼容
