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

## V9 文档 (当前架构)

V9 是 SQL Optimizer 的当前架构，采用 5 阶段流水线设计。

| 文件 | 说明 |
|------|------|
| [v9-design/README.md](./v9-design/README.md) | V9 设计索引 |
| [v9-design/V9_ARCHITECTURE_OVERVIEW.md](./v9-design/V9_ARCHITECTURE_OVERVIEW.md) | V9 架构总览 |
| [v9-design/V9_ARCHITECTURE.md](./v9-design/V9_ARCHITECTURE.md) | V9 流水线详解 |
| [v9-design/V9_DATA_CONTRACTS.md](./v9-design/V9_DATA_CONTRACTS.md) | 数据契约与 Schema |
| [v9-design/V9_STAGE_API_CONTRACTS.md](./v9-design/V9_STAGE_API_CONTRACTS.md) | 阶段 API 契约 |
| [v9-design/V9_STAGE_DEV_GUIDE.md](./v9-design/V9_STAGE_DEV_GUIDE.md) | 阶段开发指南 |

### V9 五阶段流水线

```
Init → Parse → Recognition → Optimize → Patch
```

| 阶段 | 名称 | 说明 |
|------|------|------|
| 1 | **Init** | 连接数据库、解析 MyBatis XML、提取 SQL 单元 |
| 2 | **Parse** | 展开动态标签生成分支路径（if/choose/foreach）、风险检测 |
| 3 | **Recognition** | EXPLAIN 采集执行计划、记录性能基线 |
| 4 | **Optimize** | 规则引擎 + LLM 生成优化建议、迭代式验证 |
| 5 | **Patch** | 生成 XML 补丁、用户确认、应用变更 |

### V8 → V9 阶段映射

| V8 阶段 | V9 阶段 | 变化说明 |
|---------|---------|----------|
| Discovery | Init | 合并到初始化阶段 |
| Branching + Pruning | Parse | 合并为单一解析阶段 |
| Baseline | Recognition | 重命名，语义不变 |
| Optimize + Validate | Optimize | 验证内置于优化迭代中 |
| Patch | Patch | 保持不变 |

---

## V8 文档 (Legacy)

V8 是 SQL Optimizer 的旧版架构，采用 7 阶段流水线设计。**已由 V9 取代**，仅供历史参考。

| 文件 | 说明 |
|------|------|
| [V8/V8_SUMMARY.md](./V8/V8_SUMMARY.md) | V8 架构设计总览 |
| [V8/V8_STAGES_OVERVIEW.md](./V8/V8_STAGES_OVERVIEW.md) | 7 阶段详解 |
| [V8/STAGE_API_CONTRACTS.md](./V8/STAGE_API_CONTRACTS.md) | 阶段 API、输入输出契约与样例规范 |

### V8 核心流程 (Legacy)

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
2. **了解架构**: ARCHITECTURE.md → v9-design/V9_ARCHITECTURE_OVERVIEW.md → v9-design/V9_ARCHITECTURE.md
3. **问题排查**: TROUBLESHOOTING.md
