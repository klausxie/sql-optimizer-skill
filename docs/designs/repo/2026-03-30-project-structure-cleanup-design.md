# Project Structure Cleanup Design

## Status

- Date: 2026-03-30
- Scope: concise repo-structure cleanup proposal

## Goal

Reduce repository sprawl without touching stable runtime boundaries.

This cleanup only targets the areas that are currently too flat or mixed:

1. `docs`
2. `tests`
3. `scripts`

## Non-Goals

This cleanup does not:

1. refactor `python/sqlopt` package boundaries
2. change product behavior
3. rewrite existing specs
4. introduce broad naming churn outside the moved areas

## Required Changes

### 1. Split Governance Docs From Feature Specs

Current problem:

one flat specs directory mixed feature designs, harness governance, templates, and review samples.

Required target:

```text
docs/
  project/
  governance/
    harness/
      guidelines.md
      templates/
      reviews/
  designs/
    patch/
  plans/
```

Required moves:

1. harness guideline
2. harness templates
3. harness review samples
4. patch design specs into `docs/designs/patch/`

### 2. Split Tests By Proof Layer

Current problem:

`tests/` is almost entirely flat, so unit, fixture, workflow, and CI-facing tests are mixed together.

Required target:

```text
tests/
  unit/
  contract/
  harness/
    fixture/
    workflow/
  ci/
  support/
  fixtures/
```

Required moves:

1. pure logic and engine tests into `tests/unit/`
2. contract and artifact-shape tests into `tests/contract/`
3. fixture harness tests into `tests/harness/fixture/`
4. workflow and golden tests into `tests/harness/workflow/`
5. script-facing acceptance tests into `tests/ci/`
6. helper modules into `tests/support/`

### 3. Split Scripts By Use

Current problem:

`scripts/` mixes CLI entrypoints, CI jobs, fixture tooling, and local developer helpers.

Required target:

```text
scripts/
  cli/
  ci/
  fixtures/
  dev/
```

Required moves:

1. CLI entrypoint into `scripts/cli/`
2. fixture generation and calibration into `scripts/fixtures/`
3. local probes and quick helpers into `scripts/dev/`
4. keep CI jobs under `scripts/ci/`

## Naming Rules

1. governance docs use stable names, not date-only names
2. feature designs stay date-prefixed
3. test filenames use one domain prefix only
4. avoid parallel prefixes like `patch_*` and `patching_*` for the same area

## Migration Order

1. move governance docs first
2. move test helpers and harness tests second
3. move remaining tests by layer
4. move scripts last

## Acceptance

This cleanup is complete when:

1. harness governance docs no longer live beside feature specs
2. `tests/` top level is no longer the default home for every new test
3. script purpose is visible from path alone
4. no runtime code behavior changes are required to finish the cleanup
