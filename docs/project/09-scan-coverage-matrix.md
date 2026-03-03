# 扫描覆盖矩阵（当前基线）

本矩阵定义当前 `scan` 阶段对 MyBatis mapper 结构的覆盖边界。目标不是声明“全部支持”，而是明确哪些场景已有稳定输出保证，哪些场景只有部分保证，哪些场景仍不在当前范围内。

## 1. 覆盖状态定义

1. `SUPPORTED`：当前有稳定输出契约，且已有回归测试覆盖。
2. `PARTIAL`：当前会输出结果，但部分证据可能降级，需结合 verification 看待。
3. `UNSUPPORTED`：当前不提供稳定输出，不应假设结果完整。

## 2. 场景矩阵

| 场景 | 状态 | 当前输出保证 | 降级/限制 | 现有回归 |
| --- | --- | --- | --- | --- |
| 静态 `select/update/delete/insert` | `SUPPORTED` | `sql`, `locators.statementId`, `templateSql`（fallback） | 若 XML 不可解析会降级或失败 | `tests/test_scan_stage.py` |
| `if` | `SUPPORTED` | `dynamicFeatures` 含 `IF`，动态模板保留 | 若缺源码范围，verification 可能为 `PARTIAL` | `tests/test_scan_stage.py` |
| `foreach` | `SUPPORTED` | `dynamicFeatures` 含 `FOREACH`，模板保留，Java scanner/fallback 都覆盖 | Java scanner jar 缺失时回退到 Python fallback | `tests/test_scan_stage.py` |
| `choose/when/otherwise` | `SUPPORTED` | `dynamicFeatures` 含 `CHOOSE`，模板保留 | 仅保证结构级识别，不做分支语义推断 | `tests/test_scan_stage.py` |
| `where` | `SUPPORTED` | `dynamicFeatures` 含 `WHERE` | 仅做结构识别，不推断逻辑条件完整性 | `tests/test_scan_stage.py` |
| `trim` | `SUPPORTED` | `dynamicFeatures` 含 `TRIM` | 仅做结构识别，不重建 trim 规则语义 | `tests/test_scan_stage.py` |
| `set` | `SUPPORTED` | `dynamicFeatures` 含 `SET` | 同上 | `tests/test_scan_stage.py` |
| `bind` | `SUPPORTED` | `dynamicFeatures` 含 `BIND` | 仅识别存在性，不保证表达式求值上下文 | `tests/test_scan_stage.py` |
| `include` | `SUPPORTED` | `includeTrace`, `dynamicTrace.includeFragments`, fragment catalog | 片段缺失时 verification 为 `PARTIAL` | `tests/test_scan_stage.py` |
| 嵌套 `include` | `SUPPORTED` | `includeTrace` 递归展开，片段动态特征可见 | 仅记录链路，不做完整执行语义展开 | `tests/test_scan_stage.py` |
| unresolved include / catalog 缺失 | `PARTIAL` | statement 仍可产出 | `SCAN_INCLUDE_TRACE_PARTIAL` / `SCAN_INCLUDE_TRACE_UNRESOLVED` | `tests/test_scan_stage.py` |
| Java scanner 严格模式降级 | `PARTIAL` | 运行可被拒绝并给出明确 reason code | `strict` 下会直接失败 | `tests/test_scan_stage.py` |
| 非 mapper XML | `SUPPORTED`（跳过） | 安全跳过，不产出 SQL unit | 不作为错误 | `tests/test_scan_stage.py` |
| annotation mapper / 非 XML SQL 源 | `UNSUPPORTED` | 无稳定扫描产物 | 需由后续扩展单独支持 | 当前未覆盖 |

## 3. 当前工程约束

1. `state.json` 不依赖扫描矩阵；矩阵只定义输入覆盖基线。
2. 新增动态标签支持时，必须同时：
   - 更新本矩阵
   - 在 `tests/test_scan_stage.py` 补对应场景断言
3. 对于 `PARTIAL` 场景，必须通过 verification 明确标记，而不是静默当成完整扫描。

## 4. 实际 fixture 回归基线

仓库内置了一份扫描覆盖样例：

- XML：`tests/fixtures/project/scan_samples/dynamic_tags_mapper.xml`
- 配置：`tests/fixtures/project/sqlopt.scan.local.yml`

推荐回归命令：

```bash
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

当前这份样例会锁住：

1. `searchUsersAdvanced`
   - `dynamicFeatures` 必须包含 `FOREACH / INCLUDE / IF / CHOOSE / WHERE / BIND`
   - `includeTrace` 必须解析到 `demo.scan.ActiveOnly` 与 `demo.scan.TenantGuard`
   - `verification` 必须是 `SCAN_EVIDENCE_VERIFIED`
2. `patchUserStatusAdvanced`
   - `dynamicFeatures` 必须包含 `IF / TRIM / SET`
   - `sql` 必须归一化为单个 `SET`，不得回退为 `SET SET`

## 5. 当前建议

1. 若项目大量使用 annotation mapper，不应把当前扫描结果视为全量覆盖。
2. 若依赖复杂 `bind` 表达式，只能把当前输出视为结构线索，而不是完整运行语义。
3. 上线前建议至少用本矩阵中的 `SUPPORTED` 场景跑一次 fixture 回归，确认项目主要模式都在当前覆盖范围内。
