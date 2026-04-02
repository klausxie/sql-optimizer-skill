from __future__ import annotations

from ....patch_contracts import FROZEN_AUTO_PATCH_FAMILIES
from .helpers import (
    fixture_registered_families,
    patch_apply_ready,
    patch_blocker_family,
    patch_meets_registered_fixture_obligations,
)


def assert_registered_fixture_patch_obligations(scenarios: list[dict], patches: list[dict]) -> None:
    patch_by_key = {str(row["sqlKey"]): row for row in patches}
    registered_families = fixture_registered_families(scenarios)
    if not registered_families:
        raise AssertionError("expected at least one registered fixture patch family")

    for scenario in scenarios:
        sql_key = str(scenario["sqlKey"])
        patch = patch_by_key[sql_key]
        target_registered_family = str(scenario.get("targetRegisteredFamily") or "").strip()
        target_dynamic_family = str(scenario.get("targetDynamicBaselineFamily") or "").strip()
        tracked_family = target_registered_family or target_dynamic_family
        if not tracked_family:
            continue
        if tracked_family not in registered_families:
            raise AssertionError(f"{sql_key}: unregistered tracked family {tracked_family!r}")
        if not patch_meets_registered_fixture_obligations(patch, scenario):
            raise AssertionError(f"{sql_key}: patch does not meet registered fixture obligations")
        if target_registered_family and patch_apply_ready(patch) and patch.get("patchFamily") != target_registered_family:
            raise AssertionError(
                f"{sql_key}: expected patch family {target_registered_family!r}, got {patch.get('patchFamily')!r}"
            )
        if str(scenario.get("targetDynamicDeliveryClass") or "").upper() == "READY_DYNAMIC_PATCH":
            if patch.get("patchFamily") != target_dynamic_family:
                raise AssertionError(
                    f"{sql_key}: expected dynamic patch family {target_dynamic_family!r}, got {patch.get('patchFamily')!r}"
                )


def assert_auto_patches_frozen_and_verified(patches: list[dict]) -> None:
    auto_patches = [row for row in patches if patch_apply_ready(row)]
    if not auto_patches:
        raise AssertionError("expected at least one auto-applicable patch")
    for patch in auto_patches:
        sql_key = str(patch["sqlKey"])
        family = str(patch.get("patchFamily") or "").strip()
        if family not in FROZEN_AUTO_PATCH_FAMILIES:
            raise AssertionError(f"{sql_key}: auto patch family {family!r} is not frozen")
        if ((patch.get("replayEvidence") or {}).get("matchesTarget")) is not True:
            raise AssertionError(f"{sql_key}: replay evidence did not confirm target match")
        if ((patch.get("syntaxEvidence") or {}).get("ok")) is not True:
            raise AssertionError(f"{sql_key}: syntax evidence did not pass")


def assert_patch_matrix_matches_scenarios(scenarios: list[dict], patches: list[dict]) -> None:
    patch_by_key = {str(row["sqlKey"]): row for row in patches}
    for scenario in scenarios:
        sql_key = str(scenario["sqlKey"])
        patch = patch_by_key[sql_key]
        expected_reason = scenario["targetPatchReasonCode"]
        actual_reason = (patch.get("selectionReason") or {}).get("code")
        if actual_reason != expected_reason:
            raise AssertionError(f"{sql_key}: expected selection reason {expected_reason!r}, got {actual_reason!r}")
        expected_strategy = scenario["targetPatchStrategy"]
        actual_strategy = patch.get("strategyType")
        if actual_strategy != expected_strategy:
            raise AssertionError(f"{sql_key}: expected strategy {expected_strategy!r}, got {actual_strategy!r}")
        expected_blocker_family = str(scenario["targetBlockerFamily"])
        actual_blocker_family = patch_blocker_family(patch)
        if actual_blocker_family != expected_blocker_family:
            raise AssertionError(
                f"{sql_key}: expected blocker family {expected_blocker_family!r}, got {actual_blocker_family!r}"
            )
        if scenario["targetPatchStrategy"]:
            if not patch.get("patchFiles"):
                raise AssertionError(f"{sql_key}: expected patch files for applicable strategy")
            if not patch_apply_ready(patch):
                raise AssertionError(f"{sql_key}: expected apply-ready patch")
            patch_text = "\n".join(str(x) for x in (patch.get("_patchTexts") or []))
            added_text = "\n".join(
                line[1:]
                for line in patch_text.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            for snippet in scenario["targetPatchMustContain"]:
                if str(snippet) not in added_text:
                    raise AssertionError(f"{sql_key}: missing required patch snippet {snippet!r}")
            for snippet in scenario["targetPatchMustNotContain"]:
                if str(snippet) in added_text:
                    raise AssertionError(f"{sql_key}: found forbidden patch snippet {snippet!r}")
        else:
            if patch.get("patchFiles") != []:
                raise AssertionError(f"{sql_key}: expected no patch files for blocked/review scenario")
            if patch_apply_ready(patch):
                raise AssertionError(f"{sql_key}: blocked/review scenario unexpectedly became apply-ready")
