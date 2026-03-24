# V10 重构 - 简要总结

## 目标

将 SQL Optimizer 重构为清晰的五阶段架构，每阶段代码自治，阶段间通过 JSON 契约传递数据。

## 五阶段

| 阶段 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Init** | 扫描 MyBatis XML | 配置 | `sql_units.json` (纯净SQL) |
| **Parse** | 展开动态标签 | `sql_units.json` | `sql_units.json` (带branches) + `risks.json` |
| **Recognition** | EXPLAIN 采集 | `sql_units.json` | `baselines.json` |
| **Optimize** | 生成优化建议 | `baselines.json` + 原始SQL | `proposals.json` + `recommendations.json` |
| **Result** | 汇总输出 | proposals/recommendations | `patches.json` + `reports/*.md` |

## 目录结构

```
python/sqlopt/
├── init/           # Init 阶段
├── parse/         # Parse 阶段
├── recognition/   # Recognition 阶段
├── optimize/      # Optimize 阶段
├── result/        # Result 阶段（Patch + Report）
└── common/        # 公共模块（严格审计）
    ├── llm.py               # 统一的大模型调用
    └── llm_mock_generator.py  # LLM 生成 Mock 测试数据
```

## CLI 设计

```bash
# 默认使用 ./sqlopt.yml
sqlopt run init
sqlopt run parse
sqlopt run recognition
sqlopt run optimize
sqlopt run result

# LLM 生成 Mock 测试数据（独立调测用）
sqlopt mock init "生成一个复杂的SQL单元"
sqlopt mock parse "生成一个包含include和foreach的SQL"
```

## 关键约束

- 阶段间**不直接调用**，只读写 JSON 文件
- Common 只放被 **2+ 阶段**使用的代码
- 每个阶段可**独立调测**（用 LLM 生成测试 Fixture）
- config 文件有默认路径 `./sqlopt.yml`

## 禁止的设计

- ❌ `--to-stage` / `--from-stage` / `--skip-stages`
- ❌ 每个阶段都要传 `--config`（默认路径即可）

## 成功标准

1. ✅ `sqlopt run init` 完整运行（默认找 `./sqlopt.yml`）
2. ✅ `sqlopt run <stage>` 从指定阶段开始
3. ✅ 每阶段输出通过契约验证
4. ✅ Common 模块无业务逻辑代码
5. ✅ `sqlopt mock <stage> "<描述>"` 可生成 Mock 测试数据
