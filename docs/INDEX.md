# SQL Optimizer 文档导航

欢迎使用 SQL Optimizer！本页面帮助你快速找到所需的文档。

## 🚀 快速开始

**新用户？从这里开始：**

- **[快速入门指南](QUICKSTART.md)** - 10 分钟完成首次运行
- **[安装指南](INSTALL.md)** - 详细的安装步骤
- **[配置示例](../templates/sqlopt.example.yml)** - 带详细注释的配置文件
- **配置边界提示**：外部仅支持 `project / scan / db / llm / report / config_version`

## 📚 按用户角色分类

### 👤 最终用户（使用 SQL Optimizer 的开发者）

**基础使用：**
- [快速入门指南](QUICKSTART.md) - 快速上手
- [安装指南](INSTALL.md) - 安装和配置
- [配置说明](project/05-config-and-conventions.md) - 配置选项详解
- [故障排查](TROUBLESHOOTING.md) - 常见问题和解决方案

**进阶使用：**
- [系统规格](project/02-system-spec.md) - 理解系统架构和阶段
- [工作流程](project/03-workflow-and-state-machine.md) - 命令和状态机
- [数据契约](project/04-data-contracts.md) - 输入输出格式
- [失败码说明](failure-codes.md) - 错误码含义和处理

**维护和升级：**
- [升级指南](UPGRADE.md) - 版本升级步骤
- [兼容性说明](compatibility.md) - 版本兼容性政策
- [分发指南](DISTRIBUTION.md) - 打包和分发

### 👨‍💻 贡献者（参与开发的开发者）

**开发指南：**
- [产品需求](project/01-product-requirements.md) - 产品定位和需求
- [系统规格](project/02-system-spec.md) - 架构设计
- [数据契约](project/04-data-contracts.md) - 数据结构定义
- [交付清单](project/06-delivery-checklist.md) - 发布前检查

**技术参考：**
- [Scanner SPI](scanner-spi.md) - 扫描器接口规范
- [失败码定义](failure-codes.md) - 错误码体系
- [CLAUDE.md](../CLAUDE.md) - AI 助手使用指南

**测试和验证：**
- [手动测试 Fixture](project/07-manual-test-fixture.md) - 测试用例

## 📖 按主题分类

### 安装和配置

- [安装指南](INSTALL.md) - 完整安装步骤
- [快速入门](QUICKSTART.md) - 快速开始
- [配置参考](CONFIG.md) - 完整配置说明
- [配置示例](../templates/sqlopt.example.yml) - 带注释的配置文件

### 使用和操作

- [工作流程](project/03-workflow-and-state-machine.md) - 命令和状态机
- [Skill 触发示例](skill-trigger-examples.md) - 使用示例
- [故障排查](TROUBLESHOOTING.md) - 问题诊断和解决

### 技术细节

- [系统规格](project/02-system-spec.md) - 架构和实现
- [数据契约](project/04-data-contracts.md) - 数据格式
- [Scanner SPI](scanner-spi.md) - 扫描器接口
- [失败码说明](failure-codes.md) - 错误处理

### 维护和升级

- [升级指南](UPGRADE.md) - 版本升级
- [兼容性说明](compatibility.md) - 版本兼容性
- [分发指南](DISTRIBUTION.md) - 打包分发

## 🔍 常见任务快速查找

### 我想...

**开始使用：**
- ➡️ [快速入门指南](QUICKSTART.md)

**安装到新项目：**
- ➡️ [安装指南](INSTALL.md) → 第 2-4 节

**配置数据库连接：**
- ➡️ [配置参考](CONFIG.md) - 完整配置说明
- ➡️ [故障排查](TROUBLESHOOTING.md) → 数据库连接问题

**理解错误消息：**
- ➡️ [失败码说明](failure-codes.md)
- ➡️ [故障排查](TROUBLESHOOTING.md)

**查看运行结果：**
- ➡️ [工作流程](project/03-workflow-and-state-machine.md) → 完成判定
- ➡️ [数据契约](project/04-data-contracts.md) → 报告格式

**升级到新版本：**
- ➡️ [升级指南](UPGRADE.md)
- ➡️ [兼容性说明](compatibility.md)

**解决问题：**
- ➡️ [故障排查](TROUBLESHOOTING.md)
- ➡️ [失败码说明](failure-codes.md)

**理解系统架构：**
- ➡️ [系统规格](project/02-system-spec.md)
- ➡️ [产品需求](project/01-product-requirements.md)

**贡献代码：**
- ➡️ [系统规格](project/02-system-spec.md)
- ➡️ [数据契约](project/04-data-contracts.md)
- ➡️ [交付清单](project/06-delivery-checklist.md)

## 📋 文档完整列表

### 用户文档

| 文档 | 描述 | 适合人群 |
|------|------|---------|
| [QUICKSTART.md](QUICKSTART.md) | 快速入门指南 | 新用户 |
| [INSTALL.md](INSTALL.md) | 安装和配置 | 所有用户 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 故障排查 | 所有用户 |
| [UPGRADE.md](UPGRADE.md) | 版本升级 | 维护者 |
| [DISTRIBUTION.md](DISTRIBUTION.md) | 打包分发 | 管理员 |
| [compatibility.md](compatibility.md) | 兼容性说明 | 所有用户 |
| [failure-codes.md](failure-codes.md) | 失败码说明 | 所有用户 |
| [scanner-spi.md](scanner-spi.md) | 扫描器接口 | 高级用户 |
| [skill-trigger-examples.md](skill-trigger-examples.md) | 使用示例 | 所有用户 |
| [CONFIG.md](CONFIG.md) | 配置参考 | 所有用户 |

### 项目文档

| 文档 | 描述 | 适合人群 |
|------|------|---------|
| [01-product-requirements.md](project/01-product-requirements.md) | 产品需求 | 贡献者 |
| [02-system-spec.md](project/02-system-spec.md) | 系统规格 | 贡献者 |
| [03-workflow-and-state-machine.md](project/03-workflow-and-state-machine.md) | 工作流程 | 所有用户 |
| [04-data-contracts.md](project/04-data-contracts.md) | 数据契约 | 贡献者 |
| [05-config-and-conventions.md](project/05-config-and-conventions.md) | 配置说明 | 所有用户 |
| [06-delivery-checklist.md](project/06-delivery-checklist.md) | 交付清单 | 贡献者 |
| [07-manual-test-fixture.md](project/07-manual-test-fixture.md) | 测试用例 | 贡献者 |

### Skill 参考文档

| 文档 | 描述 |
|------|------|
| [contracts.md](../skills/sql-optimizer/references/contracts.md) | 契约定义 |
| [failure-codes.md](../skills/sql-optimizer/references/failure-codes.md) | 失败码 |
| [postgresql.md](../skills/sql-optimizer/references/postgresql.md) | PostgreSQL 支持 |
| [runtime-budget.md](../skills/sql-optimizer/references/runtime-budget.md) | 运行时预算 |

## 🆘 获取帮助

### 命令行帮助

```bash
# 查看主帮助
sqlopt-cli --help

# 查看子命令帮助
sqlopt-cli run --help
sqlopt-cli status --help
sqlopt-cli resume --help
sqlopt-cli apply --help
```

### 诊断工具

```bash
# 运行环境检查
python3 install/doctor.py --project <your_project>

# 验证配置文件
sqlopt-cli validate-config --config sqlopt.yml
```

### 在线资源

- **报告问题：** https://github.com/your-org/sql-optimizer/issues
- **查看源码：** https://github.com/your-org/sql-optimizer
- **AI 助手：** 参考 [CLAUDE.md](../CLAUDE.md)

## 📝 文档约定

### 符号说明

- ✅ 推荐的做法
- ⚠️ 需要注意的事项
- ❌ 不推荐的做法
- 💡 提示和技巧
- 🔧 配置相关
- 🐛 故障排查

### 代码块

```bash
# Shell 命令
command --option value
```

```yaml
# YAML 配置
key: value
```

```python
# Python 代码
def function():
    pass
```

## 🔄 文档更新

本文档随项目持续更新。如果发现文档问题或有改进建议，请：

1. 提交 Issue：https://github.com/your-org/sql-optimizer/issues
2. 提交 Pull Request
3. 联系维护团队

---

**最后更新：** 2026-03-06
**文档版本：** 与项目版本同步
