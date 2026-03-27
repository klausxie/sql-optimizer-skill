# tests/test_classification.py
"""Tests for classification module - configuration-driven patch family classification."""
from sqlopt.patch_families.classification import (
    ClassificationConfig,
    ClassificationContext,
    classify_patch_family,
)


def test_classification_config_can_be_imported():
    """ClassificationConfig can be imported from classification module."""
    config = ClassificationConfig(
        family="TEST_FAMILY",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\btest\b"],
        rewritten_patterns=[],
    )
    assert config.family == "TEST_FAMILY"
    assert config.strategy_type == "EXACT_TEMPLATE_EDIT"


def test_classification_context_can_be_created():
    """ClassificationContext can be created with SQL parameters."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users",
        rewritten_sql="SELECT id FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    assert ctx.original_sql == "SELECT * FROM users"
    assert ctx.rewritten_sql == "SELECT id FROM users"


def test_classify_patch_family_is_callable():
    """classify_patch_family function is importable and callable."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id IN (1)",
        rewritten_sql="SELECT * FROM users WHERE id = 1",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    # Stub returns None - full implementation will return family name
    assert result is None or isinstance(result, str)


def test_config_based_classification_for_in_list():
    """STATIC_IN_LIST_SIMPLIFICATION can be classified via config."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id IN (1)",
        rewritten_sql="SELECT * FROM users WHERE id = 1",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_IN_LIST_SIMPLIFICATION"


def test_config_based_classification_for_limit():
    """STATIC_LIMIT_OPTIMIZATION can be classified via config."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users LIMIT 0",
        rewritten_sql="SELECT * FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_LIMIT_OPTIMIZATION"