# V10 测试设计

> 基于 mybatis-test 项目的真实数据进行测试设计

---

## 1. 测试分类

| 类型 | 说明 | 依赖 |
|------|------|------|
| **Unit Tests** | 单个模块/函数测试 | Mock 数据 |
| **Stage Tests** | 单阶段完整测试 | LLM Mock 生成的数据 |
| **Integration Tests** | 多阶段链式调用 | LLM Mock 或 真实数据 |
| **E2E Tests** | 完整流程测试 | 真实数据库 + LLM |

---

## 2. 测试目录结构

```
tests/
├── init/
│   ├── test_api.py
│   ├── test_scanner.py
│   ├── test_parser.py
│   ├── mocks/                    # LLM 生成的 mock 数据
│   └── test_with_real_mapper.py # 使用 mybatis-test 真实 mapper
│
├── parse/
│   ├── test_api.py
│   ├── test_branch_generator.py
│   ├── test_include_resolver.py
│   ├── test_risk_detector.py
│   ├── mocks/
│   └── test_with_real_mapper.py
│
├── recognition/
│   ├── test_api.py
│   ├── test_explain_collector.py
│   ├── test_baseline_runner.py
│   ├── mocks/
│   └── test_with_real_mapper.py    # 真实 EXPLAIN 测试
│
├── optimize/
│   ├── test_api.py
│   ├── test_rules_engine.py
│   ├── test_semantic_check.py
│   ├── test_llm_provider.py        # LLM 调用测试
│   ├── mocks/
│   └── test_with_real_baseline.py   # 基于真实 baseline 优化
│
├── result/
│   ├── test_api.py
│   ├── test_patch_generator.py
│   ├── test_report_generator.py
│   ├── mocks/
│   └── test_with_real_proposal.py
│
├── common/
│   ├── test_contracts.py
│   ├── test_config.py
│   ├── test_llm.py                 # 统一 LLM 调用测试
│   └── test_llm_mock_generator.py   # Mock 生成器测试
│
├── integration/
│   ├── test_full_pipeline.py         # 完整流程测试
│   ├── test_stage_chain.py          # 阶段链式调用
│   └── mocks/
│
└── real/                          # mybatis-test 迁移过来的真实测试
    ├── mybatis-test/               # 真实的 mybatis 项目
    ├── test_with_real_db.py        # 真实数据库测试
    └── test_with_real_llm.py       # 真实 LLM 测试
```

---

## 3. 各阶段测试用例

### 3.1 Init 阶段测试用例

```python
# tests/init/test_api.py

class TestInitStage:
    """Init 阶段完整测试"""
    
    def test_scan_single_mapper(self):
        """扫描单个 mapper 文件"""
        # 使用 UserMapper.xml
        pass
    
    def test_scan_multiple_mappers(self):
        """扫描多个 mapper 文件"""
        # 使用 UserMapper + OrderMapper + CommonMapper
        pass
    
    def test_extract_sql_units(self):
        """提取 SQL 单元"""
        pass
    
    def test_extract_table_schemas(self):
        """提取表结构信息"""
        pass
    
    def test_include_fragment_detection(self):
        """检测 include 片段引用"""
        pass

class TestInitWithRealMapper:
    """使用 mybatis-test 真实 mapper 测试"""
    
    def test_user_mapper_full_scan(self):
        """扫描 UserMapper.xml (95+ 场景)"""
        pass
    
    def test_order_mapper_cross_reference(self):
        """扫描 OrderMapper.xml (跨文件引用)"""
        pass
    
    def test_common_mapper_fragment_extraction(self):
        """提取 CommonMapper.xml 共享片段"""
        pass
    
    def test_extract_statistics_with_real_db(self):
        """连接真实数据库提取统计信息"""
        # 需要真实数据库连接
        pass
```

### 3.2 Parse 阶段测试用例

```python
# tests/parse/test_api.py

class TestParseStage:
    """Parse 阶段完整测试"""
    
    def test_resolve_include_refid(self):
        """解析 <include refid="xxx"> 引用"""
        # CommonMapper.xml 的片段被其他 mapper 引用
        pass
    
    def test_expand_if_branches(self):
        """展开 <if> 标签为分支"""
        # UserMapper.xml 场景 1-10
        pass
    
    def test_expand_foreach_branches(self):
        """展开 <foreach> 标签"""
        pass
    
    def test_expand_choose_branches(self):
        """展开 <choose> 标签"""
        pass
    
    def test_risk_detection(self):
        """风险检测"""
        pass

class TestParseWithRealMapper:
    """使用 mybatis-test 真实 mapper 测试"""
    
    def test_user_mapper_all_if_branches(self):
        """UserMapper.xml 全部 if 分支展开 (95+ 分支)"""
        pass
    
    def test_cross_file_include_resolution(self):
        """跨文件 include 解析"""
        # OrderMapper.xml 引用 CommonMapper.xml
        pass
    
    def test_complex_nested_branches(self):
        """复杂嵌套分支"""
        # 场景 46-55 (JOIN + if + foreach)
        pass
```

### 3.3 Recognition 阶段测试用例

```python
# tests/recognition/test_api.py

class TestRecognitionStage:
    """Recognition 阶段完整测试"""
    
    def test_collect_explain_postgresql(self):
        """PostgreSQL EXPLAIN 采集"""
        pass
    
    def test_collect_explain_mysql(self):
        """MySQL EXPLAIN 采集"""
        pass
    
    def test_baseline_execution(self):
        """基线执行"""
        pass
    
    def test_explain_plan_parsing(self):
        """执行计划解析"""
        pass

class TestRecognitionWithRealDB:
    """连接真实数据库的 EXPLAIN 测试"""
    
    @pytest.fixture
    def real_db_connection(self):
        """真实数据库连接"""
        # 使用 mybatis-test 的 H2 内存数据库
        # 或 MySQL/PostgreSQL 真实实例
        pass
    
    def test_seq_scan_detection(self):
        """检测 Seq Scan（全表扫描）"""
        # UserMapper.xml 场景 71-85 (Pagination) 可能触发
        pass
    
    def test_index_scan_detection(self):
        """检测 Index Scan"""
        pass
    
    def test_nested_loop_detection(self):
        """检测 Nested Loop"""
        pass
    
    def test_hash_join_detection(self):
        """检测 Hash Join"""
        pass
    
    def test_explain_with_parameters(self):
        """带参数的 EXPLAIN"""
        pass
```

### 3.4 Optimize 阶段测试用例

```python
# tests/optimize/test_api.py

class TestOptimizeStage:
    """Optimize 阶段完整测试"""
    
    def test_prefix_wildcard_fix(self):
        """LIKE '%xxx' → LIKE 'xxx%' 优化"""
        pass
    
    def test_unnecessary_select_star(self):
        """SELECT * 优化"""
        pass
    
    def test_missing_index_suggestion(self):
        """缺失索引建议"""
        pass
    
    def test_semantic_equivalence_check(self):
        """语义等价检查"""
        pass

class TestOptimizeWithLLM:
    """使用真实 LLM 的优化测试"""
    
    @pytest.fixture
    def real_llm(self):
        """真实 LLM 连接"""
        # 使用配置的 LLM (opencode_run 等)
        pass
    
    def test_llm_generates_proposal(self):
        """LLM 生成优化提案"""
        pass
    
    def test_llm_validates_semantic(self):
        """LLM 验证语义等价"""
        pass
    
    def test_proposals_with_real_baseline(self):
        """基于真实 baseline 生成提案"""
        pass

class TestOptimizeWithRealData:
    """使用 mybatis-test 真实数据的优化"""
    
    def test_optimize_user_mapper_all_branches(self):
        """优化 UserMapper.xml 所有分支"""
        pass
    
    def test_optimize_cross_file_reference(self):
        """优化跨文件引用"""
        pass
    
    def test_optimization_value_estimation(self):
        """优化价值评估"""
        # 基于 table_schemas.json 的 rowCount
        pass
```

### 3.5 Result 阶段测试用例

```python
# tests/result/test_api.py

class TestResultStage:
    """Result 阶段完整测试"""
    
    def test_patchable_proposals_to_patch(self):
        """可补丁的提案生成补丁"""
        pass
    
    def test_unpatchable_to_report(self):
        """不可补丁的生成报告"""
        pass
    
    def test_patch_file_generation(self):
        """补丁文件生成"""
        pass
    
    def test_report_markdown_generation(self):
        """报告 Markdown 生成"""
        pass

class TestResultWithRealProposal:
    """使用真实提案的 Result 测试"""
    
    def test_full_patch_application(self):
        """完整补丁应用"""
        pass
    
    def test_patch_with_xpath_location(self):
        """XPath 定位的补丁"""
        pass
    
    def test_report_with_full_evidence(self):
        """带完整证据的报告"""
        pass
```

---

## 4. Integration 测试用例

### 4.1 完整流程测试

```python
# tests/integration/test_full_pipeline.py

class TestFullPipeline:
    """完整流程测试"""
    
    @pytest.fixture
    def real_db(self):
        """真实数据库"""
        pass
    
    @pytest.fixture
    def real_llm(self):
        """真实 LLM"""
        pass
    
    def test_init_to_result_full_flow(self):
        """Init → Result 完整流程"""
        # 1. Init: 扫描 mybatis-test 的 mapper
        # 2. Parse: 展开分支
        # 3. Recognition: EXPLAIN 采集
        # 4. Optimize: 生成优化
        # 5. Result: 生成补丁/报告
        pass
    
    def test_parallel_branch_optimization(self):
        """并行分支优化"""
        pass
    
    def test_recovery_from_failure(self):
        """失败恢复"""
        pass
```

### 4.2 阶段链式测试

```python
# tests/integration/test_stage_chain.py

class TestStageChain:
    """阶段链式调用测试"""
    
    def test_init_then_parse_chain(self):
        """Init → Parse 链"""
        pass
    
    def test_parse_then_recognition_chain(self):
        """Parse → Recognition 链"""
        pass
    
    def test_recognition_then_optimize_chain(self):
        """Recognition → Optimize 链"""
        pass
    
    def test_optimize_then_result_chain(self):
        """Optimize → Result 链"""
        pass
```

---

## 5. Real Data 测试（mybatis-test 迁移）

### 5.1 迁移后的 mybatis-test 结构

```
tests/real/mybatis-test/
├── src/main/resources/mapper/
│   ├── UserMapper.xml      # 95+ 场景
│   ├── OrderMapper.xml     # 5 场景
│   └── CommonMapper.xml    # 共享片段
├── sqlopt.yml              # 测试用配置文件
└── init-mysql.sql         # MySQL 初始化脚本
└── init-postgresql.sql    # PostgreSQL 初始化脚本
```

### 5.2 Real DB 测试

```python
# tests/real/test_with_real_db.py

class TestWithRealDatabase:
    """真实数据库测试"""
    
    @pytest.fixture
    def mysql_db(self):
        """MySQL 数据库连接"""
        pass
    
    @pytest.fixture
    def postgresql_db(self):
        """PostgreSQL 数据库连接"""
        pass
    
    def test_init_with_real_mysql(self):
        """使用真实 MySQL 初始化"""
        pass
    
    def test_recognition_with_real_postgresql(self):
        """使用真实 PostgreSQL 执行 EXPLAIN"""
        pass
    
    def test_table_statistics_extraction(self):
        """表统计信息提取"""
        pass
```

### 5.3 Real LLM 测试

```python
# tests/real/test_with_real_llm.py

class TestWithRealLLM:
    """真实 LLM 测试"""
    
    @pytest.fixture
    def llm(self):
        """LLM 连接"""
        pass
    
    def test_mock_generation_quality(self):
        """Mock 生成质量"""
        # 使用 LLM 生成 mock 数据，验证是否符合 schema
        pass
    
    def test_optimization_proposal_quality(self):
        """优化提案质量"""
        pass
    
    def test_semantic_validation_accuracy(self):
        """语义验证准确性"""
        pass
```

---

## 6. Mock 数据生成测试

```python
# tests/common/test_llm_mock_generator.py

class TestLLMMockGenerator:
    """LLM Mock 生成器测试"""
    
    @pytest.fixture
    def generator(self):
        """Mock 生成器"""
        pass
    
    def test_generate_simple_sql_unit(self):
        """生成简单 SQL 单元"""
        prompt = "生成一个简单的 SELECT 语句，包含一个 if 条件"
        mock = generator.generate("init", prompt)
        assert validate_against_schema(mock, "sqlunit.schema.json")
        pass
    
    def test_generate_complex_branches(self):
        """生成复杂分支"""
        prompt = "生成一个包含 foreach、if、choose 嵌套的 SQL"
        mock = generator.generate("parse", prompt)
        pass
    
    def test_generate_full_explain_plan(self):
        """生成完整 EXPLAIN 计划"""
        prompt = "生成一个 PostgreSQL Index Scan 的完整 EXPLAIN JSON"
        mock = generator.generate("recognition", prompt)
        pass
    
    def test_generate_proposal_with_evidence(self):
        """生成带证据的提案"""
        prompt = "生成一个包含完整 baseline 和 rewritten 的优化提案"
        mock = generator.generate("optimize", prompt)
        pass
    
    def test_generate_invalid_data(self):
        """生成无效数据（错误处理测试）"""
        prompt = "生成一个缺少必填字段的无效数据"
        mock = generator.generate("init", prompt, valid=False)
        pass
```

---

## 7. 测试数据来源

### 7.1 mybatis-test Mapper 场景分类

| Mapper | 场景数 | 关键测试点 |
|--------|--------|-----------|
| UserMapper.xml | 95+ | if, where, foreach, choose, include, join, 聚合 |
| OrderMapper.xml | 5 | 跨文件引用 |
| CommonMapper.xml | - | 共享片段 |

### 7.2 重点测试场景

| 场景 | Mapper | 测试阶段 | 说明 |
|------|--------|---------|------|
| 场景 1-10 | UserMapper | Init + Parse | 基础动态 SQL |
| 场景 31-38 | UserMapper | Parse | SQL fragment include |
| 场景 46-55 | UserMapper | Recognition | JOIN + 聚合 EXPLAIN |
| 场景 56-70 | UserMapper | Recognition + Optimize | 聚合函数优化 |
| OrderMapper 跨文件 | OrderMapper | Parse | cross-file include |
| 场景 86-95 | UserMapper | Optimize | 跨文件片段优化 |

---

## 8. 测试执行方式

### 8.1 本地测试

```bash
# 运行单个阶段测试
cd tests/init/
python -m pytest test_api.py -v

# 使用 LLM 生成 mock 数据
sqlopt mock init "生成 UserMapper 的典型场景"

# 运行真实 mapper 测试
python -m pytest test_with_real_mapper.py -v
```

### 8.2 CI/CD 测试

```bash
# 完整测试
python -m pytest tests/ -v --llm=mock

# 真实 LLM 测试
python -m pytest tests/ -v --llm=real

# 真实数据库测试
python -m pytest tests/real/ -v --db=real
```

### 8.3 测试标记

```python
@pytest.mark.unit       # 单元测试
@pytest.mark.stage      # 阶段测试
@pytest.mark.integration # 集成测试
@pytest.mark.real_db    # 需要真实数据库
@pytest.mark.real_llm   # 需要真实 LLM
@pytest.mark.slow      # 慢速测试
```
