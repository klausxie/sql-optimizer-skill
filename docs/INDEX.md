# SQL Optimizer 文档

当前仅保留 7 份有效文档：

1. [快速入门](QUICKSTART.md)
2. [安装指南](INSTALL.md)
3. [配置参考](CONFIG.md)
4. [LLM Replay 使用说明](LLM_REPLAY.md)
5. [故障排查](TROUBLESHOOTING.md)
6. [当前规格](current-spec.md)
7. [本文档](INDEX.md)

当前支持边界与产品化说明：

- 支持矩阵与当前产品边界见 [superpowers/specs/2026-04-10-supported-capability-matrix.md](superpowers/specs/2026-04-10-supported-capability-matrix.md)
- summary/diagnostics 边界映射见 [superpowers/specs/2026-04-10-product-output-boundary-mapping.md](superpowers/specs/2026-04-10-product-output-boundary-mapping.md)
- 未来改动的 release gate 见 [superpowers/specs/2026-04-10-release-gate-definition.md](superpowers/specs/2026-04-10-release-gate-definition.md)

推荐阅读顺序：

1. 首次接入先看 [安装指南](INSTALL.md)
2. 想尽快跑通一轮流程看 [快速入门](QUICKSTART.md)
3. 调整配置看 [配置参考](CONFIG.md)
4. 做测试/fixture/generalization 时先看 [LLM Replay 使用说明](LLM_REPLAY.md)
5. 理解当前实现边界看 [当前规格](current-spec.md)
6. 看当前支持范围与 blocked boundary 先看 [支持矩阵](superpowers/specs/2026-04-10-supported-capability-matrix.md)
7. 遇到失败再看 [故障排查](TROUBLESHOOTING.md)

开发者补充：
- 测试目录与 harness 分层见 [当前规格](current-spec.md) 第 11 节
- 测试目录快速说明见 [../tests/README.md](../tests/README.md)
- 根部协作说明以 `AGENTS.md` / `CLAUDE.md` 为准，但低于代码与 schema

常用命令：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --help
```
