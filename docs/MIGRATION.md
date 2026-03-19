# 配置迁移指南: v1 到 v2

> 本指南帮助用户从 v1 配置格式迁移到 v2 声明式流水线格式。

## 迁移概述

v2 配置格式引入**声明式流水线**概念，但**完全兼容 v1 格式**。迁移是可选的，但推荐使用 v2 以获得更好的灵活性和可读性。

## 快速迁移

### 方式 1: 自动迁移 (推荐)

```bash
# 使用 CLI 工具自动迁移配置
sqlopt-cli migrate-config --input sqlopt.yml --output sqlopt_v2.yml --target-version v2
```

### 方式 2: 手动迁移

按照下方字段映射表进行转换。

## 字段映射表

### v1 顶层字段 -> v2 阶段配置

| v1 字段 | v2 字段 | 说明 |
|---------|---------|------|
| `validate.db_reachable` | `pipeline.stages[validate].config.db_reachable` | 数据库可达性检查 |
| `validate.validation_profile` | `pipeline.stages[validate].config.validation_profile` | 验证配置 |
| `validate.allow_db_unreachable_fallback` | `pipeline.stages[validate].config.allow_db_unreachable_fallback` | 允许回退 |
| `validate.selection_mode` | `pipeline.stages[validate].config.selection_mode` | 选择模式 |
| `validate.require_semantic_match` | `pipeline.stages[validate].config.require_semantic_match` | 要求语义匹配 |
| `validate.require_perf_evidence_for_pass` | `pipeline.stages[validate].config.require_perf_evidence_for_pass` | 要求性能证据 |
| `validate.require_verified_evidence_for_pass` | `pipeline.stages[validate].config.require_verified_evidence_for_pass` | 要求验证证据 |
| `validate.delivery_bias` | `pipeline.stages[validate].config.delivery_bias` | 交付策略 |
| `validate.plan_compare_enabled` | `pipeline.stages[validate].config.plan_compare_enabled` | 启用计划比较 |
| `validate.llm_semantic_check` | `pipeline.stages[validate].config.llm_semantic_check` | LLM 语义检查 |
| `runtime.profile` | `pipeline.profile` | 运行时配置 |

### v1 内部字段 (已弃用)

以下 v1 字段已移动到 v2 的 stage.config 中:

| v1 内部字段 | v2 位置 | 说明 |
|-------------|---------|------|
| `policy.require_perf_improvement` | `pipeline.stages[optimize].config.require_perf_improvement` | 要求性能提升 |
| `policy.cost_threshold_pct` | `pipeline.stages[optimize].config.cost_threshold_pct` | 成本阈值 |
| `policy.semantic_strict_mode` | `pipeline.stages[validate].config.semantic_strict_mode` | 严格语义模式 |
| `patch.llm_assist` | `pipeline.stages[patch].config.llm_assist` | LLM 辅助 |
| `diagnostics` | `pipeline.stages[pruning].config` + `pipeline.stages[diagnostics].config` | 诊断配置 |

## 迁移示例

### 示例 1: 基础迁移

**v1 配置:**

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost/db

llm:
  enabled: true
  provider: opencode_run

validate:
  db_reachable: true
  validation_profile: balanced
  allow_db_unreachable_fallback: false

runtime:
  profile: balanced
```

**v2 等效配置:**

```yaml
config_version: v2

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost/db

llm:
  enabled: true
  provider: opencode_run

pipeline:
  profile: balanced
  stages:
    - name: discovery
      enabled: true
    - name: branching
      enabled: true
    - name: pruning
      enabled: true
    - name: baseline
      enabled: true
    - name: optimize
      enabled: true
    - name: validate
      enabled: true
      config:
        db_reachable: true
        validation_profile: balanced
        allow_db_unreachable_fallback: false
    - name: patch
      enabled: true
```

### 示例 2: 完整迁移

**v1 配置:**

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml
    - src/main/resources/mapper/**/*.xml

db:
  platform: mysql
  dsn: mysql://user:pass@localhost:3306/mydb
  schema: app

llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 80000

validate:
  db_reachable: true
  validation_profile: thorough
  allow_db_unreachable_fallback: false
  require_semantic_match: true
  require_perf_evidence_for_pass: true
  delivery_bias: conservative

runtime:
  profile: fast

report:
  enabled: true

rules:
  enabled: true
  builtin_rules:
    DOLLAR_SUBSTITUTION: true
    SELECT_STAR: true
    FULL_SCAN_RISK: true
```

**v2 等效配置:**

```yaml
config_version: v2

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml
    - src/main/resources/mapper/**/*.xml

db:
  platform: mysql
  dsn: mysql://user:pass@localhost:3306/mydb
  schema: app

llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 80000

pipeline:
  profile: fast
  stages:
    - name: discovery
      enabled: true

    - name: branching
      enabled: true
      config:
        max_branches_per_sql: 100
        max_total_branches: 1000
        expand_foreach: true

    - name: pruning
      enabled: true
      config:
        risk_threshold: medium
        filter_low_value_branches: true
        mark_prefix_wildcard: true
        mark_suffix_wildcard: true
        mark_concat_wildcard: true
        mark_function_wrap: true

    - name: baseline
      enabled: true
      config:
        timeout_ms: 30000
        collect_buffer_stats: true
        collect_index_usage: true
        bind_params: true

    - name: optimize
      enabled: true
      config:
        strategy: rule_first
        rules:
          enabled: true
          builtin_rules:
            - DOLLAR_SUBSTITUTION
            - SELECT_STAR
            - FULL_SCAN_RISK

    - name: validate
      enabled: true
      config:
        validation_profile: thorough
        db_reachable: true
        allow_db_unreachable_fallback: false
        require_semantic_match: true
        require_perf_evidence_for_pass: true
        delivery_bias: conservative

    - name: patch
      enabled: true
      config:
        mode: PATCH_ONLY

report:
  enabled: true
```

## 新增特性 (v2 独有)

v2 提供了 v1 无法表达的灵活配置:

### 1. 选择性启用 stages

```yaml
pipeline:
  stages:
    - name: discovery
      enabled: true
    - name: branching
      enabled: true
    - name: pruning
      enabled: true
    - name: baseline
      enabled: false  # 跳过基线采集
    - name: optimize
      enabled: true
    - name: validate
      enabled: true
    - name: patch
      enabled: true
```

### 2. 阶段特定超时

```yaml
pipeline:
  stages:
    - name: baseline
      enabled: true
      config:
        timeout_ms: 60000  # 基线阶段延长超时
        
    - name: optimize
      enabled: true
      config:
        # 优化阶段使用规则引擎优先
        strategy: rule_first
```

### 3. 分支展开控制

```yaml
pipeline:
  stages:
    - name: branching
      enabled: true
      config:
        max_branches_per_sql: 50   # 限制单个 SQL 分支数
        max_total_branches: 500    # 限制总分支数
        expand_foreach: false      # 不展开 foreach
```

### 4. 剪枝风险配置

```yaml
pipeline:
  stages:
    - name: pruning
      enabled: true
      config:
        risk_threshold: high  # 只标记高风险
        filter_low_value_branches: true
        low_value_cost_threshold: 0.001
```

## 常见问题

### Q: 迁移后配置验证失败怎么办?

检查以下几点:
1. 确保 `config_version: v2` 在文件顶部
2. 确保 stage names 拼写正确
3. 确保 stage 配置字段符合 schema
4. 使用 `sqlopt-cli validate-config` 验证

### Q: 可以混用 v1 和 v2 字段吗?

不建议。v1 和 v2 字段不应混用。优先使用 v2 格式。

### Q: v1 配置会继续支持多久?

v1 配置会继续支持至少 12 个月。如果有弃用计划，会提前 6 个月通知。

### Q: 如何回退到 v1 格式?

将 `config_version: v2` 改回 `config_version: v1`，并删除所有 `pipeline` 相关配置。

## 自动化迁移脚本

```python
#!/usr/bin/env python3
"""配置迁移脚本: v1 -> v2"""

import argparse
import yaml
from pathlib import Path


V1_TO_V2_FIELD_MAP = {
    # validate -> validate stage config
    "validate.db_reachable": "pipeline.stages[validate].config.db_reachable",
    "validate.validation_profile": "pipeline.stages[validate].config.validation_profile",
    "validate.allow_db_unreachable_fallback": "pipeline.stages[validate].config.allow_db_unreachable_fallback",
    "validate.selection_mode": "pipeline.stages[validate].config.selection_mode",
    "validate.require_semantic_match": "pipeline.stages[validate].config.require_semantic_match",
    "validate.require_perf_evidence_for_pass": "pipeline.stages[validate].config.require_perf_evidence_for_pass",
    "validate.require_verified_evidence_for_pass": "pipeline.stages[validate].config.require_verified_evidence_for_pass",
    "validate.delivery_bias": "pipeline.stages[validate].config.delivery_bias",
    "validate.plan_compare_enabled": "pipeline.stages[validate].config.plan_compare_enabled",
    "validate.llm_semantic_check": "pipeline.stages[validate].config.llm_semantic_check",
    # runtime -> pipeline.profile
    "runtime.profile": "pipeline.profile",
}


def migrate_config(config: dict) -> dict:
    """将 v1 配置迁移到 v2"""
    if config.get("config_version") != "v1":
        return config
    
    result = config.copy()
    result["config_version"] = "v2"
    
    # 初始化 pipeline
    if "pipeline" not in result:
        result["pipeline"] = {"stages": []}
    
    # 设置 profile
    if "runtime" in config:
        result["pipeline"]["profile"] = config["runtime"].get("profile", "balanced")
    
    # 构建默认 stages
    stage_names = ["discovery", "branching", "pruning", "baseline", "optimize", "validate", "patch"]
    existing_validate_config = config.get("validate", {})
    
    for name in stage_names:
        stage = {"name": name, "enabled": True, "config": {}}
        
        if name == "validate" and existing_validate_config:
            stage["config"] = existing_validate_config.copy()
        
        result["pipeline"]["stages"].append(stage)
    
    # 清理旧字段
    for old_field in ["runtime", "validate"]:
        if old_field in result:
            del result[old_field]
    
    return result


def main():
    parser = argparse.ArgumentParser(description="迁移 SQL Optimizer 配置 v1 -> v2")
    parser.add_argument("--input", "-i", required=True, help="输入文件")
    parser.add_argument("--output", "-o", required=True, help="输出文件")
    args = parser.parse_args()
    
    with open(args.input) as f:
        config = yaml.safe_load(f)
    
    migrated = migrate_config(config)
    
    with open(args.output, "w") as f:
        yaml.dump(migrated, f, default_flow_style=False, sort_keys=False)
    
    print(f"已迁移配置: {args.input} -> {args.output}")


if __name__ == "__main__":
    main()
```

## 验证迁移结果

```bash
# 验证迁移后的配置
sqlopt-cli validate-config --config sqlopt_v2.yml

# 尝试运行
sqlopt-cli run --config sqlopt_v2.yml --dry-run
```
