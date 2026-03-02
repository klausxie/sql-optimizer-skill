#!/usr/bin/env python3
import argparse
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--config", required=True)
p.add_argument("--to-stage", default="patch_generate")
args = p.parse_args()
subprocess.check_call(["python3", "scripts/sqlopt_cli.py", "run", "--config", args.config, "--to-stage", args.to_stage])
