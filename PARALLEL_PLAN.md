# SQL Optimizer 并行分工计划

> 创建日期：2026-03-18
> 更新：2026-03-18 晚
> 分支：ai/refactor-stage-modules

---

## 当前状态

### ✅ 已完成

| 任务 | 状态 |
|------|------|
| 重命名 *_stage → * | ✅ baseline/, optimize/, validate/, patch/ |
| .sqlopt/ 缓存 | ✅ run_paths.py 已实现 |
| 部分旧workflow删除 | ✅ workflow_engine/facade/definition 已删 |

### 🔲 待完成

| 任务 | 状态 | 说明 |
|------|------|------|
| 删除 stages/*.py | 🔲 24个文件待删除 | diagnose.py, scan.py 等 |
| 实现 verify 命令 | 🔲 | cli/main.py |
| 删除 status_resolver.py | 🔲 | 待确认V8稳定 |

---

## 剩余任务

### 任务A: 删除 stages/*.py 旧代码 (24个文件)

```
需删除:
stages/diagnose.py
stages/scan.py
stages/execute.py
stages/parse.py
stages/patch_decision_engine.py
stages/patch_decision.py
stages/patch_finalize.py
stages/patch_formatting.py
stages/patch_generate.py
stages/patch_generate_llm.py
stages/patch_verification.py
stages/patching_render.py
stages/patching_results.py
stages/patching_templates.py
stages/preflight_check.py
stages/report_builder.py
stages/report_loader.py
stages/report_writer.py
stages/report_interfaces.py
stages/report_models.py
stages/report_metrics.py
stages/report_render.py
stages/report_stats.py
```

### 任务B: 实现 verify 命令

```
文件: cli/main.py
功能: 证据链验证
```

### 任务C: 删除 status_resolver.py

```
确认V8稳定后删除:
application/status_resolver.py
```

---

## 当前代码结构

```
python/sqlopt/
├── application/
│   ├── workflow_v8.py      # ✅ V8主工作流
│   ├── status_resolver.py  # 🔲 待删除
│   └── ...
│
├── stages/
│   ├── discovery/          # ✅ 新
│   ├── branching/          # ✅ 新
│   ├── pruning/            # ✅ 新
│   ├── baseline/           # ✅
│   ├── optimize/           # ✅
│   ├── validate/           # ✅
│   ├── patch/            # ✅
│   ├── report.py          # ✅
│   │
│   └── *.py              # 🔲 24个旧文件待删除
│
├── cli/
│   └── main.py            # ✅
│
└── run_paths.py           # ✅ .sqlopt/已实现
```

---

## 注意事项

1. **每天开始前先 git pull 拉最新代码**
2. **两台电脑不要同时改同一个文件**
3. **删除文件前先确认是否有引用**
