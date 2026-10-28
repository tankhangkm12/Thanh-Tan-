"""Locked tests: the files a person approved, kept as hashes, and the check that none of them changed.

When a person approves a step that has ``lock_on_approval`` (dev-core: ``test-spec``), ``create`` writes
``tasks/<task>/locked-files.json``. The lock holds, until the task is done or cancelled:

- the test files named by the ``- tests:`` lines of the step's report (``kind: test``);
- the files listed under ``## Hạ tầng test`` at the end of that report (``kind: infra``);
- the test configuration files found in the project by their names (``conftest.py``, ``pytest.ini``, ``tox.ini``,
  ``jest.config.*``...): locked whole (``scope: file``);
- ``pyproject.toml``, ``setup.cfg`` and ``package.json``, which carry more than test settings: only their test part is
  locked (``scope: part``: the ``[tool.pytest...]`` tables, ``[tool:pytest]``, the ``jest``/``vitest`` keys and
  ``scripts.test``), as a hash of the parsed data, so a new dependency does not matter.

``check`` compares the working tree and HEAD with the hashes; the gates and ``agentflow tests check`` use it. A person
changes a locked file with ``agentflow tests amend`` (see ``amend.py``). A lock is a tripwire against a hand that does not
know about it, not a sandbox: whoever runs code as the user can rewrite the files that hold the hashes.
"""

import configparser
import hashlib
import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentflow.constants import (
    DECISIONS_DIR,
    ENCODING,
    GIT_EXECUTABLE,
    IN_FLIGHT_TASK_STATUSES,
    STATE_FILE,
    TASKS_DIR,
    WORKSPACE_DIR_NAMES,
    ExitCode,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.git import run_git
from agentflow.mdutil import visible_lines

LOCKED_FILES_FILE = "locked-files.json"
INFRA_HEADING = "Hạ tầng test"
KIND_TEST, KIND_INFRA = "test", "infra"
SCOPE_FILE, SCOPE_PART = "file", "part"
KNOWN_TEST_SUFFIXES = frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})
AMEND_HINT = 'a person changes it with `agentflow tests amend {path} --reason "..."`'

_DEDICATED = re.compile(
    r"^(conftest\.py|pytest\.ini|tox\.ini"
    r"|jest\.config\.(js|cjs|mjs|ts|cts|mts|json)"
    r"|vitest\.config\.(js|cjs|mjs|ts|cts|mts|json)"
    r"|vitest\.workspace\.(js|cjs|mjs|ts|cts|mts|json)"
    r"|\.mocharc\.(js|cjs|json|jsonc|yml|yaml)"
    r"|karma\.conf\.(js|cjs|ts)"
    r"|phpunit\.xml(\.dist)?)$",
    re.IGNORECASE,
)
_SHARED = frozenset({"pyproject.toml", "setup.cfg", "package.json"})
_JSON_TEST_KEYS = ("jest", "vitest", "mocha", "ava")
_JSON_SCRIPT_KEYS = ("test", "pretest", "posttest")
_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
_NONE_WORDS = frozenset({"không có", "khong co", "none"})


# ------------------------------------------------------------------ names and digests


def posix(path: str | Path) -> str:
    """A project-relative path the way the lock writes it: forward slashes, no ``./``."""
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return re.sub(r"/{2,}", "/", text)


def folded(path: str) -> str:
    return os.path.normcase(posix(path))


def basename(path: str) -> str:
    return posix(path).rsplit("/", 1)[-1]


def is_dedicated(path: str) -> bool:
    """A file that exists only to configure tests: locked whole, and never created while a lock holds."""
    return _DEDICATED.match(basename(path)) is not None


def is_shared(path: str) -> bool:
    """A file that carries test settings among other things: locked by its test part only."""
    return basename(path).lower() in _SHARED


def is_config_name(path: str) -> bool:
    return is_dedicated(path) or is_shared(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(data: Any) -> str:
    return sha256_bytes(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode(ENCODING))


def settings_part(path: str, data: bytes) -> tuple[str, str] | None:
    """(label, digest) of the test settings in a shared file; ``None`` when it holds none. A file that cannot be read is
    its own part, so any change to it counts."""
    name = basename(path).lower()
    text = data.decode(ENCODING, errors="replace")
    try:
        if name == "pyproject.toml":
            tool = tomllib.loads(text).get("tool", {})
            picked = {key: value for key, value in tool.items() if key.lower().startswith("pytest")} if isinstance(tool, dict) else {}
            return ("[tool.pytest...]", _digest(picked)) if picked else None
        if name == "setup.cfg":
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            parser.read_string(text)
            picked = {section: dict(parser.items(section, raw=True)) for section in parser.sections() if section.lower().startswith("tool:pytest")}
            return ("[tool:pytest]", _digest(picked)) if picked else None
        if name == "package.json":
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            picked = {key: parsed[key] for key in _JSON_TEST_KEYS if key in parsed}
            scripts = parsed.get("scripts")
            if isinstance(scripts, dict):
                found = {key: scripts[key] for key in _JSON_SCRIPT_KEYS if key in scripts}
                if found:
                    picked["scripts"] = found
            return ("jest/vitest/mocha settings and scripts.test", _digest(picked)) if picked else None
    except (tomllib.TOMLDecodeError, configparser.Error, json.JSONDecodeError):
        return ("unreadable file", sha256_bytes(data))
    return None


def make_entry(path: str, data: bytes, kind: str) -> dict[str, Any] | None:
    """The record for a file with these bytes; ``None`` for a shared file that holds no test settings."""
    if is_shared(path):
        part = settings_part(path, data)
        return None if part is None else {"sha256": part[1], "kind": kind, "scope": SCOPE_PART, "part": part[0]}
    return {"sha256": sha256_bytes(data), "kind": kind, "scope": SCOPE_FILE}


def digest_of(entry: dict[str, Any], path: str, data: bytes) -> str | None:
    """What ``data`` is worth under the scope of ``entry``."""
    if entry.get("scope") == SCOPE_PART:
        part = settings_part(path, data)
        return None if part is None else part[1]
    return sha256_bytes(data)


# ------------------------------------------------------------------ git


def _git(root: Path, *args: str):
    return run_git(root, *args)


def _blob(root: Path, spec: str) -> bytes | None:
    done = subprocess.run([GIT_EXECUTABLE, "-C", str(root), "show", spec], capture_output=True, check=False)
    return done.stdout if done.returncode == 0 else None


def head_blob(root: Path, path: str) -> bytes | None:
    return _blob(root, f"HEAD:{posix(path)}")


def index_blob(root: Path, path: str) -> bytes | None:
    return _blob(root, f":{posix(path)}")


def commit_blob(root: Path, commit: str, path: str) -> bytes | None:
    return _blob(root, f"{commit}:{posix(path)}")


def _listing(root: Path, *args: str) -> list[str]:
    done = subprocess.run([GIT_EXECUTABLE, "-C", str(root), "ls-files", "-z", *args], capture_output=True, check=False)
    if done.returncode != 0:
        return []
    return [posix(part.decode(ENCODING, errors="replace")) for part in done.stdout.split(bytes(1)) if part]


def project_files(root: Path) -> list[str]:
    """Tracked files and untracked files that git does not ignore."""
    names = dict.fromkeys([*_listing(root), *_listing(root, "--others", "--exclude-standard")])
    return [name for name in names if not name.startswith(tuple(f"{folder}/" for folder in WORKSPACE_DIR_NAMES))]


def is_committed(root: Path, path: str) -> bool:
    return _git(root, "ls-files", "--error-unmatch", "--", posix(path)).returncode == 0


def is_clean(root: Path, path: str) -> bool:
    return not _git(root, "status", "--porcelain", "--", posix(path)).stdout.strip()


def head_exists(root: Path) -> bool:
    return _git(root, "rev-parse", "--verify", "HEAD").returncode == 0


# ------------------------------------------------------------------ the report


def declared_infra(report_text: str) -> list[str]:
    """The paths under the heading ``## Hạ tầng test`` of a report (``không có`` or nothing: none)."""
    inside = False
    found: list[str] = []
    for line in visible_lines(report_text):
        heading = _HEADING.match(line)
        if heading:
            inside = heading.group("title").strip().lower() == INFRA_HEADING.lower()
            continue
        if not inside:
            continue
        bullet = _BULLET.match(line)
        if bullet is None:
            continue
        text = bullet.group("text").strip()
        if text.lower().rstrip(".") in _NONE_WORDS:
            continue
        if text.startswith("`") and "`" in text[1:]:
            path = text[1:].split("`", 1)[0]
        else:
            path = text.split()[0].rstrip(":,;")
        path = posix(path.strip("`").strip())
        if path and path not in found:
            found.append(path)
    return found


# ------------------------------------------------------------------ the plan: which files would be locked


@dataclass
class Plan:
    """The files a lock would hold right now, in the order the checklist lists them, and what is wrong with them."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)

    def digests(self) -> dict[str, str]:
        return {path: entry["sha256"] for path, entry in self.entries.items()}


def _outside(path: str) -> bool:
    return path.startswith("/") or re.match(r"^[A-Za-z]:", path) is not None or ".." in path.split("/")


def _read(root: Path, path: str) -> bytes | None:
    target = root / path
    try:
        return target.read_bytes() if target.is_file() else None
    except OSError:
        return None


def _committed_problems(root: Path, path: str, what: str) -> list[str]:
    if not is_committed(root, path):
        return [f"{what} {path} is not committed (stage it and run `agentflow commit`)"]
    if not is_clean(root, path):
        return [f"{what} {path} has changes that are not committed (run `agentflow commit`)"]
    return []


def build_plan(root: Path, test_files: list[str], declared: list[str]) -> Plan:
    """What would be locked from these test files, these declared files and the configuration found by name.

    Problems are the ones the test-spec gate reports: a declared file that is missing, outside the project or not
    committed, and a test configuration file that is not committed.
    """
    plan = Plan(test_files=[posix(name) for name in test_files])
    for path in plan.test_files:
        data = _read(root, path)
        if data is not None:
            entry = make_entry(path, data, KIND_TEST)
            if entry is not None:
                plan.entries[path] = entry
    for path in declared:
        if _outside(path):
            plan.problems.append(f"{INFRA_HEADING}: {path} is outside the project")
            continue
        data = _read(root, path)
        if data is None:
            plan.problems.append(f"{INFRA_HEADING}: {path} does not exist")
            continue
        plan.problems += _committed_problems(root, path, f"{INFRA_HEADING}:")
        entry = make_entry(path, data, KIND_INFRA)
        if entry is not None and path not in plan.entries:
            plan.entries[path] = entry
    for path in sorted(project_files(root)):
        if not is_config_name(path) or path in plan.entries:
            continue
        data = _read(root, path)
        if data is None:
            continue
        entry = make_entry(path, data, KIND_INFRA)
        if entry is None:
            continue
        plan.problems += _committed_problems(root, path, "test configuration file")
        plan.entries[path] = entry
    if plan.test_files and not any(os.path.splitext(name)[1].lower() in KNOWN_TEST_SUFFIXES for name in plan.test_files):
        plan.warnings.append(
            f"the test files ({', '.join(plan.test_files)}) are in a language agentflow does not know, so it cannot find their "
            f"configuration by name: list every file that decides what they run under '## {INFRA_HEADING}' in the test-spec report, "
            "and read the L lines of the checklist"
        )
    return plan


# ------------------------------------------------------------------ the lock file


def lock_path(workspace_dir: Path, task_id: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / LOCKED_FILES_FILE


def load(workspace_dir: Path, task_id: str) -> dict[str, Any] | None:
    """The lock of a task; ``None`` when there is none. An unreadable lock is an integrity error."""
    path = lock_path(workspace_dir, task_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding=ENCODING))
    except (OSError, ValueError) as exc:
        raise AgentflowError(f"{LOCKED_FILES_FILE} cannot be read ({exc})", ExitCode.INTEGRITY_FAILED) from exc
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise AgentflowError(f"{LOCKED_FILES_FILE} is not in the form agentflow writes", ExitCode.INTEGRITY_FAILED)
    data.setdefault("windows", {})
    return data


def save(workspace_dir: Path, task_id: str, record: dict[str, Any]) -> str:
    """Write the lock file; returns the sha256 of what was written."""
    text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    path = lock_path(workspace_dir, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, text)
    return sha256_bytes(text.encode(ENCODING))


def file_digest(workspace_dir: Path, task_id: str) -> str | None:
    path = lock_path(workspace_dir, task_id)
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def window_for(record: dict[str, Any], path: str) -> dict[str, Any] | None:
    wanted = folded(path)
    for key, window in record.get("windows", {}).items():
        if folded(key) == wanted:
            return window
    return None


def entry_for(record: dict[str, Any], path: str) -> tuple[str, dict[str, Any]] | None:
    wanted = folded(path)
    for key, entry in record.get("files", {}).items():
        if folded(key) == wanted:
            return key, entry
    return None


def create(
    workspace_dir: Path,
    root: Path,
    task_id: str,
    step_id: str,
    test_files: list[str],
    declared: list[str],
    proven: dict[str, str] | None,
    at: str,
) -> tuple[dict[str, Any], list[str]]:
    """Lock the files of the approved step. ``proven`` are the digests the gate saw when agentflow ran the commands red:
    a file that differs now was changed after the proof, and nothing is locked. Returns the record and its warnings."""
    plan = build_plan(root, test_files, declared)
    if plan.problems:
        raise AgentflowError("the files to lock are not in order:\n  - " + "\n  - ".join(plan.problems), ExitCode.GATE_FAILED)
    if proven is not None:
        now = plan.digests()
        changed = sorted({*now, *proven} - {path for path in now if proven.get(path) == now[path]})
        if changed:
            raise AgentflowError(
                "these files are not what agentflow ran red (changed, added or removed after the commands passed): "
                + ", ".join(changed)
                + ". Send the step back (`agentflow task advance --result fail`) so the commands run again on what is there now",
                ExitCode.GATE_FAILED,
            )
    files: dict[str, dict[str, Any]] = {}
    for path, entry in plan.entries.items():
        head = head_blob(root, path)
        head_digest = None if head is None else digest_of(entry, path, head)
        files[path] = {**entry, "head_sha256": head_digest}
    record = {"task": task_id, "step": step_id, "locked_at": at, "files": files, "windows": {}}
    return record, plan.warnings


# ------------------------------------------------------------------ checking


def check(workspace_dir: Path, root: Path, task_id: str) -> list[str] | None:
    """Problems of the lock of ``task_id`` (empty: intact); ``None`` when the task has no lock."""
    record = load(workspace_dir, task_id)
    if record is None:
        return None
    problems: list[str] = []
    has_head = head_exists(root)
    for path, entry in record["files"].items():
        window = window_for(record, path)
        data = _read(root, path)
        hint = "commit it with `agentflow commit` (a window is open)" if window else AMEND_HINT.format(path=path)
        if data is None:
            problems.append(f"{path}: missing (deleted or renamed); {hint}")
            continue
        if digest_of(entry, path, data) != entry.get("sha256"):
            what = "its test settings changed" if entry.get("scope") == SCOPE_PART else "changed in the working tree"
            problems.append(f"{path}: {what}; {hint}")
        if has_head and entry.get("head_sha256") is not None:
            head = head_blob(root, path)
            if head is None or digest_of(entry, path, head) != entry["head_sha256"]:
                problems.append(f"{path}: differs at HEAD (a commit changed it); {AMEND_HINT.format(path=path)}")
    known = {folded(path) for path in record["files"]}
    for path in sorted(project_files(root)):
        if folded(path) in known or not is_config_name(path):
            continue
        data = _read(root, path)
        if data is None:
            continue
        if is_shared(path):
            if settings_part(path, data) is None:
                continue
            problems.append(f"{path}: now holds test settings that were not locked; {AMEND_HINT.format(path=path)}")
        else:
            problems.append(f"{path}: a test configuration file that is not part of the approved tests; {AMEND_HINT.format(path=path)}")
    return problems


# ------------------------------------------------------------------ which locks are in force (the hook asks)


def active_task_ids(workspace_dir: Path) -> set[str] | None:
    """Ids of the tasks that are still going; ``None`` when ``state.json`` cannot be read (then every lock counts)."""
    try:
        tasks = json.loads((workspace_dir / STATE_FILE).read_text(encoding=ENCODING))["tasks"]
        return {task["id"] for task in tasks if task["status"] in {str(s) for s in IN_FLIGHT_TASK_STATUSES}}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def active_locks(workspace_dir: Path) -> list[dict[str, Any]]:
    """The locks of the tasks still going, as read from disk. A lock file that cannot be read counts as an empty lock
    (the hook then still closes the configuration file names)."""
    folder = workspace_dir / TASKS_DIR
    try:
        candidates = sorted(folder.glob(f"*/{LOCKED_FILES_FILE}"))
    except OSError:
        return []
    if not candidates:
        return []
    alive = active_task_ids(workspace_dir)
    found: list[dict[str, Any]] = []
    for path in candidates:
        task_id = path.parent.name
        if alive is not None and task_id not in alive:
            continue
        try:
            record = load(workspace_dir, task_id)
        except AgentflowError:
            record = None
        found.append(record or {"files": {}, "windows": {}})
    return found


def decision_path(workspace_dir: Path, name: str) -> Path:
    return workspace_dir / DECISIONS_DIR / name
