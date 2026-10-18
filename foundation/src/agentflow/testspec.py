"""Tests first: the report of the step where tests are written before the code, and the two gates built on it.

``test-spec-valid`` reads the report (one block per plan item), checks the test files and RUNS each command itself: a test
must fail before the code exists. ``tests-pass`` runs the project's test command and the same commands again, which must
now exit 0. What the report says about a run is for a person to read; agentflow believes only its own runs, kept in
``verify-red.json`` and ``tests-pass.json`` next to the task.

Report block (one per plan item)::

    ### C1 - Title
    - tests: tests/test_a.py::test_x, tests/test_a.py::test_y      (or: không có — <how it is checked instead>)
    - command: `uv run pytest tests/test_a.py`
    - red: fail
    - reason: why they fail now
    - output: |
        the tail of the output
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentflow import testrun
from agentflow.confirmations import Confirmations
from agentflow.constants import (
    ENCODING,
    MARKDOWN_SUFFIX,
    REPORTS_DIR,
    TASKS_DIR,
    ExitCode,
    GateKind,
    PlanItemKind,
    ProjectSection,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.mdutil import visible_lines
from agentflow.models import Step, Task, Workflow
from agentflow.plan import PlanItem, parse_plan

VERIFY_RED_FILE = "verify-red.json"
TESTS_PASS_FILE = "tests-pass.json"
TEST_COMMAND_KEY = "test_command"
TEST_TIMEOUT_KEY = "test_timeout_minutes"
PROFILE_COMMAND_KEY = "test-command"
NONE_WORD = "không có"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RED, GREEN, TIMEOUT, NOT_FOUND, NONE = "red", "green", "timeout", "not-found", "none"

_BLOCK = re.compile(r"^###\s+(?P<code>C\d+)\b.*$")
_FIELD = re.compile(r"^-\s+(?P<key>tests|command|red|reason|output):\s*(?P<value>.*?)\s*$")
_NO_TEST = re.compile(rf"^{NONE_WORD}\s*(?:[—–-]+\s*(?P<how>.*))?$", re.IGNORECASE)
_PROFILE_LINE = re.compile(rf"^\s*[-*]\s+{PROFILE_COMMAND_KEY}:\s*(?P<command>.+?)\s*$")
_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass
class Block:
    code: str
    fields: dict[str, str] = field(default_factory=dict)
    count: int = 1

    @property
    def tests(self) -> list[str]:
        raw = self.fields.get("tests", "")
        return [] if self.is_none else [part.strip() for part in raw.split(",") if part.strip()]

    @property
    def is_none(self) -> bool:
        return _NO_TEST.match(self.fields.get("tests", "").strip()) is not None

    @property
    def how(self) -> str:
        found = _NO_TEST.match(self.fields.get("tests", "").strip())
        return (found.group("how") or "").strip() if found else ""

    @property
    def command(self) -> str:
        return self.fields.get("command", "").strip().strip("`").strip()

    @property
    def files(self) -> list[str]:
        return [entry.split("::", 1)[0].strip() for entry in self.tests]


def save_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def task_file(workspace_dir: Path, task_id: str, name: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / name


def report_path(workspace_dir: Path, task_id: str, step_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / REPORTS_DIR / f"{step_id}{MARKDOWN_SUFFIX}"


# ------------------------------------------------------------------ reading the report


def parse_report(text: str) -> list[Block]:
    """The blocks of a test-spec report, in order; a code written twice is one block with ``count`` 2."""
    blocks: list[Block] = []
    seen: dict[str, Block] = {}
    current: Block | None = None
    key: str | None = None
    collecting: list[str] = []

    def close_output() -> None:
        nonlocal collecting
        if current is not None and key == "output":
            current.fields["output"] = "\n".join(collecting).strip()
        collecting = []

    for line in visible_lines(text):
        heading = _BLOCK.match(line)
        if heading:
            close_output()
            code = heading.group("code")
            if code in seen:
                seen[code].count += 1
                current = None
            else:
                current = Block(code)
                seen[code] = current
                blocks.append(current)
            key = None
            continue
        if current is None:
            continue
        found = _FIELD.match(line)
        if found:
            close_output()
            key = found.group("key")
            value = found.group("value")
            if key == "output":
                collecting = [] if value in {"", "|"} else [value]
            else:
                current.fields[key] = value
            continue
        if key == "output" and (line.startswith((" ", "\t")) or not line.strip()):
            collecting.append(line.strip())
    close_output()
    return blocks


def plan_items(workspace_dir: Path, workflow: Workflow, task: Task) -> tuple[PlanItem, ...]:
    """The items of the plan: the report of the first step that has the gate ``plan-valid``."""
    step = next((s for s in workflow.steps if GateKind.PLAN_VALID in s.gates), None)
    if step is None:
        return ()
    path = report_path(workspace_dir, task.id, step.id)
    return parse_plan(path.read_text(encoding=ENCODING)).items if path.is_file() else ()


def spec_step(workflow: Workflow) -> Step | None:
    return next((s for s in workflow.steps if GateKind.TEST_SPEC_VALID in s.gates), None)


# ------------------------------------------------------------------ checking the report


def report_problems(blocks: list[Block], items: tuple[PlanItem, ...], root: Path) -> list[str]:
    problems: list[str] = []
    wanted = [item.code for item in items]
    by_code = {block.code: block for block in blocks}
    problems += [f"{code} has no block in the test-spec report (every plan item needs one)" for code in wanted if code not in by_code]
    problems += [f"{block.code} is not an item of the plan" for block in blocks if block.code not in wanted]
    problems += [f"{block.code} appears more than once in the report" for block in blocks if block.count > 1]
    for block in blocks:
        if block.code in wanted:
            problems += _block_problems(block, root)
    return problems


def _block_problems(block: Block, root: Path) -> list[str]:
    code = block.code
    tests = block.fields.get("tests", "").strip()
    if not tests:
        return [f"{code}: missing field 'tests'"]
    if block.is_none:
        return [] if block.how else [f"{code}: '{NONE_WORD}' needs a reason: write '{NONE_WORD} — <how the item is checked instead>'"]
    problems = []
    command = block.command
    if not command:
        problems.append(f"{code}: missing field 'command'")
    if block.fields.get("red", "").strip().lower() != "fail":
        problems.append(f"{code}: field 'red' must be 'fail' (a test that does not fail first proves nothing)")
    if not block.fields.get("reason", "").strip():
        problems.append(f"{code}: field 'reason' is empty (say why the tests fail now)")
    if not block.fields.get("output", "").strip():
        problems.append(f"{code}: field 'output' is empty (paste the tail of the output)")
    files = block.files
    for file in files:
        problems += _file_problems(code, file, root)
    if command and files and not any(file.replace("\\", "/") in command.replace("\\", "/") for file in files):
        problems.append(f"{code}: the command must mention one of its test files ({', '.join(files)}); '{command}' runs something else")
    return problems


def _file_problems(code: str, file: str, root: Path) -> list[str]:
    normal = file.replace("\\", "/")
    if normal.startswith("/") or _DRIVE.match(normal) or ".." in normal.split("/"):
        return [f"{code}: test path {file} is outside the project"]
    if not (root / normal).is_file():
        return [f"{code}: test file {normal} does not exist"]
    tracked = _git(root, "ls-files", "--error-unmatch", "--", normal)
    if tracked.returncode != 0:
        return [f"{code}: test file {normal} is not committed (stage it and run `agentflow commit`)"]
    if _git(root, "status", "--porcelain", "--", normal).stdout.strip():
        return [f"{code}: test file {normal} has changes that are not committed (run `agentflow commit`)"]
    return []


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False, encoding=ENCODING, errors="replace")


# ------------------------------------------------------------------ running


def timeout_of(lookup) -> float:
    return testrun.timeout_seconds(lookup(TEST_TIMEOUT_KEY))


def result_entry(command: str, run: testrun.RunResult, expect_fail: bool) -> dict[str, Any]:
    if run.timed_out:
        status = TIMEOUT
    elif run.not_found:
        status = NOT_FOUND
    elif run.exit_code == 0:
        status = GREEN
    else:
        status = RED
    return {"command": command, "exit_code": run.exit_code, "status": status, "duration_seconds": run.duration_seconds, "output": run.output}


def run_unique(commands: list[str], root: Path, timeout: float) -> dict[str, testrun.RunResult]:
    """Each distinct command once, in the order first met."""
    done: dict[str, testrun.RunResult] = {}
    for command in commands:
        if command not in done:
            done[command] = testrun.run_command(command, root, timeout)
    return done


def verify_red(workspace_dir: Path, workflow: Workflow, task: Task, root: Path, head: str, lookup) -> tuple[list[str], dict[str, Any] | None]:
    """The problems of the report, and (when it is in order) the record of running every command."""
    step = spec_step(workflow)
    if step is None:
        return ["this workflow has no test-spec step"], None
    path = report_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        return [f"no report for step '{step.id}' yet (save it with `agentflow report --step {step.id}`)"], None
    blocks = parse_report(path.read_text(encoding=ENCODING))
    problems = report_problems(blocks, plan_items(workspace_dir, workflow, task), root)
    try:
        timeout = timeout_of(lookup)
    except ValueError as exc:
        problems.append(str(exc))
    if problems:
        return problems, None
    runs = run_unique([b.command for b in blocks if not b.is_none], root, timeout)
    results: dict[str, Any] = {}
    for block in blocks:
        if block.is_none:
            results[block.code] = {"status": NONE, "reason": block.how}
            continue
        entry = result_entry(block.command, runs[block.command], True)
        results[block.code] = entry
        problems += _red_problems(block.code, entry, timeout)
    record = {"head": head, "at": now(), "results": results}
    save_record(task_file(workspace_dir, task.id, VERIFY_RED_FILE), record)
    return problems, record


def _red_problems(code: str, entry: dict[str, Any], timeout: float) -> list[str]:
    status = entry["status"]
    if status == RED:
        return []
    if status == GREEN:
        return [f"{code}: the command did not fail (exit 0), so it proves nothing yet:\n{_indent(entry['output'])}"]
    if status == TIMEOUT:
        return [f"{code}: the command timed out after {timeout / 60:g} minutes"]
    return [f"{code}: the command cannot run (command not found?):\n{_indent(entry['output'])}"]


def _indent(text: str) -> str:
    return "\n".join(f"      {line}" for line in text.strip().splitlines()[-15:])


# ------------------------------------------------------------------ tests-pass


@dataclass(frozen=True)
class ProjectCommand:
    command: str | None
    source: str
    problem: str | None = None


def project_command(workspace_dir: Path, lookup) -> ProjectCommand:
    configured = lookup(TEST_COMMAND_KEY)
    if isinstance(configured, str) and configured.strip():
        return ProjectCommand(configured.strip(), "config")
    from agentflow.project import document_path

    path = document_path(workspace_dir, ProjectSection.PROFILE)
    if not path.is_file():
        return ProjectCommand(None, "none", "there is no project profile")
    text = path.read_text(encoding=ENCODING)
    if not Confirmations.load(workspace_dir).is_confirmed(str(ProjectSection.PROFILE), text):
        return ProjectCommand(None, "none", "the profile is not confirmed (or changed since): a person runs `agentflow project confirm profile`")
    found = [m.group("command").strip().strip("`").strip() for m in map(_PROFILE_LINE.match, visible_lines(text)) if m]
    if len(found) > 1:
        return ProjectCommand(None, "none", f"the profile has more than one '- {PROFILE_COMMAND_KEY}:' line, so it is not clear which to run")
    if not found:
        return ProjectCommand(None, "none", f"the profile has no '- {PROFILE_COMMAND_KEY}: <command>' line")
    return ProjectCommand(found[0], "profile")


def missing_command_text(why: str) -> str:
    return (
        f"no test command: {why}. Give one of two ways: a person runs `agentflow config set {TEST_COMMAND_KEY} \"<command>\"`, or the "
        f"profile gets a line `- {PROFILE_COMMAND_KEY}: <command>` and a person runs `agentflow project confirm profile`"
    )


def spec_commands(workspace_dir: Path, workflow: Workflow, task: Task) -> tuple[list[tuple[str, Block]], list[str]]:
    """The (command, block) pairs to run again, checked against ``verify-red.json``; plus the problems found."""
    step = spec_step(workflow)
    if step is None:
        return [], []
    path = report_path(workspace_dir, task.id, step.id)
    if not path.is_file():
        return [], [f"the approved report of step '{step.id}' is missing, so the {VERIFY_RED_FILE} cannot be checked"]
    blocks = parse_report(path.read_text(encoding=ENCODING))
    record_path = task_file(workspace_dir, task.id, VERIFY_RED_FILE)
    try:
        results = json.loads(record_path.read_text(encoding=ENCODING))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        return [], [f"{VERIFY_RED_FILE} is missing or unreadable: the test-spec step has to pass through agentflow first"]
    problems = []
    for block in blocks:
        entry = results.get(block.code)
        if not isinstance(entry, dict):
            problems.append(f"{VERIFY_RED_FILE} does not match the approved test-spec report: {block.code} is missing from it")
        elif block.is_none:
            continue
        elif entry.get("command") != block.command or entry.get("status") != RED:
            problems.append(f"{VERIFY_RED_FILE} does not match the approved test-spec report: {block.code} was not recorded as red with the command of the report")
    problems += [
        f"{VERIFY_RED_FILE} does not match the approved test-spec report: {code} is not in the report"
        for code in results
        if code not in {b.code for b in blocks}
    ]
    return ([(b.command, b) for b in blocks if not b.is_none], problems)


def tests_pass(workspace_dir: Path, workflow: Workflow, task: Task, root: Path, head: str, lookup) -> tuple[list[str], str | None]:
    """Run the project's test command and the commands of the test-spec; return the problems and, when only a warning is
    due, its text. The record is written either way."""
    problems: list[str] = []
    try:
        timeout = timeout_of(lookup)
    except ValueError as exc:
        return [str(exc)], None
    chosen = project_command(workspace_dir, lookup)
    items = plan_items(workspace_dir, workflow, task)
    pairs, spec_problems = spec_commands(workspace_dir, workflow, task)
    problems += spec_problems
    record: dict[str, Any] = {"head": head, "at": now(), "source": chosen.source, "command": chosen.command, "spec_results": {}}
    warning = None
    if chosen.command is None:
        only_other = bool(items) and all((item.kind or "").lower() == PlanItemKind.OTHER for item in items)
        if only_other:
            warning = f"warning: {missing_command_text(chosen.problem or 'not set')}; the plan has only 'kind: other' items, so the step passes without it"
        else:
            problems.append(missing_command_text(chosen.problem or "not set"))
        record.update(status="skipped", exit_code=None, output="")
    else:
        run = testrun.run_command(chosen.command, root, timeout)
        record.update(exit_code=run.exit_code, output=run.output, duration_seconds=run.duration_seconds)
        if run.timed_out:
            record["status"] = TIMEOUT
            problems.append(f"the project's test command timed out after {timeout / 60:g} minutes")
        elif run.exit_code != 0:
            record["status"] = "fail"
            problems.append(f"the project's test command failed (exit {run.exit_code}):\n{_indent(run.output)}")
        else:
            record["status"] = "pass"
    if not spec_problems:
        runs = run_unique([command for command, _ in pairs], root, timeout)
        for block in (b for _, b in pairs):
            entry = result_entry(block.command, runs[block.command], False)
            record["spec_results"][block.code] = entry
            if entry["status"] != GREEN:
                problems.append(f"{block.code}: its command still fails (exit {entry['exit_code']}) after the build:\n{_indent(entry['output'])}")
        for code, how in ((b.code, b.how) for b in parse_report_for(workspace_dir, workflow, task) if b.is_none):
            record["spec_results"][code] = {"status": NONE, "reason": how}
    if problems and record["status"] in {"pass", "skipped"}:
        record["status"] = "fail"
    save_record(task_file(workspace_dir, task.id, TESTS_PASS_FILE), record)
    return problems, warning


def parse_report_for(workspace_dir: Path, workflow: Workflow, task: Task) -> list[Block]:
    step = spec_step(workflow)
    if step is None:
        return []
    path = report_path(workspace_dir, task.id, step.id)
    return parse_report(path.read_text(encoding=ENCODING)) if path.is_file() else []


def require_active_spec_step(workflow: Workflow, task: Task) -> Step:
    step = workflow.get_step(task.current_step)
    if step is None or GateKind.TEST_SPEC_VALID not in step.gates:
        raise AgentflowError(f"step '{task.current_step}' has no test-spec: `agentflow tests verify-red` works at the step that has the gate {GateKind.TEST_SPEC_VALID}", ExitCode.INVALID_INPUT)
    return step
