# SQL Optimizer 并行分工计划

> 创建日期：2026-03-18
> 分支：ai/refactor-stage-modules

---

## 任务概览

| 电脑 | 任务 | 依赖 |
|------|------|------|
| 电脑A | patch_stage + 删除旧stages/*.py + 重命名 | 无 |
| 电脑B | verify命令 + .sqlopt缓存 + 删除旧workflow | 无 |

---

## 电脑A：代码清理

### A1. 完善 patch_stage
```
文件: stages/patch_stage/patch_generator.py
从以下文件迁移逻辑:
- stages/patch_generate.py
- stages/patch_generate_llm.py
- stages/patch_verification.py
```

### A2. 删除旧stages/*.py文件
```
需删除 (13个文件):
- stages/optimize.py
- stages/validate.py
- stages/apply.py
- stages/patch_generate.py
- stages/patch_generate_llm.py
- stages/patch_verification.py
- stages/patch_decision_engine.py
- stages/patch_decision.py
- stages/patch_finalize.py
- stages/patch_formatting.py
- stages/patch_verification.py
- stages/patching_render.py
- stages/patching_results.py
- stages/patching_templates.py
```

### A3. 重命名 *_stage → *
```
baseline_stage/ → baseline/
optimize_stage/ → optimize/
validate_stage/ → validate/
patch_stage/ → patch/
```

---

## 电脑B：功能完善

### B1. 实现 verify 命令
```
文件: cli/main.py
功能: 证据链验证
参考: stages/patch_verification.py 现有逻辑
```

### B2. 实现 .sqlopt/ 缓存目录
```
文件: run_paths.py
目录结构:
.sqlopt/
├── cache/
│   ├── db_schemas/
│   └── sqlmap_cache/
└── history/
```

### B3. 删除旧 workflow 文件
```
删除 (确认V8稳定后):
- application/workflow_engine.py
- application/workflow_facade.py
- application/workflow_definition.py
- application/status_resolver.py
- application/run_repository.py
```

---

## 执行顺序

### 电脑A (按顺序执行)
```
A1 完善patch_stage → A2 删除旧stages/*.py → A3 重命名
```

### 电脑B (可并行执行)
```
B1 verify命令 → B2 .sqlopt缓存 → B3 删除旧workflow(最后)
```

---

## 注意事项

1. **A3和B3建议最后执行** - 确认V8稳定后再删旧文件
2. **A1需要先完成** - patch_stage是A2的前提
3. **两台电脑不要同时改同一个文件**
4. **每天开始前先 git pull 拉最新代码**
