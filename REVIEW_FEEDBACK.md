# SQL Optimizer Skill 严厉评审

> 评审日期：2026-03-15
> 评审者：AI Agent (Sisyphus)
> 评审背景：对 `testWhereMultipleIf` SQL 进行完整优化流程测试

---

## 一、易用性：灾难级体验

### 1.1 SQL Key 的匹配逻辑是个谜

```bash
# 用户输入的是
--sql-key testWhereMultipleIf

# 返回的错误
SCAN_SELECTION_SQL_KEY_NOT_FOUND: scan selection did not match sql keys: testWhereMultipleIf
```

**为什么？** 因为实际的 key 是 `com.test.mapper.UserMapper.testWhereMultipleIf#v12`。

用户怎么知道要加命名空间？要加 `#v12`？这套 key 格式在哪定义的？有没有文档？有没有自动补全？

**用户根本不可能猜出来正确的 key 格式。**

### 1.2 命令行工具超时没有任何进度反馈

```bash
sqlopt-cli run --to-stage scan
# 然后就... 卡住了？
# 3 分钟后 timeout
```

用户在等什么？在扫描？在连接数据库？在生成什么？**一无所知。**

### 1.3 Windows 支持形同虚设

```cmd
@echo off
set "ROOT_DIR=%~dp0..\runtime"
"%ROOT_DIR%\.venv\Scripts\python.exe" ...
```

然后 bash 调用 `.cmd` 文件？路径里的反斜杠处理了吗？

最后不得不直接调用 Python 解释器才能跑起来。

---

## 二、引导精确性：完全是摆设

### 2.1 Skill 文档说要提示用户确认执行

> **⚠️ 必须交互提示**：
> "是否执行这些 SQL 获取实际性能数据？[Y/n]"

**实际呢？** 根本没有这个交互流程！

用户直接手动执行了 `/sql-execute`，工具自己就跑了，没有确认，没有提示。

### 2.2 "下一步建议"完全失灵

文档说：
> 扫描后 → **必须提示用户**："是否执行获取性能数据？"

**实际看到的输出：**
```
\u2139 run_id=run_e030942e6bb9
\u25b6 开始阶段：scan - Scanning MyBatis mapper files
[timeout]
```

然后呢？用户该干嘛？去哪看结果？怎么继续？

### 2.3 状态查询几乎无用

```json
{
  "run_status": "RUNNING",
  "current_phase": "scan",
  "phase_status": {"scan": "PENDING", ...}
}
```

`RUNNING` 但 `PENDING`？这是什么状态？在跑还是没跑？

---

## 三、脚本正确性：问题一堆

### 3.1 数据库配置错误时没有任何友好提示

```
"baseline": {
  "error": "connection to server at \"127.0.0.1\", port 5432 failed: FATAL: password authentication failed for user \"<user>\"\n"
}
```

这是 PostgreSQL 的错误！但项目用的是 MySQL！

**sqlopt.yml 的默认配置是占位符 `<user>:<password>`**，然后工具就傻傻地连 PostgreSQL 失败，失败了还把错误塞在 JSON 里面，完全不影响后续流程？

**为什么不检测配置有效性？为什么不提示用户配置数据库？**

### 3.2 扫描完成但超时，结果丢失

```
Found 1 SQL statements to analyze (selected 1 of 96)

<bash_metadata>
bash tool terminated command after exceeding timeout 60000 ms
```

明明扫描完成了，但因为 timeout，整个命令被杀掉。结果呢？去哪了？

用户必须手动去 `runs/run_xxx/` 目录找 JSON 文件才知道发生了什么。

### 3.3 16 个分支的 EXPLAIN 全是空

```json
"baseline": {
  "error": "connection to server...",
  "executionTime": null,
  "rowsExamined": null,
  "rowsReturned": null,
  "usingIndex": null
}
```

**所有 16 个分支的性能数据全是 null。**

那这 "执行阶段" 到底执行了什么？有执行吗？

---

## 四、输出质量：敷衍了事

### 4.1 所谓的 "优化建议" 是规则模板，不是真正的分析

看到的输出：

```
| 风险项 | 模式 | 风险等级 |
|--------|------|----------|
| 全字段查询 | SELECT * | 高 |
| 前缀通配符 | LIKE '%xxx' | 高 |
```

**这是通用规则匹配，不是针对这个 SQL 的分析。**

真正的分析应该告诉用户：
- 这张表有多少数据？
- 现有索引是什么？
- 实际执行计划是什么？
- 全表扫描会扫描多少行？

### 4.2 没有数据库元数据收集

表结构呢？索引列表呢？数据量呢？

**工具根本没有连接数据库收集这些信息。** 

所谓的 "执行" 只是把错误信息塞进 JSON 里，然后继续跑后面的阶段。

### 4.3 补丁生成是硬编码模板

```xml
SELECT id, name, email, status, type, created_at, updated_at
```

**你怎么知道这张表有这些字段？**

我是从 Spring Boot 测试里看到的实体类才知道的。工具根本没看表结构！

万一表里有 50 个字段呢？万一字段叫 `user_name` 不是 `name` 呢？

---

## 五、流程设计：断裂严重

### 5.1 阶段之间没有真正的衔接

```
scan → optimize → validate → patch_generate → report
```

实际上：
- scan "完成"（虽然 timeout）
- optimize 根本没跑起来
- validate 因为数据库连不上，全是错误
- patch_generate 生成通用模板
- report 汇报一堆空数据

**每个阶段都是独立的，失败不传播，错误不中断。**

### 5.2 `/sql-apply` 根本没用工具

最后用户直接用 `edit` 工具改的 XML 文件！

**sqlopt-cli apply 根本没被调用。**

那这个命令存在的意义是什么？

```bash
sqlopt-cli apply --run-id run_aa03564f80e8
```

试着跑了，它告诉我 "验证过的补丁已就绪可应用"，但实际上 patches 目录是空的！

---

## 六、最离谱的问题

### 工具自己没有完成任何有价值的分析

回顾整个过程：

| 工具声称做的 | 实际做的 |
|-------------|---------|
| 扫描 SQL | ✅ 确实找到了 SQL |
| 执行并收集性能数据 | ❌ 数据库连不上，全是 null |
| 分析瓶颈 | ❌ 只是规则匹配 `SELECT *` 和 `LIKE %` |
| 生成优化建议 | ❌ 通用模板，没有针对具体场景 |
| 应用补丁 | ❌ 用户手动改的文件 |

**这套工具的实际价值：帮用户找到了 SQL 在哪个文件。**

剩下的分析、优化、应用，全是 AI Agent 自己做的！

---

## 七、改进建议

### 7.1 必须修复的问题

#### 1. SQL Key 自动补全/提示
- 扫描后列出所有可用的 key
- 支持模糊匹配 `--sql-key testWhereMultipleIf`

```bash
# 期望的行为
$ sqlopt-cli run --sql-key testWhereMultipleIf
⚠ Multiple SQL keys match 'testWhereMultipleIf':
  1. com.test.mapper.UserMapper.testWhereMultipleIf#v12
  2. com.test.mapper.OrderMapper.testWhereMultipleIf#v3
  
Use full key or number: 
```

#### 2. 数据库连接验证
- 在 scan 阶段就验证 DSN 有效性
- 失败时立即报错并提示配置方法

```bash
# 期望的行为
$ sqlopt-cli run --to-stage scan
❌ Database connection failed
   DSN: mysql://root:root@localhost:3306/sqlopt_test
   Error: Access denied for user 'root'@'localhost'

To fix:
  1. Check sqlopt.yml → db.dsn
  2. Run: sqlopt-cli validate-config
```

#### 3. 收集真正的数据库元数据
- 表结构 `DESCRIBE table`
- 索引列表 `SHOW INDEX`
- 数据量 `SELECT COUNT(*)`
- 实际 EXPLAIN 结果

#### 4. 超时处理
- 不要让 bash timeout 杀掉进程
- 后台运行 + 状态轮询
- 断点续跑

### 7.2 用户体验改进

#### 1. 进度可视化

```
[1/4] Scanning mapper files... ✓ Found 92 SQL statements
[2/4] Connecting to MySQL... ✓ Connected to sqlopt_test
[3/4] Analyzing testWhereMultipleIf... 
      - Branch 1/16: SELECT * FROM users (0.001s, full scan)
      - Branch 2/16: SELECT * FROM users WHERE type = ? (0.002s, idx_type)
      ...
```

#### 2. 失败时的具体指导

```
❌ Database connection failed
   DSN: mysql://root:root@localhost:3306/sqlopt_test
   Error: Access denied for user 'root'

To fix:
  1. Check your sqlopt.yml configuration
  2. Run: sqlopt-cli validate-config
  3. Docs: https://docs.sql-optimizer.dev/config
```

#### 3. 真正的优化分析

```
Analysis for testWhereMultipleIf:

Table: users (估测 100,000 行)
现有索引: PRIMARY(id), idx_email(email)

Branch 5 (email LIKE '%xxx%'):
- EXPLAIN: type=ALL, rows=100000, Extra=Using where
- 问题: email 索引无法用于前导通配符
- 建议: 考虑全文索引或 Elasticsearch

Branch 3 (status = ?):
- EXPLAIN: type=ref, rows=5000, key=idx_status
- 问题: 无，可用索引
```

### 7.3 架构改进建议

#### 1. 错误传播机制
- 任一阶段失败应该停止后续阶段
- 错误应该累积并最终报告
- 支持跳过失败继续运行（可选）

#### 2. 真正的补丁系统
- 补丁应该基于实际表结构生成
- 支持多个候选补丁供选择
- 应用前预览 diff

#### 3. 配置验证命令
```bash
sqlopt-cli validate-config
# 检查: DSN 格式、数据库连接、mapper 路径、LLM 配置
```

#### 4. 交互式模式
```bash
sqlopt-cli run --interactive
# 发现问题后暂停，询问用户如何处理
```

---

## 八、测试用例清单

### 必须通过的测试场景

| # | 场景 | 预期行为 |
|---|------|----------|
| 1 | DSN 配置错误 | 立即报错，提示修复方法 |
| 2 | SQL Key 部分匹配 | 列出所有匹配项或自动选择唯一匹配 |
| 3 | 数据库连接超时 | 友好错误，建议检查网络/防火墙 |
| 4 | 表不存在 | 提示表名，建议检查 schema |
| 5 | 动态 SQL 16 分支 | 实际执行并收集每个分支的性能数据 |
| 6 | 无索引表 | 建议创建索引，给出 CREATE INDEX 语句 |
| 7 | 已优化 SQL | 报告 "无需优化"，说明原因 |
| 8 | Windows 路径 | 正确处理反斜杠和空格 |

---

## 总结

这套工具目前的状态：**框架搭好了，但核心功能是空的。**

| 阶段 | 状态 | 说明 |
|------|------|------|
| 扫描 | ✅ | 能找到 SQL |
| 执行 | ❌ | 连不上数据库继续跑 |
| 分析 | ❌ | 只是规则匹配 |
| 优化 | ❌ | 通用模板 |
| 应用 | ❌ | patches 目录空的 |

**用户用这套工具，最后还是得靠自己分析问题、自己想方案、自己改代码。**

那这套工具的价值在哪？

---

## 优先级排序

### P0 - 立即修复
1. SQL Key 模糊匹配
2. 数据库连接验证 + 友好错误
3. 实际执行 EXPLAIN 并收集结果

### P1 - 本周修复
4. 进度可视化
5. 表结构/索引元数据收集
6. Windows 路径处理

### P2 - 下个版本
7. 交互式模式
8. 多候选补丁
9. 配置验证命令

---

*评审结束*
