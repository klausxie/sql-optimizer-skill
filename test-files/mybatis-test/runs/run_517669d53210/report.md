# SQL Optimize Report: run_517669d53210

## Executive Decision
- Release Readiness: `NO_GO`
- Verdict: `BLOCKED`
- Scope: SQL units `0`, proposals `0`
- Delivery Snapshot: patches `0`, applicable `0`, blocked sql `0`
- Perf Evidence: improved `0`, not improved `0`
- Materialization: `{}`
- Materialization Reasons: `{}`
- Materialization Actions: `{}`

## Top Risks
- `PREFLIGHT_DB_UNREACHABLE` (`fatal`): count `1`, impacted sql `0`

## Delivery Status
- preflight: `FAILED`
- scan: `PENDING` (attempts `0`)
- optimize: `PENDING` (attempts `0`)
- validate: `PENDING` (attempts `0`)
- patch_generate: `PENDING` (attempts `0`)
- report: `PENDING`

## Change Portfolio
| SQL Key | Status | Source | Perf | Materialization | Patch Applicable | Patch Decision |
|---|---|---|---|---|---|---|

## Proposal Insights
| SQL Key | Verdict | Issues | LLM Candidates |
|---|---|---|---|
| `n/a` | `n/a` | `n/a` | `0` |

## Technical Evidence
- No PASS items with technical evidence.

## Action Plan (Next 24h)
- Platform: resume run: `PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id run_517669d53210`

## Appendix
- report.json: `run_517669d53210/report.json`
- proposals: `run_517669d53210/proposals/optimization.proposals.jsonl`
- acceptance: `run_517669d53210/acceptance/acceptance.results.jsonl`
- patches: `run_517669d53210/patches/patch.results.jsonl`
- failures: `run_517669d53210/ops/failures.jsonl`
