from __future__ import annotations

from typing import Protocol

from ..canonicalization_models import CanonicalContext, CanonicalMatch


class CanonicalRule(Protocol):
    rule_id: str

    def evaluate(self, context: CanonicalContext) -> CanonicalMatch | None:
        ...
