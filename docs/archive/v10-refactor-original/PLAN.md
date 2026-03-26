# V10 重构计划 - 空壳先行

> SQL Optimizer V10 五阶段架构重构执行计划

## 概述

- **目标**: 构建可运行的空壳，核心逻辑后续迁移
- **原则**: 空壳先行，逻辑后填
- **依赖**: Wave 1 → Wave 2 → Wave 3 → Wave 4

## TODOs

### Wave 1: 数据契约定义（Foundation）

- [x] 1. 定义 InitOutput 契约 - `python/sqlopt/contracts/init.py`
- [x] 2. 定义 ParseOutput 契约 - `python/sqlopt/contracts/parse.py`
- [x] 3. 定义 RecognitionOutput 契约 - `python/sqlopt/contracts/recognition.py`
- [x] 4. 定义 OptimizeOutput 契约 - `python/sqlopt/contracts/optimize.py`
- [x] 5. 定义 ResultOutput 契约 - `python/sqlopt/contracts/result.py`
- [x] 6. 契约序列化工具 - `python/sqlopt/contracts/__init__.py`, `base.py`

### Wave 2: 公共模块

- [x] 7. 配置加载 (config.py) - `python/sqlopt/common/config.py`
- [x] 8. 错误定义 (errors.py) - `python/sqlopt/common/errors.py`
- [x] 9. 进度跟踪 (progress.py) - `python/sqlopt/common/progress.py`
- [x] 10. 路径管理 (run_paths.py) - `python/sqlopt/common/run_paths.py`
- [x] 11. LLM Mock Provider - `python/sqlopt/common/llm_mock_generator.py`
- [x] 12. 数据库连接器 Stub - `python/sqlopt/common/db_connector.py`
- [x] 13. 阶段基类 - `python/sqlopt/stages/base.py`

### Wave 3: CLI + 空壳阶段

- [x] 14. CLI 入口 - `python/sqlopt/cli/main.py`
- [x] 15. Init 阶段空壳 - `python/sqlopt/stages/init/stage.py`
- [x] 16. Parse 阶段空壳 - `python/sqlopt/stages/parse/stage.py`
- [x] 17. Recognition 阶段空壳 - `python/sqlopt/stages/recognition/stage.py`
- [x] 18. Optimize 阶段空壳 - `python/sqlopt/stages/optimize/stage.py`
- [x] 19. Result 阶段空壳 - `python/sqlopt/stages/result/stage.py`
- [x] 20. 阶段调度器 - `python/sqlopt/stage_runner.py`

### Wave 4: 测试基础设施

- [ ] 21. 单元测试 - 契约
- [ ] 22. 单元测试 - 公共模块
- [ ] 23. 单元测试 - CLI
- [ ] 24. 单元测试 - 各阶段空壳
- [ ] 25. 集成测试 - 阶段流
- [ ] 26. Mock Fixtures

### Final Verification Wave

- [ ] F1. Plan Compliance Audit
- [ ] F2. Code Quality Review
- [ ] F3. CLI 功能验收
- [ ] F4. Scope Fidelity Check

## 执行文件

详细设计文档位于 `.sisyphus/plans/v10-refactor/`:
- `EXECUTION_PLAN.md` - 完整执行计划
- `ARCHITECTURE.md` - 总体架构
- `STANDARDS.md` - Python 代码规范

