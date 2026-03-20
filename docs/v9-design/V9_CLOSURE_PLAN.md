# V9 Closure Plan

> 目标：把当前“主干已 V9 化，但外围仍有旧语义残留”的状态，收口成真正单一、可维护、可测试的 V9 架构。

## 当前判断

当前仓库已经以 `init -> parse -> recognition -> optimize -> patch` 作为主工作流，但仍保留旧的 `diagnose / validate / apply / report / pipeline/*` 语义、路径和帮助文案。收口重点应从“继续引入 V9 能力”转为“删除并隔离非 V9 主流程语义”。

## 阶段化开发计划

### Phase 1: 单一事实来源（当前优先级最高）
- [x] 引入统一的 V9 pipeline 定义模块，集中维护 `STAGE_ORDER`、合法阶段校验、DB 依赖阶段集合。
- [x] 让 `workflow_v9`、`v9_stages.runtime`、`config_service`、`supervisor`、CLI 使用同一套定义。
- [x] 清理 CLI 中已经明显错误的旧示例（如 `--to-stage report`）。

### Phase 2: 运行时收口
- [ ] 清理 `run_paths.py` 中带 `diagnose / validate / apply / report` 的 deprecated 路径常量与 alias。
- [ ] 给 V9 明确唯一产物布局，停止新增对 `pipeline/*` 旧目录的依赖。
- [ ] 统一 `state.json` / `plan.json` / CLI status 输出的最终语义，确保 `supervisor` 状态成为唯一真相。

### Phase 3: 生命周期与状态机收口
- [x] 将 `status_resolver.py` 中的 `report` 特殊处理从 V9 主状态机中拆离。
- [ ] 让 `run_service.py` 主体只负责五阶段工作流；`apply`、`report` 相关逻辑下沉到单独后处理服务。
- [ ] 用阶段声明驱动 runtime prerequisites，而不是分散在多个入口写死规则。

### Phase 4: 命令与文档收口
- [ ] 清理 CLI 帮助、示例和命令说明中的旧阶段语义。
- [ ] 更新 `docs/v9-design/*` 中过时的“已完成”描述，改成基于当前代码的真实状态。
- [ ] 将仍然使用 V8/旧阶段命名的测试、脚本、README 逐步重命名。

### Phase 5: 删除兼容层
- [ ] 删除不再被引用的 compatibility wrapper、legacy comment、deprecated alias。
- [ ] 在测试中新增“不得接受旧阶段名/旧路径”的保护性断言。
- [ ] 最终形成“只能被理解成 V9”的主代码路径。

## 本轮实现范围

本轮先落地 Phase 1，并为后续 Phase 2/3 的大清理建立稳定的公共入口。
