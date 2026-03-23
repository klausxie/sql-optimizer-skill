# SQL Optimizer Skill - Issue Tracker

> 使用 GitHub Issues 风格的 Checkbox 格式追踪问题

---

## Open Issues

- [ ] **#2 列名不匹配 (user_type vs type)** `[MEDIUM]` `2026-03-22`
  - MyBatis XML 中使用的列名与数据库实际列名不一致
  - 示例: XML 使用 `type`， 数据库列名是 `user_type`
  - 影响: `UserMapper.xml` 中的某些 SQL 可能失败
  - **注意**: 需要外部 UserMapper.xml 修复，非本项目范畴

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
  - **提交**: `aa562e9`

- [x] **#3 动态 SQL 参数展开问题** `[MEDIUM]` `2026-03-23`
  - **问题**: `${}` 占位符在 EXPLAIN 时导致空 SQL 或未替换的占位符
  - **解决方案**: 在 `_run_explain()` 添加 guard
    1. 空 SQL 返回 `scan_type="EMPTY_SQL_GUARD"`
    2. 未替换的 `${}` 返回 `scan_type="DYNAMIC_SQL_UNSUBSTITUTED"`
  - **涉及文件**: `python/sqlopt/application/v9_stages/recognition.py`
  - **提交**: `5104bfc`

- [x] **#4 Recognition 阶段执行过慢** `[HIGH]` `2026-03-23`
  - **问题**: 处理 110 个 SQL 单元时速度极慢
  - **解决方案**:
    1. `ThreadPoolExecutor` 并行处理 (max_workers=4)
    2. 线程本地连接池复用
    3. 增量 checkpoint 每 10 条保存一次
  - **涉及文件**: `python/sqlopt/application/v9_stages/recognition.py`
  - **提交**: `5104bfc`

- [x] **#5 OpenCode Subprocess 在 Python 中挂起** `[HIGH]` `2026-03-23`
  - **问题**: `opencode run` 在 Python subprocess 中挂起
  - **解决方案**: 添加 `_get_opencode_cmd()` 函数
    - Windows: 返回 `[node_path, opencode_script]` 直接调用 node
    - Unix: 保持原样使用 `opencode` 命令
  - **涉及文件**: `python/sqlopt/llm/provider.py`
  - **提交**: `3e0ac87` - fix(llm): bypass Windows .CMD batch file

---

## Issue Details

### Issue #4: Recognition 阶段执行过慢 (已修复)

**问题描述**:
Recognition 阶段处理 110 个 SQL 单元时速度极慢，每个 SQL 单元需要数秒到数十秒。

**解决方案** (提交 `5104bfc`):
1. `ThreadPoolExecutor` 并行处理 (max_workers=4)
2. 线程本地连接池复用
3. 增量 checkpoint 每 10 条保存一次

---

### Issue #6: Workflow 状态管理问题 (已修复)

**问题描述**:
使用 `--to-stage optimize` 时，即使 recognition 阶段已有 baselines.json，workflow仍会重新运行 recognition。

**解决方案** (提交 `5104bfc`):
1. 在 `get_next_action()` 中检查 `baselines.json` 是否存在且完整
2. recognition 完成或跳过时更新 `completed_stages` 并保存 state

---

## Notes

- **测试环境**: `D:\01_workspace\test\mybatis-test`
- **数据库**: PostgreSQL at `localhost:5432`
- **测试配置**: `sqlopt.yaml` with LLM enabled (`opencode_run` provider)
