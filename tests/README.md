# Tests

`tests/` 只负责验证，不承载共享实现本体。

目录分层：
- `tests/unit/`
  - 模块级与实现级单元测试
- `tests/contract/`
  - 稳定契约测试
  - 当前分组：`classification/`、`patch/`、`report/`、`schema/`
- `tests/harness/`
  - 多组件与样本项目场景测试
  - `engine/`：回归 `python/sqlopt/devtools/harness/` 本身
  - `workflow/`：运行控制与 golden workflow 场景
  - `fixture/`：sample project / fixture 场景
- `tests/ci/`
  - 脚本与验收入口测试
- `tests/fixtures/`
  - 静态测试资产
  - `projects/`：样本项目
  - `scenarios/`：scenario matrix
  - `configs/`：测试配置变体
  - `mocks/`：模拟输入/输出
  - `scan_samples/`：scanner 专用样本

`python/sqlopt/devtools/harness/` 是正式 harness 实现层：
- `runtime/`
- `assertions/`
- `scenarios/`
- `benchmark/`

关系约束：
- 公共 harness 逻辑应放在 `python/sqlopt/devtools/harness/`
- `tests/harness/engine/` 验证这层实现
- `tests/harness/workflow/` 和 `tests/harness/fixture/` 只保留场景意图

常用命令：

```bash
python3 -m pytest -q
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract -q
python3 -m pytest tests/harness -q
python3 -m pytest tests/ci -q
```

生成垃圾文件不应提交：
- `tests/__pycache__/`
- `tests/.DS_Store`
- `tests/fixtures/.DS_Store`
