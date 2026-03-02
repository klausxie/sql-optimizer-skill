from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, write_json
from ..llm.provider import generate_llm_candidates
from ..manifest import log_event
from ..platforms.sql.optimizer_sql import build_optimize_prompt, generate_proposal


def execute_one(sql_unit: dict[str, Any], run_dir: Path, validator: ContractValidator, config: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = dict(config.get("llm", {}) or {})
    project_root = (config.get("project", {}) or {}).get("root_path")
    if isinstance(project_root, str) and project_root.strip():
        llm_cfg["opencode_workdir"] = project_root
    proposal = generate_proposal(sql_unit, config=config)
    candidates: list[dict[str, Any]] = []
    trace: dict[str, Any] = {}
    if "${" in str(sql_unit.get("sql", "")):
        trace = {
            "stage": "optimize",
            "mode": "candidate_generation",
            "sql_key": sql_unit["sqlKey"],
            "task_id": f"{sql_unit['sqlKey']}:opt",
            "executor": "skip",
            "degrade_reason": "RISKY_DOLLAR_SUBSTITUTION",
            "response": {"fallback_used": True, "skip": True},
        }
    else:
        prompt = build_optimize_prompt(sql_unit, proposal)
        candidates, trace = generate_llm_candidates(sql_unit["sqlKey"], sql_unit["sql"], llm_cfg, prompt=prompt)
        if candidates:
            proposal["llmCandidates"] = candidates
            proposal["llmTraceRefs"] = [f"traces/{sql_unit['sqlKey']}.optimize.llm.json"]
    validator.validate("optimization_proposal", proposal)
    append_jsonl(run_dir / "proposals" / "optimization.proposals.jsonl", proposal)
    if proposal.get("llmTraceRefs"):
        trace_path = run_dir / proposal["llmTraceRefs"][0]
        write_json(
            trace_path,
            {
                **trace,
                "response": {**(trace.get("response") or {}), "candidates": proposal.get("llmCandidates", [])},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    log_event(run_dir / "manifest.jsonl", "optimize", "done", {"statement_key": sql_unit["sqlKey"]})
    return proposal
