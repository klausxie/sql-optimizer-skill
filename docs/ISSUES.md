# SQL Optimizer Skill - Issue Tracker

## Open Issues

| # | Issue | Severity | Status | Created |
|---|-------|----------|--------|---------|
| 1 | MyBatis Include 片段展开问题 | HIGH | Open | 2026-03-22 |
| 2 | 列名不匹配 (user_type vs type) | MEDIUM | Open | 2026-03-22 |
| 3 | 动态 SQL 参数展开问题 | MEDIUM | Open | 2026-03-22 |
| 4 | Recognition 阶段执行过慢 | HIGH | Open | 2026-03-23 |
| 5 | OpenCode Subprocess 在 Python 中挂起 | HIGH | Open | 2026-03-23 |
| 6 | Workflow 状态管理问题 | HIGH | Open | 2026-03-23 |

---

## Issue Details

### Issue #1: MyBatis Include 片段展开问题

**严重程度**: HIGH

**问题描述**:
`<include refid="..."/>` 标签展开不正确，导致生成的 SQL 无效。

**复现步骤**:
```bash
cd D:\01_workspace\test\mybatis-test
sqlopt.exe --verbose run --config sqlopt.yaml --to-stage init --run-id test
```

**预期行为**:
```sql
SELECT id, order_no, user_id, status, amount, created_at, updated_at
FROM orders o
```

**实际行为**:
```sql
SELECT 
        ,
        ,
           
FROM orders o
```

**影响阶段**:
- init 阶段: SQL 单元的 `sql` 字段包含未展开的 include 或错误的空白
- parse 阶段: 分支继承自 init 的无效 SQL
- recognition 阶段: EXPLAIN 执行失败（语法错误）
- optimize 阶段: 可能生成错误的优化建议

**根因分析**:
`python/sqlopt/application/v9_stages/init.py` 中的 `_render_logical_text` 函数在处理 `<include>` 标签时：
1. 可能没有正确递归展开片段
2. 空白处理可能导致列名之间产生多余逗号和换行

**涉及文件**:
- `python/sqlopt/application/v9_stages/init.py`
- `python/sqlopt/shared/xml_utils.py` (如果有)

**相关 XML 文件**:
- `tests/real/mybatis-test/src/main/resources/mapper/OrderMapper.xml`
- `tests/real/mybatis-test/src/main/resources/mapper/CommonMapper.xml`

---

### Issue #2: 列名不匹配 (user_type vs type)

**严重程度**: MEDIUM

**问题描述**:
MyBatis XML 中使用的列名与数据库实际列名不一致。

**示例**:
- XML 使用: `type`
- 数据库列: `user_type`

**影响**:
- `UserMapper.xml` 中的 `testChooseWithMultipleIf` 等 SQL 可能失败

---

### Issue #3: 动态 SQL 参数展开问题

**严重程度**: MEDIUM

**问题描述**:
含有 `${}` 动态表达式的 SQL 在 EXPLAIN 时会失败。

**示例**:
```sql
ORDER BY ${sortColumn} ${sortOrder}
```

**影响**:
- recognition 阶段的 EXPLAIN 执行会报错

---

### Issue #4: Recognition 阶段执行过慢

**严重程度**: HIGH

**问题描述**:
Recognition 阶段处理 110 个 SQL 单元时速度极慢，每个 SQL 单元需要数秒到数十秒。在 5 分钟超时内只能完成约 20 个 SQL 单元。

**根因分析**:
1. 每个 SQL 单元可能有多个分支（动态 SQL 展开）
2. 每个分支执行 EXPLAIN 需要 10 秒超时
3. 串行处理，没有并行化
4. 超时时会话被终止，但没有 state 保存，导致无法恢复

**影响**:
- 无法在合理时间内完成 recognition
- 即使使用 `fix_test2` 的 baselines，也是因为 recognition 完成过（之前某次运行）
- workflow 引擎在 `--to-stage optimize` 时会重新检查并尝试运行 recognition

**涉及文件**:
- `python/sqlopt/application/v9_stages/recognition.py`

**可能的修复方向**:
1. 增加并行处理（多进程/多线程）
2. 优化单个 EXPLAIN 的执行时间
3. 实现增量 state 保存，支持断点恢复

---

### Issue #5: OpenCode Subprocess 在 Python 中挂起

**严重程度**: HIGH

**问题描述**:
`opencode run` 命令在终端中可以正常工作，但在 Python `subprocess.run()` 中调用时会挂起，超时后失败。

**复现步骤**:
```python
import subprocess
import shutil
full_path = shutil.which('opencode')  # 返回 D:\dev\data\nodejs\node_global\opencode.CMD
cmd = [full_path, 'run', '--format', 'json', 'hello']
proc = subprocess.run(cmd, capture_output=True, text=False, timeout=5)  # 挂起
```

**预期行为**:
命令应该返回 JSON 输出或错误信息

**实际行为**:
命令挂起，直到超时

**根因分析**:
可能是 Windows 上 .CMD 文件的执行问题。当使用完整路径 `D:\dev\data\nodejs\node_global\opencode.CMD` 时，Python subprocess 不正确处理 Windows batch 文件的执行。

**涉及文件**:
- `python/sqlopt/llm/provider.py` (_run_opencode 函数)
- `python/sqlopt/subprocess_utils.py` (run_capture_text 函数)

**影响**:
- optimize 阶段无法调用 LLM
- 无法生成 SQL 优化建议

**可能的修复方向**:
1. 使用 `shell=True` 调用 batch 文件（安全性需评估）
2. 使用 `start /wait` Windows 命令包装
3. 使用 `pyopencode` 库替代 subprocess 调用
4. 实现 OpenAI compatible API 模式（HTTP 调用）

---

### Issue #6: Workflow 状态管理问题

**严重程度**: HIGH

**问题描述**:
使用 `--to-stage optimize` 时，即使 recognition 阶段已有 baselines.json，workflow 仍会重新运行 recognition。

**根因分析**:
1. recognition 超时后进程被杀死，没有写入 state.json
2. workflow 引擎检查 state 发现没有完成记录
3. 引擎从上一个完成的阶段重新开始（而非从 checkpoint 恢复）

**涉及文件**:
- `python/sqlopt/application/workflow_v9.py`
- `python/sqlopt/application/status_resolver.py`

**影响**:
- 无法使用已有的 baselines 跳过 recognition
- 每次都需要等待 recognition 完成

**可能的修复方向**:
1. 确保 recognition 阶段在超时前保存 state
2. 修改 workflow 引擎，在发现 baselines.json 存在时跳过 recognition
3. 实现 supervisor 的 checkpoint 机制

---

## Resolved Issues

暂无

---

## Notes

- **测试环境**: `D:\01_workspace\test\mybatis-test`
- **数据库**: PostgreSQL at `localhost:5432`
- **测试配置**: `sqlopt.yaml` with LLM enabled (`opencode_run` provider)
