# SQL Optimizer Skill - Issue Tracker

> 使用 GitHub Issues 风格的 Checkbox 格式追踪问题

---

## Open Issues

- [ ] **#2 列名不匹配 (user_type vs type)** `[MEDIUM]` `2026-03-22`
  - MyBatis XML 中使用的列名与数据库实际列名不一致
  - 示例: XML 使用 `type`， 数据库列名是 `user_type`
  - 影响: `UserMapper.xml` 中的某些 SQL 可能失败

- [ ] **#3 动态 SQL 参数展开问题** `[MEDIUM]` `2026-03-22`
  - 含有 `${}` 动态表达式的 SQL 在 EXPLAIN 时会失败
  - 示例: `ORDER BY ${sortColumn} ${sortOrder}`
  - 影响: recognition 阶段的 EXPLAIN 执行会报错

- [ ] **#4 Recognition 阶段执行过慢** `[HIGH]` `2026-03-23`
  - 处理 110 个 SQL 单元时速度极慢，  - 根因: 串行处理、无并行化、无断点恢复
  - 涉及文件: `python/sqlopt/application/v9_stages/recognition.py`

- [ ] **#6 Workflow 状态管理问题** `[HIGH]` `2026-03-23`
  - `--to-stage optimize` 时，即使存在 baselines.json 也会重新运行 recognition
  - 根因: 超时后没有写入 state.json，workflow 引擎从上一完成阶段重新开始
  - 涉及文件: `python/sqlopt/application/workflow_v9.py`, `status_resolver.py`

---

## Resolved Issues

- [x] **#1 MyBatis Include 片段展开问题** `[HIGH]` `2026-03-23`
  - **问题**: `<include refid="..."/>` 跨文件引用展开不正确，导致生成的 SQL 为空白
  - **根因**: `_parse_mapper()` 只收集当前文件的 fragments，跨文件引用找不到
  - **解决方案**: 添加 `_build_global_fragment_registry()` 函数
    1. `Scanner.scan()` 先扫描所有 XML 文件，构建全局片段注册表
    2. `_parse_mapper()` 接受 `global_fragments` 参数
    3. 所有 include 引用从全局注册表解析
  - **涉及文件**: `python/sqlopt/application/v9_stages/init.py`
  - **提交**: (pending)

- [x] **#5 OpenCode Subprocess 在 Python 中挂起** `[HIGH]` `2026-03-23`
  - **问题**: `opencode run` 在 Python subprocess 中挂起
  - **解决方案**: 添加 `_get_opencode_cmd()` 函数
    - Windows: 返回 `[node_path, opencode_script]` 直接调用 node
    - Unix: 保持原样使用 `opencode` 命令
  - **涉及文件**: `python/sqlopt/llm/provider.py`
  - **提交**: `3e0ac87` - fix(llm): bypass Windows .CMD batch file

---

## Issue Details

### Issue #4: Recognition 阶段执行过慢

**问题描述**:
Recognition 阶段处理 110 个 SQL 单元时速度极慢，每个 SQL 单元需要数秒到数十秒。

**根因分析**:
1. 每个 SQL 单元可能有多个分支（动态 SQL 展开）
2. 每个分支执行 EXPLAIN 需要 10 秒超时
3. 串行处理，没有并行化
4. 超时时会话被终止，没有 state 保存

**修复方向**:
1. 增加并行处理（多进程/多线程）
2. 优化单个 EXPLAIN 的执行时间
3. 实现增量 state 保存，支持断点恢复

---

### Issue #6: Workflow 状态管理问题

**问题描述**:
使用 `--to-stage optimize` 时，即使 recognition 阶段已有 baselines.json，workflow 仍会重新运行 recognition。

**根因分析**:
1. recognition 超时后进程被杀死，没有写入 state.json
2. workflow 引擎检查 state 发现没有完成记录
3. 引擎从上一个完成的阶段重新开始（而非从 checkpoint 恢复）

**修复方向**:
1. 确保 recognition 阶段在超时前保存 state
2. 修改 workflow 引擎，在发现 baselines.json 存在时跳过 recognition
3. 实现 supervisor 的 checkpoint 机制

---

## Notes

- **测试环境**: `D:\01_workspace\test\mybatis-test`
- **数据库**: PostgreSQL at `localhost:5432`
- **测试配置**: `sqlopt.yaml` with LLM enabled (`opencode_run` provider)
