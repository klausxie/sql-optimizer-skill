#!/usr/bin/env python3
import argparse
import ast
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--run-id", required=True)
p.add_argument("--max-steps", type=int, default=200)
args = p.parse_args()

for _ in range(args.max_steps):
    status_out = subprocess.check_output(["python3", "scripts/sqlopt_cli.py", "status", "--run-id", args.run_id], text=True).strip()
    payload = ast.literal_eval(status_out)
    if payload.get("complete"):
        print(payload)
        raise SystemExit(0)
    subprocess.check_call(["python3", "scripts/sqlopt_cli.py", "resume", "--run-id", args.run_id])

raise SystemExit("max steps reached")
