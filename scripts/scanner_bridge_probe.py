#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.adapters.scanner_java import run_scan

p = argparse.ArgumentParser()
p.add_argument("--config", required=True)
args = p.parse_args()
cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
run_dir = ROOT / "runs" / "probe"
run_dir.mkdir(parents=True, exist_ok=True)
units, warnings = run_scan(cfg, run_dir, run_dir / "manifest.jsonl")
print({"units": len(units), "warnings": len(warnings)})
