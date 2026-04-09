from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.llm_cassette import (
    build_optimize_cassette_fingerprint_input,
    fingerprint_optimize_cassette_input,
    optimize_normalized_cassette_path,
    optimize_raw_cassette_path,
)


def _request() -> dict[str, object]:
    return {
        "sqlKey": "demo.user.listUsers",
        "sql": "SELECT id, name FROM users WHERE status = #{status}",
        "templateSql": "SELECT id, name FROM users WHERE status = #{status}",
        "dynamicFeatures": ["WHERE", "IF"],
        "stableDbEvidence": {
            "tables": ["users"],
            "indexes": [{"table": "users", "name": "idx_users_status"}],
        },
        "promptVersion": "v1",
        "provider": "opencode_run",
        "model": "test-model",
    }


def _prompt() -> dict[str, object]:
    request = _request()
    return {
        "task": "sql_optimize_candidate_generation",
        "sqlKey": request["sqlKey"],
        "requiredContext": {
            "sql": request["sql"],
            "templateSql": request["templateSql"],
            "dynamicFeatures": request["dynamicFeatures"],
            "tables": request["stableDbEvidence"]["tables"],
            "indexes": request["stableDbEvidence"]["indexes"],
        },
        "optionalContext": {
            "planSummary": {"risk": "low"},
        },
    }


def _fingerprint_request(prompt: dict[str, object]) -> dict[str, object]:
    required = prompt["requiredContext"]
    optional = prompt["optionalContext"]
    return {
        "sqlKey": prompt["sqlKey"],
        "sql": required["sql"],
        "templateSql": required["templateSql"],
        "dynamicFeatures": required["dynamicFeatures"],
        "stableDbEvidence": {
            "tables": required["tables"],
            "indexes": required["indexes"],
            "planSummary": optional["planSummary"],
        },
        "promptVersion": "v1",
        "provider": "opencode_run",
        "model": "test-model",
    }


def _llm_cfg(mode: str) -> dict[str, object]:
    return {
        "enabled": True,
        "mode": mode,
        "provider": "opencode_run",
        "opencode_model": "test-model",
        "timeout_ms": 15000,
    }


class _RetryContext:
    def __init__(self, attempt: int, max_retries: int, errors: list[dict[str, object]] | None = None) -> None:
        self.attempt = attempt
        self.max_retries = max_retries
        self.errors = errors or []


class LlmReplayGatewayTest(unittest.TestCase):
    def test_replay_hit_returns_normalized_cassette_without_calling_provider(self) -> None:
        from sqlopt.platforms.sql import llm_replay_gateway as gateway

        prompt = _prompt()
        fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(_fingerprint_request(prompt)))

        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_replay_") as td:
            root = Path(td)
            raw_payload = {
                "fingerprint": fingerprint,
                "provider": "opencode_run",
                "model": "test-model",
                "promptVersion": "v1",
                "sqlKey": prompt["sqlKey"],
                "request": _fingerprint_request(prompt),
                "response": {"candidates": [{"id": "c1", "source": "llm", "rewrittenSql": "SELECT 1"}]},
                "createdAt": "2026-04-09T00:00:00Z",
            }
            normalized_payload = {
                "fingerprint": fingerprint,
                "sqlKey": prompt["sqlKey"],
                "rawCandidateCount": 1,
                "validCandidates": [{"id": "c1", "source": "llm", "rewrittenSql": "SELECT 1"}],
                "trace": {"executor": "opencode_run", "provider": "opencode_run", "task_id": "demo.user.listUsers:opt"},
            }
            root.joinpath("optimize/raw").mkdir(parents=True, exist_ok=True)
            root.joinpath("optimize/normalized").mkdir(parents=True, exist_ok=True)
            root.joinpath(optimize_raw_cassette_path(root, fingerprint).relative_to(root)).write_text(
                json.dumps(raw_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            root.joinpath(optimize_normalized_cassette_path(root, fingerprint).relative_to(root)).write_text(
                json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

            def _boom(*_: object, **__: object) -> tuple[list[dict[str, object]], dict[str, object]]:
                raise AssertionError("provider should not be called for replay hits")

            original = gateway.generate_llm_candidates
            try:
                gateway.generate_llm_candidates = _boom  # type: ignore[assignment]
                candidates, trace = gateway.generate_optimize_candidates_with_replay(
                    prompt["sqlKey"],
                    prompt["requiredContext"]["sql"],
                    _llm_cfg("replay"),
                    prompt=prompt,
                    cassette_root=root,
                )
            finally:
                gateway.generate_llm_candidates = original  # type: ignore[assignment]

        self.assertEqual(candidates, normalized_payload["validCandidates"])
        self.assertEqual(trace["executor"], "replay")
        self.assertEqual(trace["provider"], "cassette")
        self.assertEqual(trace["replaySourceExecutor"], "opencode_run")
        self.assertEqual(trace["replaySourceProvider"], "opencode_run")

    def test_replay_miss_raises_strict_error_with_sql_key_fingerprint_and_path(self) -> None:
        from sqlopt.platforms.sql.llm_replay_gateway import generate_optimize_candidates_with_replay

        prompt = _prompt()
        fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(_fingerprint_request(prompt)))

        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_replay_miss_") as td:
            root = Path(td)
            with self.assertRaises(RuntimeError) as ctx:
                generate_optimize_candidates_with_replay(
                    prompt["sqlKey"],
                    prompt["requiredContext"]["sql"],
                    _llm_cfg("replay"),
                    prompt=prompt,
                    cassette_root=root,
                )

        message = str(ctx.exception)
        self.assertIn(str(prompt["sqlKey"]), message)
        self.assertIn(fingerprint, message)
        self.assertIn(str(optimize_normalized_cassette_path(root, fingerprint)), message)

    def test_record_mode_writes_raw_and_normalized_cassettes(self) -> None:
        from sqlopt.platforms.sql import llm_replay_gateway as gateway

        prompt = _prompt()
        fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(_fingerprint_request(prompt)))
        expected_candidates = [
            {"id": "c1", "source": "llm", "rewrittenSql": "SELECT id, name FROM users WHERE status = #{status}"}
        ]
        expected_trace = {
            "executor": "opencode_run",
            "provider": "opencode_run",
            "mode": "candidate_generation",
            "response": {"mode": "opencode_run", "rawText": "{\"candidates\":[]}"},
        }

        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_record_") as td:
            root = Path(td)

            def _fake_provider(*_: object, **__: object) -> tuple[list[dict[str, object]], dict[str, object]]:
                return expected_candidates, expected_trace

            original = gateway.generate_llm_candidates
            try:
                gateway.generate_llm_candidates = _fake_provider  # type: ignore[assignment]
                candidates, trace = gateway.generate_optimize_candidates_with_replay(
                    prompt["sqlKey"],
                    prompt["requiredContext"]["sql"],
                    _llm_cfg("record"),
                    prompt=prompt,
                    cassette_root=root,
                )
            finally:
                gateway.generate_llm_candidates = original  # type: ignore[assignment]

            raw_path = optimize_raw_cassette_path(root, fingerprint)
            normalized_path = optimize_normalized_cassette_path(root, fingerprint)

            self.assertTrue(raw_path.exists())
            self.assertTrue(normalized_path.exists())
            self.assertEqual(candidates, expected_candidates)
            self.assertEqual(trace, expected_trace)

            raw = __import__("json").loads(raw_path.read_text(encoding="utf-8"))
            normalized = __import__("json").loads(normalized_path.read_text(encoding="utf-8"))

        self.assertEqual(raw["fingerprint"], fingerprint)
        self.assertEqual(raw["sqlKey"], prompt["sqlKey"])
        self.assertEqual(raw["request"]["sqlKey"], prompt["sqlKey"])
        self.assertEqual(raw["response"], expected_trace["response"])
        self.assertEqual(normalized["rawCandidateCount"], 1)
        self.assertEqual(normalized["validCandidates"], expected_candidates)
        self.assertEqual(normalized["trace"], expected_trace)

    def test_live_mode_passes_through_without_writing_cassettes(self) -> None:
        from sqlopt.platforms.sql import llm_replay_gateway as gateway

        prompt = _prompt()

        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_live_") as td:
            root = Path(td)
            observed_calls: list[tuple[str, str, dict[str, object]]] = []

            def _fake_provider(
                sql_key: str,
                sql: str,
                llm_cfg: dict[str, object],
                *,
                prompt: dict[str, object] | None = None,
                retry_context: object | None = None,
            ) -> tuple[list[dict[str, object]], dict[str, object]]:
                observed_calls.append((sql_key, sql, llm_cfg))
                return ([{"id": "c1", "source": "llm", "rewrittenSql": "SELECT 1"}], {"executor": "opencode_run"})

            original = gateway.generate_llm_candidates
            try:
                gateway.generate_llm_candidates = _fake_provider  # type: ignore[assignment]
                candidates, trace = gateway.generate_optimize_candidates_with_replay(
                    prompt["sqlKey"],
                    prompt["requiredContext"]["sql"],
                    _llm_cfg("live"),
                    prompt=prompt,
                    cassette_root=root,
                )
            finally:
                gateway.generate_llm_candidates = original  # type: ignore[assignment]

            self.assertEqual(len(observed_calls), 1)
            self.assertEqual(candidates, [{"id": "c1", "source": "llm", "rewrittenSql": "SELECT 1"}])
            self.assertEqual(trace, {"executor": "opencode_run"})
            fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(_fingerprint_request(prompt)))
            self.assertFalse(optimize_raw_cassette_path(root, fingerprint).exists())
            self.assertFalse(
                optimize_normalized_cassette_path(
                    root,
                    fingerprint,
                ).exists()
            )

    def test_invalid_mode_fails_fast(self) -> None:
        from sqlopt.platforms.sql.llm_replay_gateway import generate_optimize_candidates_with_replay

        prompt = _prompt()
        with self.assertRaises(RuntimeError):
            generate_optimize_candidates_with_replay(
                prompt["sqlKey"],
                prompt["requiredContext"]["sql"],
                _llm_cfg("replaay"),
                prompt=prompt,
            )

    def test_retry_context_changes_recorded_fingerprint(self) -> None:
        from sqlopt.platforms.sql import llm_replay_gateway as gateway

        prompt = _prompt()
        retry_context = _RetryContext(
            attempt=2,
            max_retries=3,
            errors=[{"message": "all candidates rejected", "type": "validation"}],
        )

        expected_trace = {
            "executor": "opencode_run",
            "provider": "opencode_run",
            "response": {"mode": "opencode_run"},
        }

        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_retry_record_") as td:
            root = Path(td)

            def _fake_provider(*_: object, **__: object) -> tuple[list[dict[str, object]], dict[str, object]]:
                return ([{"id": "c1", "source": "llm", "rewrittenSql": "SELECT 1"}], expected_trace)

            original = gateway.generate_llm_candidates
            try:
                gateway.generate_llm_candidates = _fake_provider  # type: ignore[assignment]
                gateway.generate_optimize_candidates_with_replay(
                    prompt["sqlKey"],
                    prompt["requiredContext"]["sql"],
                    _llm_cfg("record"),
                    prompt=prompt,
                    retry_context=retry_context,
                    cassette_root=root,
                )
            finally:
                gateway.generate_llm_candidates = original  # type: ignore[assignment]

            request = _fingerprint_request(prompt)
            request["retryContext"] = {
                "attempt": 2,
                "maxRetries": 3,
                "errors": [{"message": "all candidates rejected", "type": "validation"}],
            }
            retry_fingerprint = fingerprint_optimize_cassette_input(
                build_optimize_cassette_fingerprint_input(request)
            )
            normal_fingerprint = fingerprint_optimize_cassette_input(
                build_optimize_cassette_fingerprint_input(_fingerprint_request(prompt))
            )

            self.assertNotEqual(retry_fingerprint, normal_fingerprint)
            self.assertTrue(optimize_raw_cassette_path(root, retry_fingerprint).exists())
