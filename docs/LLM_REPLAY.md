# SQL Optimizer LLM Cassette / Replay 使用说明

目标：让日常开发、fixture harness 和 `sample_project` / `generalization` 测试默认不依赖 live LLM，只在需要录制或验收 provider 集成时才真正调用 LLM。

当前范围只覆盖 `optimize` 阶段的 LLM candidate generation：

- `python/sqlopt/stages/optimize.py`
- `python/sqlopt/platforms/sql/optimizer_sql.py`
- `python/sqlopt/platforms/sql/llm_replay_gateway.py`

不覆盖：

- validate 阶段的 LLM 语义检查
- patch_generate 的 LLM assist

## 1. 三种模式

`llm.mode` 现在支持三种运行方式：

- `live`
  直接调用真实 LLM provider。
- `record`
  调用真实 LLM，并把请求/响应写入 cassette。
- `replay`
  只读取 cassette，绝不调用真实 provider。

推荐使用方式：

- 单元测试：继续直接 mock
- integration / harness / `sample_project` / `generalization`：默认 `replay`
- 专门的 provider smoke / acceptance：使用 `live` 或 `record`

## 2. Cassette 存储位置

默认根目录：

`tests/fixtures/llm_cassettes`

当前 optimize cassette 结构：

```text
tests/fixtures/llm_cassettes/
└── optimize/
    ├── raw/
    │   └── <fingerprint>.json
    └── normalized/
        └── <fingerprint>.json
```

说明：

- `raw/` 保存 provider 原始响应相关信息
- `normalized/` 保存 replay 时真正返回的规范化结果
- key 不是 `sqlKey`，而是 request fingerprint

## 3. 相关配置

`llm` 配置现在新增这几个字段：

```yaml
llm:
  provider: opencode_run
  mode: replay
  cassette_root: tests/fixtures/llm_cassettes
  replay_strict: true
```

语义：

- `mode`
  `live | record | replay`
- `cassette_root`
  cassette 根目录
- `replay_strict`
  `true` 时 replay miss 直接失败，不会偷偷 fallback 到 live

开发建议：

- 日常默认：`mode=replay` 且 `replay_strict=true`
- 刷新 cassette：临时切到 `mode=record`
- provider 真集成验收：显式用 `mode=live`

## 4. sample_project 使用方式

### 4.1 日常开发默认 replay

```bash
python3 scripts/run_sample_project.py --scope generalization-batch1 --to-stage optimize
python3 scripts/run_sample_project.py --scope family --to-stage optimize
```

`run_sample_project.py` 现在默认：

- `--llm-mode replay`
- `--llm-cassette-root tests/fixtures/llm_cassettes`
- `--llm-replay-strict`

也就是说，日常运行不会主动打 live LLM。

### 4.2 录制单条 SQL 的 cassette

```bash
python3 scripts/run_sample_project.py \
  --scope sql \
  --sql-key demo.user.countUser \
  --to-stage optimize \
  --llm-mode record \
  --max-seconds 180
```

适用场景：

- 新增了 optimize replay 测试样本
- 某条 statement 的 prompt / fingerprint 确实发生了预期变化
- 需要刷新 fixture cassette

### 4.3 整批 generalization replay 验证

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 240
```

这个脚本也默认走 replay，适合：

- 快速确认 `batch1..N` 不依赖 live provider
- 看 optimize 阶段的批量 smoke 是否通过

### 4.4 整批录制 cassette

```bash
python3 scripts/ci/generalization_refresh.py \
  --batch generalization-batch1 \
  --batch generalization-batch2 \
  --llm-mode record \
  --max-seconds 240
```

这类命令只在你明确要刷新 cassette 时使用。

## 5. 测试场景推荐用法

### 5.1 代码逻辑测试

如果你要验证的是：

- candidate 选择逻辑
- validate / convergence
- patch_generate
- harness/assertion

优先使用：

- 单测 mock
- 或 `sample_project` + `replay`

不要为这类逻辑测试额外打 live LLM。

### 5.2 适合 replay 的测试

典型命令：

```bash
python3 -m pytest -q tests/unit/sql/test_llm_cassette.py
python3 -m pytest -q tests/unit/sql/test_llm_replay_gateway.py
python3 -m pytest -q tests/unit/verification/test_verification_stage_integration.py
python3 -m pytest -q tests/ci/test_run_sample_project_script.py
python3 -m pytest -q tests/ci/test_generalization_refresh_script.py
```

### 5.3 什么时候才用 record/live

只在这些情况才建议真打 provider：

- 新增 `sample_project` statement，需要种第一份 cassette
- prompt 结构有意变更，需刷新 cassette
- 专门做 provider 级 smoke / acceptance

## 6. Replay Miss 怎么看

`replay` 模式 miss 会直接失败，并输出：

- `sqlKey`
- `fingerprint`
- 期望的 raw/normalized cassette 路径

这是故意的。它的目标是：

- 不让日常测试悄悄退回 live
- 明确告诉你该补哪份 cassette

正确处理方式：

1. 先确认这条 statement 是否真的会走 LLM
2. 如果会走 LLM，再用 `record` 补 cassette
3. 如果本来就是 skip / blocked 路径，不需要补 cassette

## 7. 什么情况下“看起来缺 cassette，其实不用补”

有些 statement 在 `optimize` 阶段根本不会走 LLM，例如：

- 风险过高的 `${}` 动态替换
- 已知安全边界直接 skip
- 明确 blocked 的非 LLM 路径

这类 statement 的典型特征是：

- `llmCandidates = []`
- `verification.inputs.executor = skip`
- 有明确的 degrade/block reason

这不是 replay 覆盖缺失，不需要强行录 cassette。

## 8. 运行策略建议

推荐把日常流程固定成：

1. 改逻辑：先跑定向单测
2. 收口一个 task：跑相关 `sample_project` scope 的 replay smoke
3. 需要刷新 fixture：显式用 `record`
4. 阶段收口：再跑全量 `pytest`

这样能把“慢”限制在少数需要 live provider 的场景里。

## 9. 相关文件

- [配置参考](CONFIG.md)
- [快速入门](QUICKSTART.md)
- [故障排查](TROUBLESHOOTING.md)
- [python/sqlopt/platforms/sql/llm_cassette.py](/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/llm_cassette.py)
- [python/sqlopt/platforms/sql/llm_replay_gateway.py](/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/llm_replay_gateway.py)
