"""A person changes an approved test: ``agentflow tests amend`` opens a window, ``agentflow commit`` closes it.

``open_windows`` is the person's command. It opens one window per file (the hook then lets the tools change that file and
no other) and keeps the reason in ``decisions/``. ``LockCommit`` plugs into ``agentflow commit``: it refuses a commit that
changes a locked file without a window, a test configuration file that is new, or a test that passes on the old code (unless
the person opened the window with ``--accept-green``); after the commit it locks the new bytes, closes the windows, keeps
the red proof made again in ``verify-red.json`` under ``reverified`` and completes the decision.
"""

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agentflow import lockfiles, reverify, testspec
from agentflow.constants import DECISIONS_DIR, ENCODING, GIT_EXECUTABLE, MARKDOWN_SUFFIX, ExitCode, TestSpecMode
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.integrity import Integrity
from agentflow.models import Task, Workflow
from agentflow.plan import PlanItem

DECISION_SUFFIX = "-tests-amend"
ACCEPT_GREEN_FLAG = "--accept-green"
NEWLINE = chr(10)


def _stamp(at: str) -> str:
    return "".join(ch for ch in at if ch.isalnum())


def staged_changes(root: Path) -> list[tuple[str, str]]:
    """(status letter, path) of what is staged; a rename counts as a deletion and an addition."""
    done = subprocess.run([GIT_EXECUTABLE, "-C", str(root), "diff", "--cached", "--name-status", "--no-renames", "-z"], capture_output=True, check=False)
    if done.returncode != 0:
        return []
    parts = [part.decode(ENCODING, errors="replace") for part in done.stdout.split(bytes(1)) if part]
    return [(parts[i][:1], lockfiles.posix(parts[i + 1])) for i in range(0, len(parts) - 1, 2)]


# ------------------------------------------------------------------ the person's command


def open_windows(workspace_dir: Path, task_id: str, files: Sequence[str], reason: str, accept_green: bool, at: str) -> list[str]:
    """Open a window for each file; returns the lines to print. Nothing changes if any file is refused."""
    if not reason.strip():
        raise AgentflowError('give the reason a locked test is changed: --reason "..."', ExitCode.INVALID_INPUT)
    if not files:
        raise AgentflowError("name the files to open: agentflow tests amend <file>... --reason \"...\"", ExitCode.INVALID_INPUT)
    record = lockfiles.load(workspace_dir, task_id)
    if record is None:
        raise AgentflowError(f"nothing is locked yet for {task_id}: the test-spec step has to be approved first", ExitCode.INVALID_INPUT)
    paths = list(dict.fromkeys(lockfiles.posix(name) for name in files))
    refused = [
        f"{path} is not locked (it is neither an approved test file nor a test configuration file by name), so it needs no window"
        for path in paths
        if lockfiles.entry_for(record, path) is None and not lockfiles.is_config_name(path)
    ]
    if refused:
        raise AgentflowError("; ".join(refused), ExitCode.INVALID_INPUT)
    folder = workspace_dir / DECISIONS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{_stamp(at)}{DECISION_SUFFIX}{MARKDOWN_SUFFIX}"
    number = 1
    while (folder / name).exists():
        number += 1
        name = f"{_stamp(at)}{DECISION_SUFFIX}-{number}{MARKDOWN_SUFFIX}"
    lines = [
        f"# {task_id}: approved tests opened for a change by a person",
        "",
        f"- Time: {at}",
        f"- Reason: {reason.strip()}",
        f"- accept-green: {'yes' if accept_green else 'no'}",
        "",
        "## Files",
    ]
    printed = []
    for path in paths:
        held = lockfiles.entry_for(record, path)
        before = held[1]["sha256"] if held else "not locked yet"
        key = held[0] if held else path
        record["windows"][key] = {"reason": reason.strip(), "opened_at": at, "accept_green": accept_green, "decision": f"{DECISIONS_DIR}/{name}", "old_sha256": before}
        lines.append(f"- {path}: sha256 before {before}")
        printed.append(f"window opened for {path}" + (" (a test that passes on the old code is accepted)" if accept_green else ""))
    write_text_atomic(folder / name, "\n".join(lines) + "\n")
    Integrity(workspace_dir).record_lock(task_id, lockfiles.save(workspace_dir, task_id, record))
    return [*printed, f"decision recorded: {folder / name}", "edit the file, then commit it with `agentflow commit`: that closes the window"]


# ------------------------------------------------------------------ agentflow commit


class LockCommit:
    """``CommitRules`` for a task that has a lock; ``closed`` finishes what the commit started."""

    def __init__(self, workspace_dir: Path, root: Path, task: Task, workflow: Workflow, lookup: Any, at: str) -> None:
        self.workspace_dir, self.root, self.task, self.workflow, self.lookup, self.at = workspace_dir, root, task, workflow, lookup, at
        self.record = lockfiles.load(workspace_dir, task.id)
        self._windowed: list[tuple[str, str]] = []
        self._results: dict[str, dict] = {}

    @property
    def active(self) -> bool:
        return self.record is not None

    # --- before the commit

    def commit_problems(self, item: PlanItem | None, staged: Sequence[str]) -> list[str]:
        if self.record is None:
            return []
        problems: list[str] = []
        self._windowed = []
        for status, path in staged_changes(self.root):
            window = lockfiles.window_for(self.record, path)
            held = lockfiles.entry_for(self.record, path)
            if window is not None:
                self._windowed.append((status, path))
            elif held is not None:
                problems += self._locked_problem(status, path, held[1])
            elif lockfiles.is_dedicated(path) and status != "D":
                problems.append(f"{path}: a new test configuration file; it can make tests pass without the work. {lockfiles.AMEND_HINT.format(path=path)}")
            elif lockfiles.is_shared(path) and status != "D" and self._staged_part(path) is not None:
                problems.append(f"{path}: now holds test settings that are not locked. {lockfiles.AMEND_HINT.format(path=path)}")
        if problems:
            return problems
        return self._red_again() if self._windowed else []

    def _staged_part(self, path: str) -> str | None:
        data = lockfiles.index_blob(self.root, path)
        part = None if data is None else lockfiles.settings_part(path, data)
        return None if part is None else part[1]

    def _locked_problem(self, status: str, path: str, entry: dict[str, Any]) -> list[str]:
        hint = lockfiles.AMEND_HINT.format(path=path)
        if status == "D":
            return [f"{path}: a locked file cannot be deleted or renamed; {hint}"]
        if entry.get("scope") == lockfiles.SCOPE_PART:
            data = lockfiles.index_blob(self.root, path)
            if data is not None and lockfiles.digest_of(entry, path, data) == entry.get("sha256"):
                return []  # something else in the file changed: a dependency, a version
            return [f"{path}: its test settings are locked; {hint}"]
        return [f"{path}: a locked test file cannot be changed; {hint}"]

    def _jobs(self) -> list[tuple[str, str, list[str]]]:
        step = testspec.spec_step(self.workflow)
        if step is None:
            return []
        report = testspec.report_path(self.workspace_dir, self.task.id, step.id)
        if not report.is_file():
            return []
        blocks = [b for b in testspec.parse_report(report.read_text(encoding=ENCODING)) if not b.is_none and b.command]
        jobs: dict[str, tuple[str, list[str]]] = {}
        for _status, path in self._windowed:
            using = [b for b in blocks if lockfiles.folded(path) in {lockfiles.folded(f) for f in b.files}] or blocks
            for block in using:
                command, files = jobs.setdefault(block.code, (block.command, []))
                if path not in files:
                    files.append(path)
        return [(code, command, files) for code, (command, files) in jobs.items()]

    def _red_again(self) -> list[str]:
        try:
            record = json.loads(testspec.task_file(self.workspace_dir, self.task.id, testspec.VERIFY_RED_FILE).read_text(encoding=ENCODING))
        except (OSError, ValueError):
            return []
        head = record.get("head")
        jobs = self._jobs()
        if not head or not jobs:
            return []
        try:
            timeout = testspec.timeout_of(self.lookup)
        except ValueError as exc:
            return [str(exc)]
        overlay = {path: (None if status == "D" else lockfiles.index_blob(self.root, path)) for status, path in self._windowed}
        self._results = reverify.old_code_results(self.root, head, overlay, jobs, timeout, self.at)
        problems = []
        if self.workflow.test_spec_mode(self.task) is TestSpecMode.GREEN:
            # A task that keeps the behaviour: the changed test must still pass on the code as it was before the change.
            for code, result in self._results.items():
                if result["status"] == reverify.RED:
                    files = ", ".join(result["files"])
                    problems.append(
                        f"{code}: its command fails on the old code with {files} as you changed it, so the test no longer describes "
                        "the behaviour this task must keep. If the behaviour is meant to change, do it in a feature or bugfix task"
                    )
            return problems
        for code, result in self._results.items():
            if result["status"] != reverify.GREEN:
                continue
            if all(self._accepts(path) for path in result["files"]):
                continue
            files = ", ".join(result["files"])
            problems.append(
                f"{code}: its command passes on the old code with {files} as you changed it, so the test no longer proves the feature "
                f'(it has to fail there). If a person accepts that, they open the window with `agentflow tests amend {result["files"][0]} {ACCEPT_GREEN_FLAG} --reason "..."`'
            )
        return problems

    # --- after the commit

    def closed(self, sha: str) -> list[str]:
        """Lock the new bytes, close the windows, keep the red proof and complete the decisions; returns warnings."""
        record = lockfiles.load(self.workspace_dir, self.task.id)
        if record is None or not self._windowed:
            return []
        warnings: list[str] = []
        notes: dict[str, list[str]] = {}
        for status, path in self._windowed:
            held = lockfiles.entry_for(record, path)
            key = held[0] if held else path
            window = lockfiles.window_for(record, path) or {}
            kind = held[1].get("kind", lockfiles.KIND_INFRA) if held else lockfiles.KIND_INFRA
            lines = notes.setdefault(window.get("decision", ""), [])
            data = None if status == "D" else self._bytes(path, sha)
            entry = None if data is None else lockfiles.make_entry(path, data, kind)
            if entry is None:
                record["files"].pop(key, None)
                lines.append(f"- {path}: no longer locked (deleted, or no test settings left in it)")
            else:
                blob = lockfiles.commit_blob(self.root, sha, path)
                entry["head_sha256"] = None if blob is None else lockfiles.digest_of(entry, path, blob)
                record["files"][key] = entry
                lines.append(f"- {path}: sha256 now {entry['sha256']}")
            record["windows"] = {k: w for k, w in record["windows"].items() if lockfiles.folded(k) != lockfiles.folded(path)}
        for code, result in self._results.items():
            note = f"- {code}: {result['status']} on the old code (exit {result['exit_code']})"
            if result["status"] == reverify.GREEN and all(self._accepts(path) for path in result["files"]):
                result["accepted"] = True
                note += f" - accepted by a person with {ACCEPT_GREEN_FLAG}"
                warnings.append(f"{code} passes on the old code with {', '.join(result['files'])}: accepted by a person ({ACCEPT_GREEN_FLAG}); the test no longer proves the feature")
            elif result["status"] in {reverify.TIMEOUT, reverify.NOT_FOUND, reverify.NOT_RUN}:
                warnings.append(f"{code}: its command could not be run on the old code ({result['status']}), so the red proof was not made again")
            for lines in notes.values():
                lines.append(note)
        self._keep_results()
        Integrity(self.workspace_dir).record_lock(self.task.id, lockfiles.save(self.workspace_dir, self.task.id, record))
        for name, lines in notes.items():
            path = self.workspace_dir / name if name else None
            if path is not None and path.is_file():
                text = path.read_text(encoding=ENCODING).rstrip(NEWLINE)
                closing = f"{NEWLINE}{NEWLINE}## Closed {self.at} by commit {sha[:7]}{NEWLINE}"
                write_text_atomic(path, text + closing + NEWLINE.join(lines) + NEWLINE)
        return warnings

    def _accepts(self, path: str) -> bool:
        window = lockfiles.window_for(self.record or {}, path)
        return bool(window and window.get("accept_green"))

    def _bytes(self, path: str, sha: str) -> bytes | None:
        target = self.root / path
        return target.read_bytes() if target.is_file() else lockfiles.commit_blob(self.root, sha, path)

    def _keep_results(self) -> None:
        if not self._results:
            return
        file = testspec.task_file(self.workspace_dir, self.task.id, testspec.VERIFY_RED_FILE)
        try:
            data = json.loads(file.read_text(encoding=ENCODING))
        except (OSError, ValueError):
            return
        data.setdefault("reverified", {}).update(self._results)
        testspec.save_record(file, data)
