from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_build_bundle_module():
    path = ROOT / "install" / "build_bundle.py"
    spec = importlib.util.spec_from_file_location("install_build_bundle_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildBundleTest(unittest.TestCase):
    def test_parse_version_from_pyproject_fallback_regex(self) -> None:
        module = _load_build_bundle_module()
        text = """
[project]
name = "x"
version = "1.2.3"
"""
        self.assertEqual(module._parse_version_from_pyproject(text), "1.2.3")


if __name__ == "__main__":
    unittest.main()
