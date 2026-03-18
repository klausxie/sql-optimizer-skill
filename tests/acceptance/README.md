# 验收测试 (CI)

端到端的质量保证测试，确保系统满足发布标准。

## 测试文件

| 文件 | 说明 |
|------|------|
| `release_acceptance.py` | 发布验收测试 |
| `verification_chain_acceptance.py` | 验证链验收 |
| `report_rebuild_acceptance.py` | 报告重建验收 |
| `opencode_smoke_acceptance.py` | OpenCode 冒烟测试 |
| `degraded_runtime_acceptance.py` | 降级运行验收 |
| `guidance_consistency_acceptance.py` | 指南一致性验收 |

## 运行方式

```bash
# 运行所有验收测试
python3 tests/acceptance/release_acceptance.py

# 运行单个验收测试
python3 tests/acceptance/verification_chain_acceptance.py
```

## 发布标准

所有验收测试必须通过才能发布：

1. **全流程测试**: 7个阶段全部完成
2. **验证链**: 产物正确传递
3. **报告重建**: 可从产物重建报告
4. **降级运行**: 部分阶段失败不影响其他阶段
5. **一致性**: 指南与实现一致

## CI 集成

这些测试在 CI pipeline 中自动运行：

```yaml
# .github/workflows/ci.yml
- name: Run Acceptance Tests
  run: |
    python3 tests/acceptance/release_acceptance.py
```
