# Result Stage

## Purpose

`result` turns proposals and baselines into a ranked report and optional per-unit patch set.

## Inputs

- init SQL units (with file content for patching)
- recognition baselines
- optimize proposals

## Main work

- rank proposals by validated impact
- separate:
  - verified improvements
  - candidates that still need validation
  - result mismatches
  - validation failures
- generate per-unit patches for proposals that are safe enough to patch
- generate a summary report for humans

## Patch generation

### Patch-ready rule

A proposal is patch-ready only when:

- validation status is `validated`
- result equivalence is not false
- gain ratio is not negative

### Patch creation

`_create_patch()` generates patches using:

1. `XmlPatchEngine.apply_text_replacement()` — when `proposal.actions` exist, applies structured text replacements (REPLACE, ADD, REMOVE, WRAP)
2. Simple `str.replace()` — fallback when no actions, replaces original SQL text with optimized SQL

The unified diff uses `a/{filename}` / `b/{filename}` headers (filename only, not full path) so that `patch -d {mapper_dir}` can locate the target file.

### Per-unit output files

For each patch-ready proposal:

- `{unit_id}.patch` — unified diff in standard Git Patch format
- `{unit_id}.meta.json` — metadata (operation, confidence, rationale, original/rewritten snippets)
- `_index.json` — index listing all unit IDs with patches

## CLI commands for patches

| Command | Description |
| --- | --- |
| `sqlopt patches --run-id <id>` | List all available patches |
| `sqlopt diff <unit_id> --run-id <id>` | Display a patch diff |
| `sqlopt apply <unit_id> --run-id <id> [--project-root .] [--dry-run]` | Apply a patch to the mapper XML file |

The `apply` command:
- Validates the patch with `patch --dry-run` before applying
- Uses `patch -d {mapper_dir} -p1` to target the correct directory
- Creates a `.orig` backup file

## Outputs

- `report.json`
- `SUMMARY.md`
- `units/_index.json`
- `units/{unit_id}.patch`
- `units/{unit_id}.meta.json`

## Primary implementation

- `python/sqlopt/stages/result/stage.py`
- `python/sqlopt/common/xml_patch_engine.py`

## Related docs

- [Result contracts](../CONTRACTS/result.md)
- [Data Flow](../DATAFLOW.md)
