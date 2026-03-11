from __future__ import annotations

from typing import Protocol

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts


class PatchCapabilityRule(Protocol):
    capability: str

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        ...
