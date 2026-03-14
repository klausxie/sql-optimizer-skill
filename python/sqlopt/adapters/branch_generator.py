"""
分支生成器 - 从 MyBatis XML 提取 SQL 并生成分支
"""

from typing import Any, Optional, List, Dict
import re

# 导入 scripting 模块（完整实现）
XMLScriptBuilder = None  # type: ignore[misc,assignment]
ScriptingBranchGenerator = None  # type: ignore[misc,assignment]
SCRIPTING_AVAILABLE = False

try:
    from sqlopt.scripting.xml_script_builder import XMLScriptBuilder  # type: ignore[misc]
    from sqlopt.scripting.branch_generator import (
        BranchGenerator as ScriptingBranchGenerator,  # type: ignore[misc]
    )

    SCRIPTING_AVAILABLE = True
except ImportError:
    pass


class BranchGenerator:
    """SQL 分支生成器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        branch_cfg = self.config.get("branch", {})
        self.max_branches = branch_cfg.get("max_branches", 100)
        self.strategy = branch_cfg.get("strategy", "auto")

    def generate(self, sql_unit: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成分支列表"""
        sql = sql_unit.get("sql", "")
        template_sql = sql_unit.get("templateSql", "")
        namespace = sql_unit.get("namespace")
        fragment_registry = self.config.get("_fragment_registry")

        # 优先使用 scripting 模块（完整实现）
        if SCRIPTING_AVAILABLE and template_sql:
            try:
                return self._generate_with_scripting(
                    template_sql,
                    namespace=namespace,
                    fragment_registry=fragment_registry,
                )
            except Exception:
                # scripting 失败时 fallback 到正则方法
                pass

        # 优先使用解析出来的条件列表
        conditions = sql_unit.get("_conditions", [])

        if not conditions:
            # 从模板SQL提取
            conditions = self._extract_if_conditions(template_sql or sql)

        if not conditions:
            # 无动态条件，返回单一分支（需要清理 SQL）
            return [
                {
                    "id": 1,
                    "conditions": [],
                    "sql": self._cleanup_sql(sql),
                    "type": "static",
                }
            ]

        # 根据策略选择生成方法
        strategy = self._select_strategy(len(conditions))

        if strategy == "all_combinations":
            branches = self._generate_all_combinations(conditions, sql, template_sql)
        elif strategy == "pairwise":
            branches = self._generate_pairwise(conditions, sql, template_sql)
        elif strategy == "boundary":
            branches = self._generate_boundary(conditions, sql, template_sql)
        else:
            branches = self._generate_all_combinations(conditions, sql, template_sql)

        return branches

    def _generate_with_scripting(
        self,
        template_sql: str,
        namespace: Optional[str] = None,
        fragment_registry: Any = None,
    ) -> List[Dict[str, Any]]:
        """使用 scripting 模块生成分支

        Args:
            template_sql: MyBatis XML 模板 SQL

        Returns:
            转换后的分支列表，格式兼容当前 API
        """
        assert SCRIPTING_AVAILABLE
        assert XMLScriptBuilder is not None
        assert ScriptingBranchGenerator is not None

        builder = XMLScriptBuilder(
            fragment_registry=fragment_registry,
            default_namespace=namespace,
        )
        sql_node = builder.parse(template_sql)

        scripting_gen = ScriptingBranchGenerator(
            strategy=self.strategy if self.strategy != "auto" else "all_combinations",
            max_branches=self.max_branches,
        )
        scripting_branches = scripting_gen.generate(sql_node)

        # 转换格式：scripting -> adapter API
        result = []
        for branch in scripting_branches:
            # 判断分支类型
            active_conds = branch.get("active_conditions", [])
            if not active_conds:
                branch_type = "static"
            elif len(active_conds) == 1:
                branch_type = "single"
            elif len(active_conds) == 2:
                branch_type = "pair"
            else:
                branch_type = "dynamic"

            result.append(
                {
                    "id": branch.get("branch_id", 0) + 1,
                    "conditions": active_conds,
                    "sql": branch.get("sql", ""),
                    "type": branch_type,
                }
            )

        return result

    def _select_strategy(self, condition_count: int) -> str:
        """智能选择策略"""
        if self.strategy != "auto":
            return self.strategy

        if condition_count <= 4:
            return "all_combinations"  # 16 以内
        elif condition_count <= 7:
            return "pairwise"
        else:
            return "pairwise"

    def _extract_if_conditions(self, template_sql: str) -> List[str]:
        """提取所有 if test 条件"""
        pattern = r'<if\s+test=["\']([^"\']+)["\']'
        matches = re.findall(pattern, template_sql)
        return matches

    def _generate_all_combinations(
        self, conditions: List[str], sql: str, template_sql: str
    ) -> List[Dict[str, Any]]:
        """全组合生成"""
        branches = []

        def generate_recursive(index: int, current_conditions: List[str]):
            if len(branches) >= self.max_branches:
                return

            if index == len(conditions):
                # 生成分支 SQL
                branch_sql = self._build_branch_sql(
                    template_sql or sql, conditions, current_conditions
                )
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "conditions": current_conditions.copy(),
                        "sql": branch_sql,
                        "type": "dynamic" if current_conditions else "static",
                    }
                )
                return

            # 条件成立
            generate_recursive(index + 1, current_conditions + [conditions[index]])
            # 条件不成立
            generate_recursive(index + 1, current_conditions)

        generate_recursive(0, [])
        return branches

    def _generate_pairwise(
        self, conditions: List[str], sql: str, template_sql: str
    ) -> List[Dict[str, Any]]:
        """成对测试生成"""
        branches = []

        # 全false作为基准
        branches.append(
            {
                "id": 1,
                "conditions": [],
                "sql": self._build_branch_sql(template_sql or sql, conditions, []),
                "type": "boundary",
            }
        )

        # 单独true
        for i, cond in enumerate(conditions):
            new_conditions = [conditions[i]]
            branches.append(
                {
                    "id": len(branches) + 1,
                    "conditions": new_conditions,
                    "sql": self._build_branch_sql(
                        template_sql or sql, conditions, new_conditions
                    ),
                    "type": "single",
                }
            )

        # 两两组合 (最多10个)
        for i in range(len(conditions)):
            for j in range(i + 1, len(conditions)):
                if len(branches) >= self.max_branches:
                    break
                new_conditions = [conditions[i], conditions[j]]
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "conditions": new_conditions,
                        "sql": self._build_branch_sql(
                            template_sql or sql, conditions, new_conditions
                        ),
                        "type": "pair",
                    }
                )

        return branches

    def _generate_boundary(
        self, conditions: List[str], sql: str, template_sql: str
    ) -> List[Dict[str, Any]]:
        """边界值分析"""
        branches = []

        # 全 false
        branches.append(
            {
                "id": 1,
                "conditions": [],
                "sql": self._build_branch_sql(template_sql or sql, conditions, []),
                "type": "boundary",
            }
        )

        # 全 true
        branches.append(
            {
                "id": 2,
                "conditions": conditions.copy(),
                "sql": self._build_branch_sql(
                    template_sql or sql, conditions, conditions
                ),
                "type": "boundary",
            }
        )

        # 第一个条件 true
        if conditions:
            branches.append(
                {
                    "id": 3,
                    "conditions": [conditions[0]],
                    "sql": self._build_branch_sql(
                        template_sql or sql, conditions, [conditions[0]]
                    ),
                    "type": "boundary",
                }
            )

        return branches

    def _build_branch_sql(
        self, template_sql: str, all_conditions: List[str], active_conditions: List[str]
    ) -> str:
        """构建分支 SQL

        根据active_conditions，从template_sql中移除不活跃的<if>块。

        Args:
            template_sql: 模板SQL（可能包含<if>标签）
            all_conditions: 所有可用条件
            active_conditions: 应该激活/为true的条件

        Returns:
            修改后的SQL字符串
        """
        if not all_conditions:
            return self._remove_xml_tags(template_sql)

        active_set = set(active_conditions)
        result = template_sql

        # 提取所有 if 块及其位置（使用更可靠的方法）
        if_blocks = self._extract_if_blocks(result)

        # 从后往前处理，避免索引偏移
        for block in reversed(if_blocks):
            block_condition = block["condition"]
            block_start = block["start"]
            block_end = block["end"]

            # 检查这个条件是否应该激活
            is_active = block_condition in active_set

            if is_active:
                # 激活：只移除 <if> 和 </if> 标签，保留内容
                result = result[:block_start] + block["content"] + result[block_end:]
            else:
                # 不激活：移除整个块
                result = result[:block_start] + result[block_end:]

        result = self._cleanup_sql(result)
        return result

    def _extract_if_blocks(self, sql: str) -> List[Dict[str, Any]]:
        """提取所有 <if> 块及其位置和条件"""
        blocks = []
        pattern = r'<if\s+test=(["\'])(.*?)\1\s*>'

        for match in re.finditer(pattern, sql):
            condition = match.group(2)
            start_pos = match.start()
            end_tag_pos = match.end()

            remaining = sql[end_tag_pos:]
            end_tag_match = re.search(r"</if>", remaining)
            if end_tag_match:
                content_start = end_tag_pos
                content_end = end_tag_pos + end_tag_match.start()
                content = sql[content_start:content_end]

                blocks.append(
                    {
                        "condition": condition,
                        "start": start_pos,
                        "end": end_tag_pos + end_tag_match.end(),
                        "content": content,
                    }
                )

        return blocks

    def _remove_xml_tags(self, sql: str) -> str:
        """移除所有XML标签，返回纯SQL"""
        # 移除 <if> 标签但保留内容
        result = re.sub(r'<if\s+test=["\'][^"\']*["\']\s*>', "", sql)
        result = re.sub(r"</if>", "", result)
        # 移除其他XML标签
        result = re.sub(r"<[^>]+>", "", result)
        return self._cleanup_sql(result.strip())

    def _activate_if_block(self, sql: str, condition: str) -> str:
        """激活一个if块 - 移除if标签但保留内容"""
        # 提取条件中的关键字来匹配（不转义操作符）
        key_parts = re.split(r"\s*[!=<>]=\s*|\s+", condition)
        key_word = key_parts[0] if key_parts else condition

        # 移除所有匹配的 <if test="..."> 标签（可能有多个）
        pattern = rf'<if\s+test=["\'].*?{re.escape(key_word)}.*?["\']\s*>'
        result = re.sub(pattern, "", sql)
        # 移除所有 </if> 标签
        result = re.sub(r"</if>", "", result)
        return result

    def _remove_if_block(self, sql: str, condition: str) -> str:
        """移除整个if块（包括内容）"""
        # 提取条件中的关键字来匹配
        key_parts = re.split(r"\s*[!=<>]=\s*|\s+", condition)
        key_word = key_parts[0] if key_parts else condition

        # 策略：找到所有 <if> 标签，逐个判断是否需要移除
        # 匹配 <if test="..."> 开头（不依赖 </if>）
        if_pattern = rf'<if\s+test=["\']([^"\']+)["\']'

        result = sql
        matches = list(re.finditer(if_pattern, result))

        # 从后往前处理，避免索引偏移
        for match in reversed(matches):
            test_attr = match.group(1)
            # 检查这个 if 块是否包含目标关键字
            test_key_parts = re.split(r"\s*[!=<>]=\s*|\s+", test_attr)
            test_key_word = test_key_parts[0] if test_key_parts else test_attr

            if test_key_word == key_word:
                # 找到匹配的 if 块，需要移除整个块
                # 找到 <if ...> 的结束位置
                start_pos = match.end()
                # 从该位置往后找对应的 </if>
                remaining = result[start_pos:]
                end_tag_match = re.search(r"</if>", remaining)
                if end_tag_match:
                    end_pos = start_pos + end_tag_match.end()
                    # 移除整个块
                    result = result[: match.start()] + result[end_pos:]

        return result

    def _cleanup_sql(self, sql: str) -> str:
        """清理SQL字符串"""
        result = sql

        # 移除所有剩余的 <if> 标签（包括内容）
        result = re.sub(
            r'<if\s+test=["\'][^"\']*["\']\s*>.*?</if>', "", result, flags=re.DOTALL
        )

        # 处理 <where> 标签：移除标签但保留内部内容，并确保有 WHERE 关键字
        where_matches = list(
            re.finditer(
                r"<where>(.*?)</where>", result, flags=re.DOTALL | re.IGNORECASE
            )
        )
        for match in where_matches:
            content = match.group(1).strip()
            if content:
                content = re.sub(r"^(AND|OR)\s+", "", content, flags=re.IGNORECASE)
                result = result.replace(match.group(0), f"WHERE {content}")
            else:
                result = result.replace(match.group(0), "")

        # 移除其他 MyBatis XML 标签（set, trim 等）
        result = re.sub(r"<(set|trim)[^>]*>", "", result, flags=re.IGNORECASE)
        result = re.sub(r"</(set|trim)>", "", result, flags=re.IGNORECASE)

        # 移除多余的空白
        result = re.sub(r"\s+", " ", result)

        # 修复 WHERE 子句
        result = re.sub(r"\bWHERE\s+AND\b", "WHERE", result)
        result = re.sub(r"\bWHERE\s+OR\b", "WHERE", result)

        # 修复 SET 子句
        result = re.sub(r"\bSET\s+,\s*", "SET ", result)
        result = re.sub(r",\s*,", ",", result)

        # 移除多余的逗号
        result = re.sub(r",\s*FROM", " FROM", result)
        result = re.sub(r",\s*WHERE", " WHERE", result)

        # 移除空的WHERE/SET
        result = re.sub(r"\bWHERE\s*;", ";", result)
        result = re.sub(r"\bSET\s*WHERE", " WHERE", result)

        return result.strip()


def generate_branches(
    sql_unit: Dict[str, Any], config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """生成分支的入口函数"""
    generator = BranchGenerator(config)
    return generator.generate(sql_unit)


# 配置示例
DEFAULT_CONFIG = {
    "branch": {
        "strategy": "auto",  # auto / all_combinations / pairwise / boundary / random
        "max_branches": 100,
        "force_mode": False,
    }
}
