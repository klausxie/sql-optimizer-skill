# 数据契约总览

## 概述
数据契约是连接各阶段的核心数据结构。

## 阶段依赖关系
| 阶段 | 输入 | 输出 | 下游消费者 |
|------|------|------|------------|
| Init | 无 | InitOutput | Parse, Result |
| Parse | InitOutput | ParseOutput | Recognition |
| Recognition | ParseOutput | RecognitionOutput | Optimize, Result |
| Optimize | ParseOutput + RecognitionOutput | OptimizeOutput | Result |
| Result | OptimizeOutput | ResultOutput | 人类/下游 |

## 数据流图
InitStage → ParseStage → RecognitionStage → OptimizeStage → ResultStage

## 契约类型速查
| 契约文件 | 主要类型 |
|----------|----------|
| init.md | SQLUnit, InitOutput |
| parse.md | SQLBranch, ParseOutput |
| recognition.md | PerformanceBaseline, RecognitionOutput |
| optimize.md | OptimizationProposal, OptimizeOutput |
| result.md | Report, Patch, ResultOutput |
| common.md | 共享字段 |

## 跨阶段 ID 引用
- run_id: 流水线执行唯一标识
- sql_unit_id: SQL Unit 稳定标识
- path_id: 分支标识

## 文件生命周期
各阶段文件在阶段完成后即可被下游引用。