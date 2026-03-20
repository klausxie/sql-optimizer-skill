# SQL Optimizer 文档导航

## 文档概览

| 文件 | 说明 |
|------|------|
| [README.md](../README.md) | 项目介绍与快速开始 |
| [QUICKSTART.md](./QUICKSTART.md) | 15分钟快速入门 |
| [INSTALL.md](./INSTALL.md) | 安装指南 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构总览 |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障排查 |

---

## V8 文档

V8 是 SQL Optimizer 的核心架构，采用 7 阶段流水线设计。

| 文件 | 说明 |
|------|------|
| [V8/V8_SUMMARY.md](./V8/V8_SUMMARY.md) | V8 架构设计总览 |
| [V8/V8_STAGES_OVERVIEW.md](./V8/V8_STAGES_OVERVIEW.md) | 7 阶段详解 |
| [V8/STAGE_API_CONTRACTS.md](./V8/STAGE_API_CONTRACTS.md) | 阶段 API、输入输出契约与样例规范 |

### V8 核心流程

```
Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch
```

1. **Discovery** - 连接数据库、采集表结构、解析 MyBatis XML
2. **Branching** - 展开动态标签生成分支路径
3. **Pruning** - 静态分析、风险标记、低价值分支过滤
4. **Baseline** - EXPLAIN 采集执行计划、记录性能基线
5. **Optimize** - 规则引擎 + LLM 生成优化建议
6. **Validate** - 语义验证、性能对比、结果集校验
7. **Patch** - 生成 XML 补丁、用户确认、应用变更

---

## 推荐阅读顺序

1. **初次使用**: README.md → QUICKSTART.md → INSTALL.md
2. **了解架构**: ARCHITECTURE.md → V8/V8_SUMMARY.md → V8/V8_STAGES_OVERVIEW.md
3. **问题排查**: TROUBLESHOOTING.md
