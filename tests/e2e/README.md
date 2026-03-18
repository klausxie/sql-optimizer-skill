# E2E 端到端全流程测试

测试完整的 V8 七阶段流水线：Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch

## 测试文件

| 文件 | 数据库 | SQL类型 | SQL单元数 |
|------|--------|---------|----------|
| `test_v8_full_flow_mysql.py` | MySQL | 简单SQL | 6 |
| `test_v8_full_flow_pg.py` | PostgreSQL | 简单SQL | 6 |
| `test_v8_full_flow_mysql_complex.py` | MySQL | 复杂动态SQL | 10 |
| `test_v8_full_flow_pg_complex.py` | PostgreSQL | 复杂动态SQL | 10 |

## 数据库配置

### MySQL
- Host: 100.101.41.123:3306
- Database: sqlopt_test
- User: root / Password: root

### PostgreSQL
- Host: 100.101.41.123:5432
- Database: postgres
- User: postgres / Password: postgres

## 运行方式

```bash
# 运行所有 e2e 测试
python3 -m pytest tests/e2e/ -v

# 运行单个测试
python3 -m pytest tests/e2e/test_v8_full_flow_mysql.py -v

# 直接运行 Python 脚本
python3 tests/e2e/test_v8_full_flow_mysql.py
```

## 简单SQL vs 复杂SQL

### 简单SQL (6个SQL)
无动态标签，每个SQL只产生1个分支。

### 复杂动态SQL (10个SQL)
包含动态标签: `<if>`, `<choose>`, `<foreach>`, `<where>`, `<set>`

## 验证内容

1. **7个阶段全部完成**: discovery → branching → pruning → baseline → optimize → validate → patch
2. **所有产物文件生成**: 每个阶段产生对应的 JSON 产物
3. **分支生成**: branching 阶段正确展开动态标签
4. **风险检测**: pruning 阶段检测到预定义的风险类型
5. **基线采集**: baseline 阶段成功采集执行计划
6. **优化建议**: optimize 阶段使用 opencode_run LLM 生成建议
7. **验证完成**: validate 阶段完成语义验证
8. **补丁生成**: patch 阶段生成 XML 补丁

## 调试技巧

### 查看详细输出
```bash
python3 tests/e2e/test_v8_full_flow_mysql.py 2>&1 | head -100
```

### 单独运行到某阶段
修改测试中的 `to_stage` 参数：
```python
run_service.start_run(config_path, to_stage="baseline", ...)  # 只跑到baseline
```

### 查看产物
测试运行后查看临时目录下的 `runs/<run_id>/`：
```
runs/<run_id>/
├── discovery/sql_units.json
├── branching/sql_units_with_branches.json
├── pruning/risks.json
├── baseline/baselines.json
├── optimize/proposals.json
├── validate/validations.json
└── patch/patches.json
```
