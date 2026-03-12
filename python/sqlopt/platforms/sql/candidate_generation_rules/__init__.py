from __future__ import annotations

from .low_value_comment_only import CommentOnlyRewriteRule
from .low_value_dynamic_filter import DynamicFilterSpeculativeRewriteRule
from .low_value_dynamic_filter_from_alias_cleanup import DynamicFilterFromAliasCleanupRewriteRule
from .low_value_dynamic_filter_select_cleanup import DynamicFilterSelectCleanupRewriteRule
from .low_value_dynamic_filter_reorder import DynamicFilterPredicateReorderRule
from .low_value_foreach_predicate import ForeachPredicateSpeculativeRewriteRule
from .low_value_identity import IdentityNoopRule
from .low_value_static_include_paged import StaticIncludePagedSpeculativeFilterRule
from .low_value_speculative import SpeculativeAdditiveRewriteRule
from .recovery_blocked_shape import BlockedShapeRecoveryRule
from .recovery_safe_baseline import SafeBaselineRecoveryRule

LOW_VALUE_RULES = (
    CommentOnlyRewriteRule(),
    IdentityNoopRule(),
    DynamicFilterPredicateReorderRule(),
    DynamicFilterFromAliasCleanupRewriteRule(),
    DynamicFilterSelectCleanupRewriteRule(),
    DynamicFilterSpeculativeRewriteRule(),
    ForeachPredicateSpeculativeRewriteRule(),
    StaticIncludePagedSpeculativeFilterRule(),
    SpeculativeAdditiveRewriteRule(),
)

RECOVERY_RULES = (
    SafeBaselineRecoveryRule(),
    BlockedShapeRecoveryRule(),
)
