# SQL Optimizer 测试目录

## 目录结构

```
tests/
├── README.md              # 本文件
│
├── unit/                  # 单元测试
│   ├── README.md
│   ├── test_baseline_module.py
│   ├── test_branching_module.py
│   └── ...
│
├── integration/           # 集成测试 (各阶段)
│   ├── README.md
│   ├── test_discovery/
│   ├── test_branching/
│   ├── test_pruning/
│   ├── test_baseline/
│   ├── test_optimize/
│   ├── test_validate/
│   └── test_patch/
│
├── e2e/                   # 端到端全流程测试
│   ├── README.md
│   ├── test_v8_full_flow_mysql.py
│   ├── test_v8_full_flow_pg.py
│   ├── test_v8_full_flow_mysql_complex.py
│   └── test_v8_full_flow_pg_complex.py
│
├── acceptance/            # 验收测试 (CI)
│   ├── README.md
│   ├── release_acceptance.py
│   ├── verification_chain_acceptance.py
│   └── ...
│
└── fixtures/             # 测试数据和配置
    ├── README.md
    ├── simple_mappers/
    └── complex_mappers/
```

## 测试类型

| 类型 | 位置 | 说明 | 运行方式 |
|------|------|------|----------|
| 单元测试 | `unit/` | 单个组件/函数测试 | `pytest tests/unit/` |
| 集成测试 | `integration/` | 阶段级测试 | `pytest tests/integration/` |
| 端到端 | `e2e/` | 完整流程测试 | `pytest tests/e2e/` |
| 验收测试 | `acceptance/` | CI发布验收 | `python tests/acceptance/*.py` |

## 快速开始

### 运行所有测试

```bash
# pytest 运行单元+集成+e2e
python3 -m pytest tests/ -v

# 运行特定类型
python3 -m pytest tests/unit/ -v          # 单元测试
python3 -m pytest tests/integration/ -v  # 集成测试
python3 -m pytest tests/e2e/ -v          # 端到端测试
```

### 端到端全流程测试

```bash
# MySQL 简单SQL全流程
python3 -m pytest tests/e2e/test_v8_full_flow_mysql.py -v

# PostgreSQL 简单SQL全流程
python3 -m pytest tests/e2e/test_v8_full_flow_pg.py -v

# MySQL 复杂动态SQL全流程
python3 -m pytest tests/e2e/test_v8_full_flow_mysql_complex.py -v

# PostgreSQL 复杂动态SQL全流程
python3 -m pytest tests/e2e/test_v8_full_flow_pg_complex.py -v

# 或运行所有 e2e 测试
python3 -m pytest tests/e2e/ -v
```

### 验收测试

```bash
python3 tests/acceptance/release_acceptance.py
```

## V8 七阶段

| 阶段 | 单元测试 | 集成测试 | E2E测试 |
|------|----------|----------|----------|
| discovery | test_discovery_module.py | integration/test_discovery/ | ✓ |
| branching | test_branching_module.py | integration/test_branching/ | ✓ |
| pruning | - | integration/test_pruning/ | ✓ |
| baseline | test_baseline_module.py | integration/test_baseline/ | ✓ |
| optimize | - | integration/test_optimize/ | ✓ |
| validate | - | integration/test_validate/ | ✓ |
| patch | - | integration/test_patch/ | ✓ |

## 测试数据

测试数据（MyBatis XML mappers）存放在 `fixtures/` 目录：

- `simple_mappers/` - 简单SQL，不含动态标签
- `complex_mappers/` - 复杂动态SQL，含 if/choose/foreach 等

## 数据库配置

测试使用真实数据库：

### MySQL
- Host: 100.101.41.123:3306
- Database: sqlopt_test
- User: root
- Password: root

### PostgreSQL
- Host: 100.101.41.123:5432
- Database: postgres
- User: postgres
- Password: postgres

## 数据契约

数据契约定义在 `contracts/` 目录，JSON Schema 规范。

详见 `contracts/README.md`
