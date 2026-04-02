# 阶段五：Result（结果阶段）

## 阶段简介
- 输入：OptimizeOutput
- 输出：ResultOutput, Report, Patch
- 职责：生成最终报告和补丁文件

## 数据契约

### Report
人类可读的报告。

| 字段 | 类型 | 说明 |
|------|------|------|
| summary | dict | 汇总统计 |
| details | list | 详细提案 |
| risks | list | 未处理风险 |
| recommendations | list | 建议措施 |

### Patch
补丁信息。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql_unit_id | str | 是 | 被修补的 SQL Unit ID |
| original_xml | str | 是 | 原始 XML |
| patched_xml | str | 是 | 替换后 XML |
| diff | str | 是 | 统一 diff 格式 |

### Per-unit Patch Metadata
每个 .meta.json 文件包含的元数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| sql_unit_id | str | SQL Unit 标识 |
| sql_id | str | XML statement ID |
| mapper_file | str | Mapper 文件相对路径 |
| operation | str | ADD/REPLACE/REMOVE/WRAP |
| confidence | float | 置信度 |
| rationale | str | 优化理由 |
| original_snippet | str|None | 原始代码片段 |
| rewritten_snippet | str|None | 替换后代码 |
| issue_type | str | 问题类型 |

### ResultOutput
顶级输出容器。

| 字段 | 类型 | 说明 |
|------|------|------|
| can_patch | bool | 是否有可应用补丁 |
| report | Report | 汇总报告 |
| patches | list[Patch] | 补丁列表 |

## 输出文件清单

| 文件路径 | 内容 | 生成时机 | 用途 |
|----------|------|----------|------|
| runs/{run_id}/result/report.json | 完整报告 | Result 结束时 | 存档 |
| runs/{run_id}/result/SUMMARY.md | Markdown 摘要 | Result 结束时 | 快速浏览 |
| runs/{run_id}/result/units/_index.json | 可用 Unit ID | Result 结束时 | 索引 |
| runs/{run_id}/result/units/{unit_id}.patch | 统一 diff | Result 结束时 | 应用补丁 |
| runs/{run_id}/result/units/{unit_id}.meta.json | 补丁元数据 | Result 结束时 | 详情审计 |

## 常见问题

### Q: 什么时候 can_patch 为 false？
没有可应用的优化提案时。

### Q: 如何应用补丁？
使用 sqlopt apply {unit_id} --run-id {run_id}，建议先用 --dry-run 预览。