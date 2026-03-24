# 分支展开能力概览

## 1. 当前实现

### 1.1 代码来源

分支模块从 `ai/refactor-stage-modules` 迁移，v10的阶梯采样策略已合并。

### 1.2 模块结构

```
python/sqlopt/stages/branching/
├── __init__.py
├── branch_generator.py      # 主生成器
├── branch_strategy.py       # 策略基类 + 4种策略
├── branch_context.py        # 分支上下文
├── dynamic_context.py       # 动态上下文
├── expression_evaluator.py   # 表达式评估
├── fragment_registry.py      # SQL片段注册
├── mutex_branch_detector.py # 互斥分支检测(choose)
├── sql_node.py             # SQL节点树
├── xml_language_driver.py   # XML语言驱动
├── xml_script_builder.py    # XML脚本构建
└── strategies/
    └── __init__.py
```

---

## 2. 支持的动态SQL标签

| 标签 | 状态 | 说明 |
|------|------|------|
| `<if test="">` | ✅ 已实现 | 基础条件判断 |
| `<choose>/<when>/<otherwise>` | ✅ 已实现 | 多选一，互斥分支 |
| `<where>` | ✅ 已实现 | 自动处理AND/OR |
| `<set>` | ✅ 已实现 | 动态SET(用于UPDATE) |
| `<trim>` | ✅ 已实现 | 前后缀处理 |
| `<foreach>` | 🔧 部分 | 循环展开(需要测试) |
| `<include refid="">` | ✅ 已实现 | SQL片段引用 |
| `<bind>` | ✅ 已实现 | 变量绑定 |

---

## 3. 策略体系

### 3.1 四种策略对比

| 策略 | 策略名 | 覆盖范围 | 分支数(15条件) | 召回率估算 |
|------|--------|----------|----------------|------------|
| **AllCombinationsStrategy** | 全组合 | 2^n | 32768 | 100% |
| **PairwiseStrategy** | 成对 | 每条件单独 | 15 | ~40% |
| **BoundaryStrategy** | 边界值 | all F + all T | 2 | ~20% |
| **LadderSamplingStrategy** | 阶梯采样 | 单因子+两两+三阶+贪心 | 50-100 | ~62-82% |

### 3.2 LadderSamplingStrategy 详解

**阶梯设计**：

```
Step 1: 单因子覆盖 (16个)
        ↓
Step 2: 高权重两两交互 (~20个)
        ↓
Step 3: 高权重三阶交互 (~5个)
        ↓
Step 4: 贪心得分填充 (~9个)
        ↓
总计: ~50个
```

**召回率估算（假设100个真慢SQL）**：

| 问题类型 | 占比 | 覆盖率 | 贡献 |
|----------|------|--------|------|
| 单因子问题 | 60% | 100% | 60% |
| 两两交互问题 | 25% | ~40% | 10% |
| 三阶交互问题 | 10% | ~15% | 1.5% |
| **总计** | 95% | - | **~71.5%** |

### 3.3 策略选择建议

| 场景 | 推荐策略 | 理由 |
|------|----------|------|
| 开发调试，快速验证 | `boundary` | 最快，2个分支 |
| 日常分析，平衡覆盖与成本 | `ladder` | ~70%召回，50个分支 |
| 上线前检查，追求全面 | `ladder` (budget=100) | ~82%召回 |
| 确保100%覆盖 | `all_combinations` | 全部展开 |

---

## 4. 互斥分支检测

### 4.1 choose结构处理

```xml
<choose>
  <when test="type == 'A'">...A...</when>
  <when test="type == 'B'">...B...</when>
  <otherwise>...default...</otherwise>
</choose>
```

**展开结果**：4个互斥分支（不是2^4=16）
- when_A: type=='A'
- when_B: type=='B'
- otherwise: 其他
- all False

### 4.2 MutexBranchDetector

```python
class MutexBranchDetector:
    def detect_choose_branches(self, choose_node):
        # 每个when一个分支 + otherwise一个分支
        # 不展开成所有组合
```

---

## 5. 配置使用

### 5.1 通过BranchGenerator使用

```python
from sqlopt.stages.branching import BranchGenerator

generator = BranchGenerator(
    strategy="ladder",    # all_combinations | pairwise | boundary | ladder
    max_branches=50      # 预算控制
)

branches = generator.generate(sql_node)
```

### 5.2 通过工厂函数创建

```python
from sqlopt.stages.branching.branch_strategy import create_strategy

strategy = create_strategy("ladder")
```

---

## 6. 与v10 Parse阶段的关系

```
v10 Parse阶段
    ↓
使用 BranchGenerator 生成分支
    ↓
应用辅助策略:
    - 死代码识别 (A1)
    - 条件互斥分析 (A2)
    - 等价分支合并
    - 采样压缩 (LadderSamplingStrategy)
    ↓
输出带优先级的分支列表
```

---

## 7. 待完善功能

| 功能 | 优先级 | 状态 |
|------|--------|------|
| 嵌套if正确递归展开 | P0 | 🔧 待验证 |
| foreach边界展开 | P1 | 🔧 待测试 |
| 元数据增强打分 | P2 | 🔧 可集成到LadderSamplingStrategy |
| 分支血缘追踪 | P3 | 🔧 长期 |

---

*文档版本：v2.0*
*更新日期：2026-03-24*
*更新内容：合并ai/refactor-stage-modules模块，添加LadderSamplingStrategy*
