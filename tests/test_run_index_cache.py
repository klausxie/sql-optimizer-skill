from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.application import run_index
from sqlopt.io_utils import write_json


class RunIndexCacheTest(unittest.TestCase):
    def test_load_run_index_reuses_cache_when_file_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_index_cache_") as td:
            index_path = Path(td) / "index.json"
            write_json(index_path, {"run_a": {"run_dir": "/tmp/a"}})

            with patch("sqlopt.application.run_index.read_json", wraps=run_index.read_json) as read_mock:
                first = run_index.load_run_index(index_path)
                second = run_index.load_run_index(index_path)

            self.assertEqual(first, second)
            self.assertEqual(read_mock.call_count, 1)

    def test_save_run_index_refreshes_cache_immediately(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_index_cache_save_") as td:
            index_path = Path(td) / "index.json"
            run_index.save_run_index(index_path, {"run_b": {"run_dir": "/tmp/b"}})

            with patch("sqlopt.application.run_index.read_json", side_effect=AssertionError("cache should be used")):
                data = run_index.load_run_index(index_path)

            self.assertIn("run_b", data)


if __name__ == "__main__":
    unittest.main()
