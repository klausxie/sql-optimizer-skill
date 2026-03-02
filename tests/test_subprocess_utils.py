from __future__ import annotations

import unittest

from sqlopt.subprocess_utils import decode_bytes


class SubprocessUtilsTest(unittest.TestCase):
    def test_decode_bytes_utf8(self) -> None:
        self.assertEqual(decode_bytes("hello".encode("utf-8")), "hello")

    def test_decode_bytes_fallback_replace(self) -> None:
        raw = b"\x80\x81\x82"
        text = decode_bytes(raw)
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 0)


if __name__ == "__main__":
    unittest.main()
