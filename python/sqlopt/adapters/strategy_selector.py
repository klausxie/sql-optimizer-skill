"""
交互式策略选择模块 - 在 Scan 阶段询问用户选择测试策略
"""

from typing import Any


def suggest_strategy(unit: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """分析并建议测试策略"""
    branches = unit.get("branches", [])
    dynamic_features = unit.get("dynamicFeatures", [])
    if_count = len([f for f in dynamic_features if f == "IF"])
    
    # 预估分支数
    estimated_branches = len(branches)
    
    # 根据分支数智能建议
    if estimated_branches <= 4:
        recommended = "all_combinations"
        reason = "分支少，建议全覆盖"
    elif estimated_branches <= 16:
        recommended = "all_combinations"
        reason = "16个分支以内，全覆盖"
    else:
        recommended = "pairwise"
        reason = "分支多，用成对测试"
    
    return {
        "estimatedBranches": estimated_branches,
        "ifConditionCount": if_count,
        "recommended": recommended,
        "reason": reason,
        "options": [
            {
                "value": "all_combinations",
                "label": "全组合",
                "coverage": "100%",
                "desc": f"生成 {estimated_branches} 个分支，覆盖所有情况",
                "speed": "较慢"
            },
            {
                "value": "pairwise",
                "label": "成对测试",
                "coverage": "95%+",
                "desc": "测试每对条件组合，快速覆盖",
                "speed": "快"
            },
            {
                "value": "boundary",
                "label": "边界值",
                "coverage": "中等",
                "desc": "测试极端值和空值",
                "speed": "最快"
            }
        ]
    }


def build_strategy_prompt(units: list[dict[str, Any]]) -> str:
    """构建策略选择的提示信息"""
    lines = [
        "📊 分支分析结果：",
        ""
    ]
    
    for unit in units[:5]:  # 只显示前5个
        suggestion = suggest_strategy(unit, {})
        lines.append(f"• {unit.get('sqlKey')}")
        lines.append(f"  条件数: {suggestion['ifConditionCount']}, 预估分支: {suggestion['estimatedBranches']}")
        lines.append(f"  建议: {suggestion['recommended']} ({suggestion['reason']})")
        lines.append("")
    
    lines.extend([
        "请选择测试策略：",
        "1. [接受建议] - 使用智能推荐的策略",
        "2. [全组合] - 100%覆盖，较慢",
        "3. [成对测试] - 95%+覆盖，快速",
        "4. [边界值] - 覆盖极端情况，最快"
    ])
    
    return "\n".join(lines)


# 配置示例
STRATEGY_CONFIG = {
    "all_combinations": {
        "name": "全组合",
        "coverage": "100%",
        "description": "测试所有条件组合"
    },
    "pairwise": {
        "name": "成对测试",
        "coverage": "95%+",
        "description": "测试每对条件组合"
    },
    "boundary": {
        "name": "边界值",
        "coverage": "中等",
        "description": "测试极端值和空值"
    }
}
