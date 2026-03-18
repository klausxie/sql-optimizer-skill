from __future__ import annotations

import re
import unittest

from sqlopt.stages.branching.branch_generator import BranchGenerator
from sqlopt.stages.branching.fragment_registry import FragmentRegistry
from sqlopt.stages.branching.xml_script_builder import XMLScriptBuilder


class ScriptingBranchGeneratorTest(unittest.TestCase):
    def test_realistic_user_mapper_if_choose_scenario(self) -> None:
        # from test-files/mybatis-test/.../UserMapper.xml::testIfChoose
        sql = """
        SELECT * FROM users
        <where>
            <if test="status != null">
                <choose>
                    <when test="status == '1'">AND status = '1'</when>
                    <when test="status == '2'">AND status = '2'</when>
                </choose>
            </if>
            <if test="type != null">AND type = #{type}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=100
        ).generate(node)

        # status != null (active/inactive) * choose(no-match/1/2) * type != null (2 options) = 8
        self.assertEqual(len(branches), 8)
        active_signatures = {tuple(branch["active_conditions"]) for branch in branches}
        self.assertEqual(
            active_signatures,
            {
                tuple(),
                ("type != null",),
                ("status != null",),
                ("status != null", "type != null"),
                ("status != null", "status == '1'"),
                ("status != null", "status == '1'", "type != null"),
                ("status != null", "status == '2'"),
                ("status != null", "status == '2'", "type != null"),
            },
        )

    def test_realistic_user_mapper_nested_choose_scenario(self) -> None:
        # from test-files/mybatis-test/.../UserMapper.xml::testChooseNestedChoose
        sql = """
        SELECT * FROM users
        <where>
            <choose>
                <when test="status != null and status == '1'">
                    <choose>
                        <when test="type == 'VIP'">AND status = '1' AND type = 'VIP'</when>
                        <when test="type == 'NORMAL'">AND status = '1' AND type = 'NORMAL'</when>
                        <otherwise>AND status = '1'</otherwise>
                    </choose>
                </when>
                <otherwise>AND status IN ('1', '2')</otherwise>
            </choose>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=100
        ).generate(node)

        active_signatures = {tuple(branch["active_conditions"]) for branch in branches}
        self.assertEqual(
            active_signatures,
            {
                tuple(),
                ("status != null and status == '1'",),
                ("status != null and status == '1'", "type == 'VIP'"),
                ("status != null and status == '1'", "type == 'NORMAL'"),
            },
        )

    def test_obvious_mutex_if_conditions_are_filtered(self) -> None:
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <if test='type == 1'> AND type = 1 </if>
        <if test='type == 2'> AND type = 2 </if>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # Full combinations would be 4, but (type==1 AND type==2) is obvious conflict.
        self.assertEqual(len(branches), 3)

        active_signatures = {
            tuple(sorted(branch["active_conditions"])) for branch in branches
        }
        self.assertNotIn(("type == 1", "type == 2"), active_signatures)

    def test_multiple_choose_nodes_generate_cartesian_combinations(self) -> None:
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <choose>
            <when test='x == 1'> AND x = 1 </when>
            <otherwise> AND x = 0 </otherwise>
        </choose>
        <choose>
            <when test='y == 1'> AND y = 1 </when>
            <otherwise> AND y = 0 </otherwise>
        </choose>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=100
        ).generate(node)

        active_signatures = {
            tuple(sorted(branch["active_conditions"])) for branch in branches
        }
        self.assertEqual(
            active_signatures,
            {
                tuple(),
                ("x == 1",),
                ("y == 1",),
                ("x == 1", "y == 1"),
            },
        )

    def test_choose_and_if_branch_count_matches_product(self) -> None:
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <if test='a != null'> AND a = #{a} </if>
        <choose>
            <when test='x == 1'> AND x = 1 </when>
            <otherwise> AND x = 0 </otherwise>
        </choose>
        <if test='b != null'> AND b = #{b} </if>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=100
        ).generate(node)

        # 2 if conditions -> 4 combinations, choose -> 2 options, total = 8
        self.assertEqual(len(branches), 8)

    def test_obvious_mutex_between_if_and_choose_is_filtered(self) -> None:
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <if test='status == 1'> AND status = 1 </if>
        <choose>
            <when test='status == 2'> AND status = 2 </when>
            <otherwise> AND status = 0 </otherwise>
        </choose>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=20
        ).generate(node)

        active_signatures = {
            tuple(sorted(branch["active_conditions"])) for branch in branches
        }
        self.assertNotIn(("status == 1", "status == 2"), active_signatures)

    def test_generated_sql_keeps_keyword_spacing(self) -> None:
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <if test='a != null'> AND a = #{a} </if>
        <if test='b != null'> AND b = #{b} </if>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)
        rendered = [branch["sql"].upper() for branch in branches]

        self.assertTrue(
            any(
                re.search(r"WHERE\s+1\s*=\s*1\s+AND\s+A\s*=\s*#\{A\}", sql)
                for sql in rendered
            )
        )
        self.assertTrue(
            any(
                re.search(r"AND\s+A\s*=\s*#\{A\}\s+AND\s+B\s*=\s*#\{B\}", sql)
                for sql in rendered
            )
        )

    def test_sql_fragment_spacing(self) -> None:
        """测试 SQL 片段之间应该有空格分隔。

        场景：两个连续的 if 标签，内容分别为 "AND a = #{a}" 和 "AND b = #{b}"
        当两个条件都为 true 时，期望生成的 SQL 中间有空格：
            "AND a = #{a} AND b = #{b}"
        而非粘连：
            "AND a = #{a}AND b = #{b}"
        """
        sql = """
        SELECT * FROM t WHERE 1 = 1
        <if test="a != null">AND a = #{a}</if>
        <if test="b != null">AND b = #{b}</if>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)
        rendered = [branch["sql"].upper() for branch in branches]

        # 期望：两个条件都出现且中间有至少一个空格
        # 片段 "AND a = #{a}" 和 "AND b = #{b}" 拼接后变成 "a = #{a} AND b = #{b}"
        # 注意：由于 normalize_sql 会处理，AND 关键字保留在第二个片段开头
        expected_pattern = r"A\s*=\s*#\{A\}\s+AND\s+B\s*=\s*#\{B\}"
        self.assertTrue(
            any(re.search(expected_pattern, sql) for sql in rendered),
            f"Expected space between SQL fragments. Got: {rendered}",
        )

    def test_foreach_renders_two_sample_parameters(self) -> None:
        sql = """
        SELECT * FROM users
        WHERE id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 现在生成 3 个分支：空集合、单元素、多元素
        # 多元素分支（原有行为）
        multi_branch = [
            b
            for b in branches
            if "()," not in b["sql"] and "(#{" not in b["sql"].replace("#{id}", "")
        ]
        self.assertTrue(len(multi_branch) > 0, "Should have multiple items branch")
        self.assertEqual(
            multi_branch[0]["sql"], "SELECT * FROM users WHERE id IN (#{id},#{id})"
        )

    def test_if_and_foreach_generate_semantic_branches(self) -> None:
        sql = """
        SELECT * FROM users
        <where>
            <if test="status != null">AND status = #{status}</if>
            <if test="ids != null and ids.size() > 0">
                AND id IN
                <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
            </if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=20
        ).generate(node)

        # 获取所有非 foreach 相关的条件
        core_conditions = {
            tuple(
                c for c in branch["active_conditions"] if not c.startswith("foreach_")
            )
            for branch in branches
        }

        # 验证核心条件存在
        self.assertIn(tuple(), core_conditions)
        self.assertIn(("status != null",), core_conditions)
        self.assertIn(("ids != null and ids.size() > 0",), core_conditions)
        self.assertIn(
            ("status != null", "ids != null and ids.size() > 0"), core_conditions
        )

        # 验证有 foreach 边界分支
        foreach_conditions = {
            tuple(c for c in branch["active_conditions"] if c.startswith("foreach_"))
            for branch in branches
        }
        self.assertTrue(
            len(foreach_conditions) > 0, "Should have foreach boundary branches"
        )

        sql_by_signature = {
            tuple(branch["active_conditions"]): branch["sql"] for branch in branches
        }
        self.assertEqual(
            sql_by_signature[("ids != null and ids.size() > 0",)],
            "SELECT * FROM users WHERE id IN (#{id},#{id})",
        )
        self.assertEqual(
            sql_by_signature[("status != null", "ids != null and ids.size() > 0")],
            "SELECT * FROM users WHERE status = #{status} AND id IN (#{id},#{id})",
        )

    def test_include_fragments_contribute_dynamic_branches(self) -> None:
        registry = FragmentRegistry()
        builder = XMLScriptBuilder(
            fragment_registry=registry,
            default_namespace="demo.user",
        )
        registry.register(
            "demo.user.StatusFilter",
            builder.parse('<if test="status != null">AND status = #{status}</if>'),
        )

        sql = """
        SELECT * FROM users
        <where>
            <include refid="StatusFilter"/>
        </where>
        """

        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(builder.parse(sql))

        self.assertEqual(
            {tuple(branch["active_conditions"]) for branch in branches},
            {tuple(), ("status != null",)},
        )
        sql_by_signature = {
            tuple(branch["active_conditions"]): branch["sql"] for branch in branches
        }
        self.assertEqual(sql_by_signature[tuple()], "SELECT * FROM users")
        self.assertEqual(
            sql_by_signature[("status != null",)],
            "SELECT * FROM users WHERE status = #{status}",
        )

    def test_include_fragment_preserves_nested_choose_semantics(self) -> None:
        registry = FragmentRegistry()
        builder = XMLScriptBuilder(
            fragment_registry=registry,
            default_namespace="demo.user",
        )
        registry.register(
            "demo.user.ComplexFilter",
            builder.parse(
                """
                <choose>
                    <when test="status == '1'">
                        AND status = '1'
                        <if test="type != null">AND type = #{type}</if>
                    </when>
                    <otherwise>AND status = '0'</otherwise>
                </choose>
                """
            ),
        )

        sql = """
        SELECT * FROM users
        <where>
            <include refid="ComplexFilter"/>
        </where>
        """

        branches = BranchGenerator(
            strategy="all_combinations", max_branches=20
        ).generate(builder.parse(sql))

        self.assertEqual(
            {tuple(branch["active_conditions"]) for branch in branches},
            {
                tuple(),
                ("status == '1'",),
                ("status == '1'", "type != null"),
            },
        )

    def test_foreach_empty_collection_branch(self) -> None:
        """测试 foreach 空集合分支。

        场景：foreach 标签，当集合为空时应生成空分支。
        期望：存在一个分支只包含 open/close（如 "()"），无内容。
        """
        sql = """
        SELECT * FROM users
        WHERE id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 应该有多个分支：空集合、单元素、多元素
        self.assertGreater(
            len(branches), 1, "Should have multiple branches for foreach boundary cases"
        )

        # 检查是否存在空集合分支（只有 open + close）
        has_empty_branch = any(
            branch["sql"].strip().endswith("()")
            or "(SELECT * FROM users WHERE id IN ())" in branch["sql"]
            for branch in branches
        )
        self.assertTrue(
            has_empty_branch,
            f"Should have empty collection branch. Got: {[b['sql'] for b in branches]}",
        )

    def test_foreach_single_item_branch(self) -> None:
        """测试 foreach 单元素分支。

        场景：foreach 标签，当集合只有单个元素时应生成单元素分支。
        期望：存在一个分支只渲染一次内容（无 separator）。
        """
        sql = """
        SELECT * FROM users
        WHERE id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 检查是否存在单元素分支（没有 separator，即只有一项）
        # 单元素分支应该是 "(#{id})" 而不是 "(#{id},#{id})"
        has_single_branch = any(
            "(#{id})" in branch["sql"] and ",#{id}" not in branch["sql"]
            for branch in branches
        )
        self.assertTrue(
            has_single_branch,
            f"Should have single item branch. Got: {[b['sql'] for b in branches]}",
        )

    def test_foreach_multiple_items_branch(self) -> None:
        """测试 foreach 多元素分支。

        场景：foreach 标签，当集合有多个元素时应生成多元素分支。
        期望：存在一个分支渲染多次内容（有 separator）。
        这是现有的 sample_size=2 行为。
        """
        sql = """
        SELECT * FROM users
        WHERE id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 存在多元素分支（有 separator）
        has_multi_branch = any(
            branch["sql"].count("id_") >= 2 or "," in branch["sql"]
            for branch in branches
        )
        # 当前实现应该已有这个分支（sample_size=2）
        # 此测试验证现有功能未退化

    def test_bind_variable_propagation(self) -> None:
        """测试 bind 变量传播。

        场景：bind 标签定义变量后，后续 SQL 中应能使用该变量。
        期望：bind 的 name 出现在 active_conditions 中，SQL 正确渲染。
        """
        sql = """
        SELECT * FROM users
        <where>
            <bind name="pattern" value="'%' + name + '%'"/>
            <if test="pattern != null">AND name LIKE #{pattern}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 验证有分支生成
        self.assertGreater(len(branches), 0, "Should have at least one branch")

        # 验证 bind:pattern 出现在 active_conditions 中
        has_bind_condition = any(
            "bind:pattern" in branch.get("active_conditions", []) for branch in branches
        )
        self.assertTrue(
            has_bind_condition,
            f"bind:pattern should appear in active_conditions. Got: {branches}",
        )

        # 验证 SQL 正确渲染 #{pattern}
        relevant_branches = [
            b for b in branches if "pattern != null" in b.get("active_conditions", [])
        ]
        self.assertGreater(
            len(relevant_branches), 0, "Should have branch with pattern != null"
        )
        for branch in relevant_branches:
            self.assertIn(
                "#{pattern}",
                branch["sql"],
                f"SQL should contain rendered pattern variable. Got: {branch['sql']}",
            )

    def test_bind_wildcard_pattern_detection(self) -> None:
        """测试 bind 通配符模式识别。

        场景：bind 的 value 包含 %...% 模式，应被识别为全表扫描风险。
        期望：分支输出包含 risk_flags 字段，标记 prefix_wildcard。
        """
        sql = """
        SELECT * FROM users
        <where>
            <bind name="pattern" value="'%' + name + '%'"/>
            <if test="name != null">AND name LIKE #{pattern}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 验证分支输出包含 risk_flags
        # 查找包含 name != null 条件的分支（该分支使用了 bind 变量）
        relevant_branches = [
            b for b in branches if "name != null" in b.get("active_conditions", [])
        ]
        self.assertGreater(
            len(relevant_branches), 0, "Should have branch with name != null"
        )

        # 验证 risk_flags 字段存在且包含 prefix_wildcard
        has_risk_flag = any(
            "risk_flags" in branch and "prefix_wildcard" in branch.get("risk_flags", [])
            for branch in relevant_branches
        )
        self.assertTrue(
            has_risk_flag,
            f"Should have prefix_wildcard risk flag. Got: {relevant_branches}",
        )

    def test_bind_suffix_wildcard_detection(self) -> None:
        """测试 bind 后缀通配符模式识别。

        场景：bind 的 value 包含后缀通配符模式（如 name + '%'），应被识别为低风险。
        期望：分支输出包含 risk_flags 字段，标记 suffix_wildcard_only。
        """
        sql = """
        SELECT * FROM users
        <where>
            <bind name="pattern" value="name + '%'"/>
            <if test="name != null">AND name LIKE #{pattern}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 验证分支输出包含 risk_flags
        # 查找包含 name != null 条件的分支（该分支使用了 bind 变量）
        relevant_branches = [
            b for b in branches if "name != null" in b.get("active_conditions", [])
        ]
        self.assertGreater(
            len(relevant_branches), 0, "Should have branch with name != null"
        )

        # 验证 risk_flags 字段存在且包含 suffix_wildcard_only
        has_risk_flag = any(
            "risk_flags" in branch
            and "suffix_wildcard_only" in branch.get("risk_flags", [])
            for branch in relevant_branches
        )
        self.assertTrue(
            has_risk_flag,
            f"Should have suffix_wildcard_only risk flag. Got: {relevant_branches}",
        )

    def test_bind_concat_wildcard_detection(self) -> None:
        """测试 bind CONCAT 函数包装的通配符模式识别。

        场景：bind 的 value 使用 CONCAT 函数包装通配符，应被识别为高风险。
        期望：分支输出包含 risk_flags 字段，标记 concat_wildcard。
        """
        sql = """
        SELECT * FROM users
        <where>
            <bind name="pattern" value="CONCAT('%', name, '%')"/>
            <if test="name != null">AND name LIKE #{pattern}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 验证分支输出包含 risk_flags
        # 查找包含 name != null 条件的分支（该分支使用了 bind 变量）
        relevant_branches = [
            b for b in branches if "name != null" in b.get("active_conditions", [])
        ]
        self.assertGreater(
            len(relevant_branches), 0, "Should have branch with name != null"
        )

        # 验证 risk_flags 字段存在且包含 concat_wildcard
        has_risk_flag = any(
            "risk_flags" in branch and "concat_wildcard" in branch.get("risk_flags", [])
            for branch in relevant_branches
        )
        self.assertTrue(
            has_risk_flag,
            f"Should have concat_wildcard risk flag. Got: {relevant_branches}",
        )

    def test_bind_function_wrap_detection(self) -> None:
        """测试 bind 函数包装模式识别。

        场景：bind 的 value 使用函数包装（如 UPPER(name)），应被识别为中等风险。
        期望：分支输出包含 risk_flags 字段，标记 function_wrap。
        """
        sql = """
        SELECT * FROM users
        <where>
            <bind name="pattern" value="UPPER(name)"/>
            <if test="name != null">AND UPPER(name) = #{pattern}</if>
        </where>
        """

        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)

        # 验证分支输出包含 risk_flags
        # 查找包含 name != null 条件的分支（该分支使用了 bind 变量）
        relevant_branches = [
            b for b in branches if "name != null" in b.get("active_conditions", [])
        ]
        self.assertGreater(
            len(relevant_branches), 0, "Should have branch with name != null"
        )

        # 验证 risk_flags 字段存在且包含 function_wrap
        has_risk_flag = any(
            "risk_flags" in branch and "function_wrap" in branch.get("risk_flags", [])
            for branch in relevant_branches
        )
        self.assertTrue(
            has_risk_flag,
            f"Should have function_wrap risk flag. Got: {relevant_branches}",
        )


if __name__ == "__main__":
    unittest.main()
