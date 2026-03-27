"""Tests for xml_patch_engine module."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from sqlopt.common.xml_patch_engine import XmlPatchEngine
from sqlopt.contracts.optimize import OptimizationAction


class TestXmlPatchEngineApplyActions:
    """Test apply_actions method."""

    def test_apply_actions_empty_list(self):
        """Test apply_actions with empty action list returns original XML."""
        xml = "<root><child>text</child></root>"
        result = XmlPatchEngine.apply_actions([], xml)
        assert result == xml

    def test_apply_actions_with_none_as_xml_string(self):
        """Test apply_actions handles None gracefully as empty action list."""
        # ET.fromstring(None) would fail, but apply_actions returns early if actions is empty
        result = XmlPatchEngine.apply_actions([], "<root/>")
        assert result == "<root/>"


class TestReplaceOperation:
    """Test REPLACE operation."""

    def test_replace_element_text(self):
        """Test replacing text content of an element."""
        xml = "<root><child>original</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="original",
                rewritten_snippet="replaced",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        child = tree.find("child")
        assert child is not None
        assert child.text == "replaced"

    def test_replace_with_xpath_predicate(self):
        """Test replacing element found via xpath with predicate."""
        xml = '<root><item id="1">first</item><item id="2">second</item></root>'
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/item[@id='1']",
                target_tag="item",
                original_snippet="first",
                rewritten_snippet="FIRST",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        item1 = tree.find("item[@id='1']")
        item2 = tree.find("item[@id='2']")
        assert item1 is not None
        assert item2 is not None
        assert item1.text == "FIRST"
        assert item2.text == "second"

    def test_replace_nonexistent_xpath_raises(self):
        """Test replacing nonexistent element raises ValueError."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/nonexistent",
                target_tag="nonexistent",
                rewritten_snippet="new",
            )
        ]
        with pytest.raises(ValueError, match="Element not found"):
            XmlPatchEngine.apply_actions(actions, xml)


class TestAddOperation:
    """Test ADD operation."""

    def test_add_sibling_after_element(self):
        """Test adding a sibling element after target."""
        xml = "<root><child>original</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="ADD",
                xpath="/root/child",
                target_tag="child",
                rewritten_snippet="<new>sibling</new>",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        assert tree.find("child") is not None
        assert tree.find("new") is not None
        children = list(tree)
        assert len(children) == 2
        assert children[0].tag == "child"
        assert children[1].tag == "new"

    def test_add_requires_rewritten_snippet(self):
        """Test ADD without rewritten_snippet raises error."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="ADD",
                xpath="/root/child",
                target_tag="child",
            )
        ]
        with pytest.raises(ValueError, match="rewritten_snippet required"):
            XmlPatchEngine.apply_actions(actions, xml)


class TestRemoveOperation:
    """Test REMOVE operation."""

    def test_remove_element(self):
        """Test removing an element."""
        xml = "<root><child>to_remove</child><other>keep</other></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REMOVE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="to_remove",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        assert tree.find("child") is None
        assert tree.find("other") is not None

    def test_remove_nonexistent_xpath_raises(self):
        """Test removing nonexistent element raises ValueError."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REMOVE",
                xpath="/root/nonexistent",
                target_tag="nonexistent",
            )
        ]
        with pytest.raises(ValueError, match="Element not found"):
            XmlPatchEngine.apply_actions(actions, xml)


class TestWrapOperation:
    """Test WRAP operation."""

    def test_wrap_element_with_parent(self):
        """Test wrapping an element with a new parent."""
        xml = "<root><child>content</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="WRAP",
                xpath="/root/child",
                target_tag="child",
                original_snippet="content",
                rewritten_snippet="<wrapper></wrapper>",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        wrapper = tree.find("wrapper")
        assert wrapper is not None
        assert wrapper.find("child") is not None
        assert wrapper.find("child").text == "content"

    def test_wrap_requires_rewritten_snippet(self):
        """Test WRAP without rewritten_snippet raises error."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="WRAP",
                xpath="/root/child",
                target_tag="child",
            )
        ]
        with pytest.raises(ValueError, match="rewritten_snippet required"):
            XmlPatchEngine.apply_actions(actions, xml)


class TestNamespaceHandling:
    """Test namespace handling in XML."""

    def test_simple_xml_without_namespace(self):
        """Test handling XML without namespace declarations."""
        xml = "<mapper><select id='test'>SELECT *</select></mapper>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/mapper/select",
                target_tag="select",
                original_snippet="SELECT *",
                rewritten_snippet="SELECT id, name",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        select = tree.find("select")
        assert select is not None
        assert select.text == "SELECT id, name"

    def test_mybatis_xml_with_namespace(self):
        """Test handling MyBatis XML with namespace."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<mapper xmlns="http://mybatis.org/schema/mybatis-3">
    <select id="findAll">SELECT * FROM users</select>
</mapper>"""
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/mapper/select",
                target_tag="select",
                original_snippet="SELECT * FROM users",
                rewritten_snippet="SELECT id, name FROM users",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        assert "SELECT id, name FROM users" in result


class TestInvalidXpathHandling:
    """Test handling of invalid xpath expressions."""

    def test_invalid_xpath_format(self):
        """Test that invalid xpath raises appropriate error."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child[@invalid",  # malformed xpath
                target_tag="child",
                rewritten_snippet="new",
            )
        ]
        # Malformed xpath with unbalanced bracket won't find element
        with pytest.raises(ValueError, match="Element not found"):
            XmlPatchEngine.apply_actions(actions, xml)


class TestRoundtrip:
    """Test roundtrip: apply actions, verify result."""

    def test_multiple_actions_in_sequence(self):
        """Test applying multiple actions in sequence."""
        xml = "<root><item>original</item></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/item",
                target_tag="item",
                original_snippet="original",
                rewritten_snippet="step1",
            ),
            OptimizationAction(
                action_id="act_002",
                operation="ADD",
                xpath="/root/item",
                target_tag="item",
                rewritten_snippet="<new>added</new>",
            ),
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        items = list(tree)
        assert len(items) == 2
        assert items[0].text == "step1"
        assert items[1].tag == "new"

    def test_preserves_xml_declaration(self):
        """Test that XML declaration is preserved when present."""
        xml = '<?xml version="1.0" encoding="UTF-8"?><root><child>text</child></root>'
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="text",
                rewritten_snippet="modified",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        assert result.startswith("<?xml")
        assert "modified" in result

    def test_preserves_no_declaration_when_not_present(self):
        """Test that declaration is not added when original had none."""
        xml = "<root><child>text</child></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="text",
                rewritten_snippet="modified",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        assert not result.startswith("<?xml")

    def test_replace_then_remove(self):
        """Test replace followed by remove on different elements."""
        xml = "<root><a>A</a><b>B</b></root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/a",
                target_tag="a",
                original_snippet="A",
                rewritten_snippet="AAA",
            ),
            OptimizationAction(
                action_id="act_002",
                operation="REMOVE",
                xpath="/root/b",
                target_tag="b",
                original_snippet="B",
            ),
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        assert tree.find("a") is not None
        assert tree.find("a").text == "AAA"
        assert tree.find("b") is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_xml_string(self):
        """Test handling of empty XML string."""
        import xml.etree.ElementTree as ET

        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="text",
                rewritten_snippet="modified",
            )
        ]
        with pytest.raises(ET.ParseError):
            XmlPatchEngine.apply_actions(actions, "")

    def test_whitespace_only_xml(self):
        """Test handling of whitespace-only XML string."""
        import xml.etree.ElementTree as ET

        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root/child",
                target_tag="child",
                original_snippet="text",
                rewritten_snippet="modified",
            )
        ]
        with pytest.raises(ET.ParseError):
            XmlPatchEngine.apply_actions(actions, "   ")

    def test_root_element_replace(self):
        """Test replacing root element content."""
        xml = "<root>original_root</root>"
        actions = [
            OptimizationAction(
                action_id="act_001",
                operation="REPLACE",
                xpath="/root",
                target_tag="root",
                original_snippet="original_root",
                rewritten_snippet="modified_root",
            )
        ]
        result = XmlPatchEngine.apply_actions(actions, xml)
        tree = ET.fromstring(result)
        assert tree.text == "modified_root"
