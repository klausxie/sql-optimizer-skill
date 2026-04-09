from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.llm_cassette import (
    CassetteMiss,
    CassetteFormatError,
    build_optimize_cassette_fingerprint_input,
    load_optimize_cassette,
    optimize_normalized_cassette_path,
    optimize_raw_cassette_path,
    save_optimize_cassette,
    fingerprint_optimize_cassette_input,
)


class LlmCassetteTest(unittest.TestCase):
    def test_optimize_cassette_fingerprint_stable_for_logical_equivalent_requests(self) -> None:
        request_a = {
            "sqlKey": "demo.user.findUsers",
            "sql": "\nSELECT id, name FROM users WHERE status = 'ACTIVE'\n",
            "templateSql": "\nSELECT id, name FROM users WHERE status = 'ACTIVE'\n",
            "dynamicFeatures": ["WHERE", "IF", "WHERE"],
            "stableDbEvidence": {
                "planSummary": {"cost": 12, "rows": 3},
                "run_id": "run-local-1",
                "createdAt": "2026-04-09T01:23:45Z",
                "tempPath": "/tmp/volatile",
                "sourcePath": "/Users/example/project/tmp/debug.json",
            },
            "promptVersion": "v1",
            "provider": "opencode_run",
            "model": "gpt-5-mini",
            "run_id": "run-local-1",
            "createdAt": "2026-04-09T01:23:45Z",
            "tempPath": "/tmp/volatile",
        }
        request_b = {
            "provider": "opencode_run",
            "model": "gpt-5-mini",
            "promptVersion": "v1",
            "sqlKey": "demo.user.findUsers",
            "dynamicFeatures": ["IF", "WHERE"],
            "templateSql": "SELECT id, name FROM users WHERE status = 'ACTIVE'",
            "sql": "SELECT id, name FROM users WHERE status = 'ACTIVE'",
            "stableDbEvidence": {
                "planSummary": {"rows": 3, "cost": 12},
                "sourcePath": "/tmp/local/debug.json",
            },
        }

        fingerprint_input_a = build_optimize_cassette_fingerprint_input(request_a)
        fingerprint_input_b = build_optimize_cassette_fingerprint_input(request_b)

        self.assertEqual(fingerprint_input_a, fingerprint_input_b)
        self.assertNotIn("run_id", fingerprint_input_a)
        self.assertNotIn("createdAt", fingerprint_input_a)
        self.assertNotIn("tempPath", fingerprint_input_a)
        self.assertEqual(fingerprint_input_a["stableDbEvidence"]["sourcePath"], "<path>")
        self.assertEqual(
            fingerprint_optimize_cassette_input(fingerprint_input_a),
            fingerprint_optimize_cassette_input(fingerprint_input_b),
        )

    def test_optimize_cassette_fingerprint_preserves_literal_whitespace(self) -> None:
        request_a = {
            "sqlKey": "demo.user.literal",
            "sql": "SELECT 'a  b' AS marker",
            "templateSql": "SELECT 'a  b' AS marker",
            "dynamicFeatures": [],
            "stableDbEvidence": {},
            "promptVersion": "v1",
            "provider": "opencode_run",
            "model": "gpt-5-mini",
        }
        request_b = dict(request_a, sql="SELECT 'a b' AS marker", templateSql="SELECT 'a b' AS marker")

        self.assertNotEqual(
            fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(request_a)),
            fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(request_b)),
        )

    def test_optimize_cassette_fingerprint_changes_when_prompt_version_changes(self) -> None:
        base_request = {
            "sqlKey": "demo.user.findUsers",
            "sql": "SELECT id FROM users",
            "templateSql": "SELECT id FROM users",
            "dynamicFeatures": [],
            "stableDbEvidence": {"planSummary": {"cost": 1}},
            "promptVersion": "v1",
            "provider": "opencode_run",
            "model": "gpt-5-mini",
        }
        changed_request = dict(base_request, promptVersion="v2")

        base_fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(base_request))
        changed_fingerprint = fingerprint_optimize_cassette_input(
            build_optimize_cassette_fingerprint_input(changed_request)
        )

        self.assertNotEqual(base_fingerprint, changed_fingerprint)

    def test_optimize_cassette_fingerprint_changes_when_provider_or_model_changes(self) -> None:
        base_request = {
            "sqlKey": "demo.user.findUsers",
            "sql": "SELECT id FROM users",
            "templateSql": "SELECT id FROM users",
            "dynamicFeatures": [],
            "stableDbEvidence": {"planSummary": {"cost": 1}},
            "promptVersion": "v1",
            "provider": "opencode_run",
            "model": "gpt-5-mini",
        }
        changed_provider_request = dict(base_request, provider="direct_openai_compatible")
        changed_model_request = dict(base_request, model="gpt-5.1")

        base_fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(base_request))
        provider_fingerprint = fingerprint_optimize_cassette_input(
            build_optimize_cassette_fingerprint_input(changed_provider_request)
        )
        model_fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(changed_model_request))

        self.assertNotEqual(base_fingerprint, provider_fingerprint)
        self.assertNotEqual(base_fingerprint, model_fingerprint)

    def test_optimize_cassette_fingerprint_requires_feature_list_not_string(self) -> None:
        with self.assertRaises(CassetteFormatError):
            build_optimize_cassette_fingerprint_input(
                {
                    "sqlKey": "demo.user.badFeatures",
                    "sql": "SELECT id FROM users",
                    "templateSql": "SELECT id FROM users",
                    "dynamicFeatures": "WHERE",
                    "stableDbEvidence": {},
                    "promptVersion": "v1",
                    "provider": "opencode_run",
                    "model": "gpt-5-mini",
                }
            )

    def test_optimize_cassette_path_helpers_use_raw_and_normalized_layout(self) -> None:
        root = Path("/tmp/cassettes")
        fingerprint = "abc123"

        self.assertEqual(optimize_raw_cassette_path(root, fingerprint), root / "optimize" / "raw" / "abc123.json")
        self.assertEqual(
            optimize_normalized_cassette_path(root, fingerprint),
            root / "optimize" / "normalized" / "abc123.json",
        )

    def test_optimize_cassette_roundtrip_writes_deterministic_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_cassette_") as td:
            root = Path(td)
            fingerprint = "abc123"
            raw_payload = {
                "model": "gpt-5-mini",
                "provider": "opencode_run",
                "promptVersion": "v1",
                "sqlKey": "demo.user.findUsers",
                "request": {"b": 2, "a": 1},
                "response": {"candidates": [{"rewrittenSql": "SELECT id FROM users"}]},
                "createdAt": "2026-04-09T01:23:45Z",
                "fingerprint": fingerprint,
            }
            normalized_payload = {
                "fingerprint": fingerprint,
                "sqlKey": "demo.user.findUsers",
                "rawCandidateCount": 1,
                "validCandidates": [{"id": "c1", "rewrittenSql": "SELECT id FROM users"}],
                "trace": {"executor": "opencode_run"},
            }

            save_optimize_cassette(root, "raw", fingerprint, raw_payload)
            save_optimize_cassette(root, "normalized", fingerprint, normalized_payload)

            raw_path = optimize_raw_cassette_path(root, fingerprint)
            normalized_path = optimize_normalized_cassette_path(root, fingerprint)

            self.assertEqual(raw_path.read_text(encoding="utf-8"), (
                '{\n'
                '  "createdAt": "2026-04-09T01:23:45Z",\n'
                '  "fingerprint": "abc123",\n'
                '  "model": "gpt-5-mini",\n'
                '  "promptVersion": "v1",\n'
                '  "provider": "opencode_run",\n'
                '  "request": {\n'
                '    "a": 1,\n'
                '    "b": 2\n'
                '  },\n'
                '  "response": {\n'
                '    "candidates": [\n'
                '      {\n'
                '        "rewrittenSql": "SELECT id FROM users"\n'
                '      }\n'
                '    ]\n'
                '  },\n'
                '  "sqlKey": "demo.user.findUsers"\n'
                '}\n'
            ))
            self.assertEqual(normalized_path.read_text(encoding="utf-8"), (
                '{\n'
                '  "fingerprint": "abc123",\n'
                '  "rawCandidateCount": 1,\n'
                '  "sqlKey": "demo.user.findUsers",\n'
                '  "trace": {\n'
                '    "executor": "opencode_run"\n'
                '  },\n'
                '  "validCandidates": [\n'
                '    {\n'
                '      "id": "c1",\n'
                '      "rewrittenSql": "SELECT id FROM users"\n'
                '    }\n'
                '  ]\n'
                '}\n'
            ))

            self.assertEqual(load_optimize_cassette(root, "raw", fingerprint), raw_payload)
            self.assertEqual(load_optimize_cassette(root, "normalized", fingerprint), normalized_payload)

    def test_optimize_cassette_enforces_required_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_cassette_required_") as td:
            root = Path(td)
            with self.assertRaises(CassetteFormatError):
                save_optimize_cassette(root, "raw", "abc123", {"sqlKey": "demo.user.findUsers"})
            raw_path = optimize_raw_cassette_path(root, "abc123")
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text('{"sqlKey":"demo.user.findUsers"}\n', encoding="utf-8")
            with self.assertRaises(CassetteFormatError):
                load_optimize_cassette(root, "raw", "abc123")

    def test_missing_optimize_cassette_returns_typed_miss_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_cassette_missing_") as td:
            root = Path(td)
            result = load_optimize_cassette(root, "raw", "missing-fingerprint")

            self.assertIsInstance(result, CassetteMiss)
            self.assertEqual(result.cassette_kind, "raw")
            self.assertEqual(result.fingerprint, "missing-fingerprint")
            self.assertEqual(result.path, optimize_raw_cassette_path(root, "missing-fingerprint"))

    def test_optimize_cassette_rejects_unsafe_fingerprint_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_llm_cassette_path_") as td:
            root = Path(td)
            with self.assertRaises(CassetteFormatError):
                optimize_raw_cassette_path(root, "../../outside")


if __name__ == "__main__":
    unittest.main()
