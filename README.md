# SQL Optimize 重构交接文档

本目录用于把当前项目的有效需求与可验证规格，整理为可直接交接给下一位开发者的重构输入。

## 🚀 快速开始

**新用户？** 查看 [快速入门指南](docs/QUICKSTART.md) - 10 分钟完成首次运行

**查找文档？** 访问 [文档导航](docs/INDEX.md) - 按角色和主题查找所需文档

## 📖 文档定位

- 面向"完全重写"而非"在旧代码上小修小补"。
- 目标规格优先，当前实现仅作为事实基线与差距参考。

## 📚 阅读顺序

1. `docs/QUICKSTART.md` - **从这里开始！**
2. `docs/project/01-product-requirements.md`
3. `docs/project/02-system-spec.md`
4. `docs/project/03-workflow-and-state-machine.md`
5. `docs/project/04-data-contracts.md`
6. `docs/project/05-config-and-conventions.md`
7. `docs/project/06-delivery-checklist.md`

## 🔧 判定规则（冲突时优先级）

1. `contracts/*.schema.json`
2. 当前代码可验证行为（`python/sqlopt`、`scripts/sqlopt_cli.py`）
3. 历史说明文档（`docs/*.md`）

## 💻 交接使用方式

- 先按 `06-delivery-checklist.md` 创建新仓/新模块骨架。
- 以 `04-data-contracts.md` 作为接口和产物结构的"红线"。
- 以 `03-workflow-and-state-machine.md` 实现命令与恢复语义。

## 🎯 Install As Skill

### 快速安装

```bash
# 1. 打包
python3 install/build_bundle.py

# 2. 安装到项目
python3 install/install_skill.py --project <your_project_path>

# 3. 验证安装
python3 install/doctor.py --project <your_project_path>
```

Windows 用户请使用 `python` 替代 `python3`。

### 使用 Skill

```bash
# 查看帮助
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli --help

# 开始优化
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli run --config sqlopt.yml

# 查看状态
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli status --run-id <run_id>

# 继续运行
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli resume --run-id <run_id>

# 应用补丁
~/.opencode/skills/sql-optimizer/bin/sqlopt-cli apply --run-id <run_id>
```

## 🔌 LLM Provider 选型

与代码一致的 LLM 提供商选项：

1. `opencode_run` - 走 `opencode run` 外部命令（推荐）
2. `direct_openai_compatible` - 直连 OpenAI 兼容 `/chat/completions`
3. `opencode_builtin` - 本地内置策略
4. `heuristic` - 本地简化启发式策略

配置示例见 `templates/sqlopt.example.yml`。

## 📋 详细文档

- **[快速入门](docs/QUICKSTART.md)** - 10 分钟上手指南
- **[文档导航](docs/INDEX.md)** - 完整文档索引
- **[安装指南](docs/INSTALL.md)** - 详细安装步骤
- **[配置说明](docs/project/05-config-and-conventions.md)** - 配置选项详解
- **[故障排查](docs/TROUBLESHOOTING.md)** - 常见问题解决
- **[升级指南](docs/UPGRADE.md)** - 版本升级步骤
- **[分发指南](docs/DISTRIBUTION.md)** - 打包和分发

## 🆘 获取帮助

- 查看命令帮助：`sqlopt-cli --help`
- 运行诊断工具：`python3 install/doctor.py --project <path>`
- 报告问题：https://github.com/your-org/sql-optimizer/issues
- AI 助手指南：[CLAUDE.md](CLAUDE.md)

