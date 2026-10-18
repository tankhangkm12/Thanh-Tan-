"""The parts of the locked-tests feature that the commands share: what is checked before a task command, how the lock is made
at the approval, and the rules a commit follows while a lock holds."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agentflow import lockfiles, testspec
from agentflow.amend import LockCommit
from agentflow.constants import ENCODING, StepStatus, TaskStatus
from agentflow.integrity import Integrity
from agentflow.models import Task, Workflow
from agentflow.plan import PlanItem
from agentflow.settings import get_value

TEST_SETTING_KEYS = ("test_command", "test_timeout_minutes")


def settings_digest(settings: Any) -> str:
    """What decides which command runs the tests and for how long, as one hash."""
    picked = {key: get_value(settings, key) for key in TEST_SETTING_KEYS}
    return lockfiles.sha256_bytes(json.dumps(picked, sort_keys=True, ensure_ascii=False, default=str).encode(ENCODING))


def verify(workspace_dir: Path, settings: Any, active: Task | None) -> None:
    """Before ``task new|advance|approve``: the lock file and the test settings are what agentflow last wrote."""
    integrity = Integrity(workspace_dir)
    if active is not None:
        integrity.verify_lock(active.id, lockfiles.file_digest(workspace_dir, active.id))
    integrity.verify_settings(settings_digest(settings))


def lock_on_approval(workspace_dir: Path, root: Path, workflow: Workflow, task: Task, at: str) -> tuple[list[str], list[str]]:
    """Lock the files of the step a person is about to approve, when the workflow says so. Returns the lines to print and the
    warnings. Raises (nothing is locked) when the files are not in order or are not what agentflow ran red."""
    step = workflow.get_step(task.current_step)
    if step is None or not step.lock_on_approval or task.status is not TaskStatus.OPEN or task.step_status is not StepStatus.AWAITING_APPROVAL:
        return [], []
    path = testspec.report_path(workspace_dir, task.id, step.id)
    text = path.read_text(encoding=ENCODING) if path.is_file() else ""
    test_files = [file for block in testspec.parse_report(text) for file in block.files]
    try:
        proven = json.loads(testspec.task_file(workspace_dir, task.id, testspec.VERIFY_RED_FILE).read_text(encoding=ENCODING)).get("files")
    except (OSError, ValueError):
        proven = None
    record, warnings = lockfiles.create(workspace_dir, root, task.id, step.id, test_files, lockfiles.declared_infra(text), proven, at)
    Integrity(workspace_dir).record_lock(task.id, lockfiles.save(workspace_dir, task.id, record))
    names = ", ".join(record["files"]) or "nothing"
    return [f"locked {len(record['files'])} file(s): {names}"], warnings


class _Rules:
    """Several ``CommitRules`` as one; the project's own first."""

    def __init__(self, rules: Sequence[Any]) -> None:
        self.rules = rules

    def commit_problems(self, item: PlanItem | None, staged: Sequence[str]) -> list[str]:
        problems: list[str] = []
        for rules in self.rules:
            problems += rules.commit_problems(item, staged)
        return problems


def commit_rules(project_rules: Any, lock: LockCommit | None) -> Any:
    if lock is None or not lock.active:
        return project_rules
    return lock if project_rules is None else _Rules([project_rules, lock])


def lock_commit(workspace_dir: Path, root: Path, active: Task | None, workflow: Workflow, lookup: Callable[[str], Any], at: str) -> LockCommit | None:
    return None if active is None else LockCommit(workspace_dir, root, active, workflow, lookup, at)
