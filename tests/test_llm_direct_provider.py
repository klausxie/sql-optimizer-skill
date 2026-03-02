from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from sqlopt.llm.provider import generate_llm_candidates


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LlmDirectProviderTest(unittest.TestCase):
    def _cfg(self) -> dict:
        return {
            "enabled": True,
            "provider": "direct_openai_compatible",
            "api_base": "https://example.com/v1",
            "api_key": "k",
            "api_model": "m",
            "timeout_ms": 1000,
        }

    def test_direct_provider_success(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"candidates": [{"id": "c1", "rewrittenSql": "SELECT id FROM users", "rewriteStrategy": "s1"}]},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        with patch("sqlopt.llm.provider.urllib.request.urlopen", return_value=_Resp(payload)):
            candidates, trace = generate_llm_candidates("k1", "SELECT * FROM users", self._cfg(), prompt={"sqlKey": "k1"})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["rewrittenSql"], "SELECT id FROM users")
        self.assertEqual(trace.get("degrade_reason"), None)

    def test_direct_provider_mixed_text_json(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": "说明文字\n```json\n{\"candidates\":[{\"rewrittenSql\":\"SELECT id FROM users\"}]}\n```"
                    }
                }
            ]
        }
        with patch("sqlopt.llm.provider.urllib.request.urlopen", return_value=_Resp(payload)):
            candidates, _trace = generate_llm_candidates("k1", "SELECT * FROM users", self._cfg(), prompt={"sqlKey": "k1"})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source"], "llm")

    def test_direct_provider_missing_candidates_fails(self) -> None:
        payload = {"choices": [{"message": {"content": "{\"ok\":true}"}}]}
        with patch("sqlopt.llm.provider.urllib.request.urlopen", return_value=_Resp(payload)):
            with self.assertRaises(RuntimeError):
                generate_llm_candidates("k1", "SELECT * FROM users", self._cfg(), prompt={"sqlKey": "k1"})


if __name__ == "__main__":
    unittest.main()
