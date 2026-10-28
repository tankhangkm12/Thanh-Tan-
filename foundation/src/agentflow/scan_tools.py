"""The scanners dev-core runs itself: Semgrep, Trivy and Gitleaks. Plugins add more through extensions."""

import shutil
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from agentflow.errors import AgentflowError
from agentflow.constants import (
    CUSTOM_RULES_CACHE_DIR,
    CUSTOM_RULES_MOUNT,
    ExitCode,
    GITLEAKS_IMAGE,
    GITLEAKS_LEAKS_EXIT_CODE,
    SEMGREP_IMAGE,
    TRIVY_CACHE_VOLUME,
    TRIVY_IMAGE,
    NetworkMode,
    ResultKind,
)
from agentflow.scan_types import FileSelection, MountSpec, ResultSpec, ScanContext, ScanToolSpec
from agentflow.semgrep_rules import ensure_rules
from agentflow.scanner import SAFE_DIRECTORY_ENV

SEMGREP = "semgrep"
TRIVY = "trivy"
GITLEAKS = "gitleaks"
VAR_RULES_DIR = "rules_dir"
VAR_RANGE = "range"
RULES_MOUNT = "/rules"
TRIVY_CACHE_MOUNT = "/root/.cache"
SEMGREP_BLOCKING = ("ERROR",)
TRIVY_BLOCKING = ("HIGH", "CRITICAL")

def prepare_semgrep(context: ScanContext) -> None:
    """Fetch (or reuse) the rules; they are mounted read-only and never enter the repository."""
    rules = ensure_rules(context.cache_dir, context.rulesets, context.repo, context.fetcher, warn=context.warn)
    context.extra[VAR_RULES_DIR] = str(rules)


SEMGREP_SPEC = ScanToolSpec(
    id=SEMGREP,
    prepare=prepare_semgrep,
    image=SEMGREP_IMAGE,
    # Only the files the task changed; no network, rules come from the read-only cache mount.
    args=("semgrep", "scan", "--config", RULES_MOUNT, "--json", "--metrics=off", "--disable-version-check", "--quiet", "${files}"),
    network=NetworkMode.NONE,
    mounts=(MountSpec(f"${{var:{VAR_RULES_DIR}}}", RULES_MOUNT),),
    files=FileSelection(),
    skip_note="no changed files for Semgrep to scan",
    result=ResultSpec(
        kind=ResultKind.JSON_FINDINGS,
        items="results",
        rule_field="check_id",
        severity_field="extra.severity",
        location_field="path",
        message_field="extra.message",
        blocking_severities=SEMGREP_BLOCKING,
    ),
)

CUSTOM_RULES_VAR = "custom_rules_dir"
# A person's own rule can use any of Semgrep's severities; the strong ones block.
CUSTOM_BLOCKING = ("ERROR", "HIGH", "CRITICAL")
CONVENTIONS_SUFFIX = "conventions"


def custom_semgrep_spec(rules: Sequence[tuple[str, Path]], problems: Sequence[str]) -> ScanToolSpec:
    """Semgrep with the rules of the project's enforced conventions, in a folder of their own (read-only, no network).

    ``problems`` (a rule file that is missing or broken) make the scan fail instead of quietly checking less.
    """

    def prepare(context: ScanContext) -> None:
        if problems:
            raise AgentflowError("convention rules cannot be used:\n- " + "\n- ".join(problems), ExitCode.CONVENTIONS_INVALID)
        staged = context.cache_dir / CUSTOM_RULES_CACHE_DIR / context.repo.name
        shutil.rmtree(staged, ignore_errors=True)
        staged.mkdir(parents=True)
        for code, path in rules:
            shutil.copyfile(path, staged / f"{code}-{path.name}")
        context.extra[CUSTOM_RULES_VAR] = str(staged)

    return replace(
        SEMGREP_SPEC,
        id=f"{SEMGREP}-{CONVENTIONS_SUFFIX}",
        prepare=prepare,
        args=("semgrep", "scan", "--config", CUSTOM_RULES_MOUNT, "--json", "--metrics=off", "--disable-version-check", "--quiet", "${files}"),
        mounts=(MountSpec(f"${{var:{CUSTOM_RULES_VAR}}}", CUSTOM_RULES_MOUNT),),
        skip_note="no changed files for the convention rules to scan",
        result=replace(SEMGREP_SPEC.result, blocking_severities=CUSTOM_BLOCKING),
    )


TRIVY_SPEC = ScanToolSpec(
    id=TRIVY,
    image=TRIVY_IMAGE,
    args=("fs", "--scanners", "vuln", "--format", "json", "--quiet", "/repo"),
    # The vulnerability data is downloaded into the cache volume, so this one needs the network.
    network=NetworkMode.BRIDGE,
    mounts=(MountSpec(TRIVY_CACHE_VOLUME, TRIVY_CACHE_MOUNT, readonly=False, volume=True),),
    result=ResultSpec(
        kind=ResultKind.JSON_FINDINGS,
        items="Results[].Vulnerabilities",
        rule_field="VulnerabilityID",
        severity_field="Severity",
        location_field="PkgName",
        message_field="Title",
        blocking_severities=TRIVY_BLOCKING,
        # Only vulnerabilities that already have a fixed version block.
        require_field="FixedVersion",
    ),
)

GITLEAKS_SPEC = ScanToolSpec(
    id=GITLEAKS,
    image=GITLEAKS_IMAGE,
    args=(
        "git",
        f"--log-opts=${{var:{VAR_RANGE}}}",
        "--redact",
        "--no-banner",
        "--no-color",
        "--exit-code",
        str(GITLEAKS_LEAKS_EXIT_CODE),
        "--report-format",
        "json",
        "--report-path",
        "-",
        "/repo",
    ),
    network=NetworkMode.NONE,
    env=SAFE_DIRECTORY_ENV,
    result=ResultSpec(
        kind=ResultKind.JSON_FINDINGS,
        items="",
        rule_field="RuleID",
        location_field="Fingerprint",
        message_field="Description",
        # Any finding blocks.
        ok_exit_codes=(0, GITLEAKS_LEAKS_EXIT_CODE),
    ),
)

BUILTIN_TOOLS = (SEMGREP_SPEC, TRIVY_SPEC, GITLEAKS_SPEC)
