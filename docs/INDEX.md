# SQL Optimizer 文档导航

## 首次使用

1. [快速入门](QUICKSTART.md)
2. [安装指南](INSTALL.md)
3. [故障排查](TROUBLESHOOTING.md)

## 常见任务

- 配置说明：[`project/05-config-and-conventions.md`](project/05-config-and-conventions.md)
- 命令与状态机：[`project/03-workflow-and-state-machine.md`](project/03-workflow-and-state-machine.md)
- 失败码解释：[`failure-codes.md`](failure-codes.md)
- 升级：[`UPGRADE.md`](UPGRADE.md)
- 分发：[`DISTRIBUTION.md`](DISTRIBUTION.md)

## 架构与契约

- 产品需求：[`project/01-product-requirements.md`](project/01-product-requirements.md)
- 系统规格：[`project/02-system-spec.md`](project/02-system-spec.md)
- 数据契约：[`project/04-data-contracts.md`](project/04-data-contracts.md)
- 产物治理：[`project/08-artifact-governance.md`](project/08-artifact-governance.md)
- SQL 补丁能力架构：[`project/10-sql-patchability-architecture.md`](project/10-sql-patchability-architecture.md)

## 测试与验收

- 手工 fixture：[`project/07-manual-test-fixture.md`](project/07-manual-test-fixture.md)
- 交付清单：[`project/06-delivery-checklist.md`](project/06-delivery-checklist.md)

动态模板与局部调试建议：

1. 优先阅读 [`project/07-manual-test-fixture.md`](project/07-manual-test-fixture.md) 中的局部 run 说明
2. 当前动态模板能力版图与 baseline family 已同步到：
   - [`project/02-system-spec.md`](project/02-system-spec.md)
   - [`project/04-data-contracts.md`](project/04-data-contracts.md)
   - [`project/10-sql-patchability-architecture.md`](project/10-sql-patchability-architecture.md)

推荐执行：

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```

## 命令帮助

```bash
sqlopt-cli --help
sqlopt-cli run --help
sqlopt-cli resume --help
sqlopt-cli status --help
sqlopt-cli apply --help
sqlopt-cli validate-config --help
```
