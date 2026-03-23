"""ResultOutput contract for SQL Optimizer Result stage.

This module defines the data structures for the final output of the
SQL optimization pipeline, including reports and patches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class Report:
    """Optimization report with summary and recommendations.

    Attributes:
        summary: Brief overview of the optimization results
        details: Detailed explanation of findings
        risks: List of identified risks
        recommendations: List of optimization recommendations
    """

    summary: str
    details: str
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize Report to JSON string."""
        return json.dumps(
            {
                "summary": self.summary,
                "details": self.details,
                "risks": self.risks,
                "recommendations": self.recommendations,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> Report:
        """Deserialize Report from JSON string.

        Args:
            json_str: JSON string representation of Report

        Returns:
            Report instance
        """
        data = json.loads(json_str)
        return cls(
            summary=data["summary"],
            details=data["details"],
            risks=data.get("risks", []),
            recommendations=data.get("recommendations", []),
        )


@dataclass
class Patch:
    """SQL patch for a single SQL unit.

    Attributes:
        sql_unit_id: Identifier of the SQL unit being patched
        original_xml: Original XML content before patch
        patched_xml: Modified XML content after patch
        diff: Unified diff showing changes
    """

    sql_unit_id: str
    original_xml: str
    patched_xml: str
    diff: str

    def to_json(self) -> str:
        """Serialize Patch to JSON string."""
        return json.dumps(
            {
                "sql_unit_id": self.sql_unit_id,
                "original_xml": self.original_xml,
                "patched_xml": self.patched_xml,
                "diff": self.diff,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> Patch:
        """Deserialize Patch from JSON string.

        Args:
            json_str: JSON string representation of Patch

        Returns:
            Patch instance
        """
        data = json.loads(json_str)
        return cls(
            sql_unit_id=data["sql_unit_id"],
            original_xml=data["original_xml"],
            patched_xml=data["patched_xml"],
            diff=data["diff"],
        )


@dataclass
class ResultOutput:
    """Final output of the SQL optimization pipeline.

    Attributes:
        can_patch: Whether the XML can be safely patched
        report: Optimization report with findings and recommendations
        patches: List of patches to apply (if can_patch is True)
    """

    can_patch: bool
    report: Report
    patches: List[Patch] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize ResultOutput to JSON string."""
        return json.dumps(
            {
                "can_patch": self.can_patch,
                "report": json.loads(self.report.to_json()),
                "patches": [json.loads(p.to_json()) for p in self.patches],
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> ResultOutput:
        """Deserialize ResultOutput from JSON string.

        Args:
            json_str: JSON string representation of ResultOutput

        Returns:
            ResultOutput instance
        """
        data = json.loads(json_str)
        report = Report.from_json(json.dumps(data["report"]))
        patches = [Patch.from_json(json.dumps(p)) for p in data.get("patches", [])]
        return cls(
            can_patch=data["can_patch"],
            report=report,
            patches=patches,
        )
