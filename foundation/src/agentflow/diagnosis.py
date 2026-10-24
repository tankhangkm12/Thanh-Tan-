"""Diagnoses: what an agent that only reads and runs found about a failure, kept for the person and the next role.

A diagnosis is Markdown with at least the sections ``## Tái hiện`` (how the failure was reproduced) and ``## Nguyên nhân``
(the root cause and the evidence for it). Where it goes depends on whether a task is open:

- with an open task: ``tasks/<task>/diagnoses/round-<n>.md`` (``n`` is the rework round; a second one in the same round
  gets ``round-<n>-2.md``), so the implementer and the reviewer of that task read it;
- with none: ``diagnoses/D-001.md``, ``D-002.md``, ... in the workspace, for a bugfix task a person starts afterwards.

A diagnosis never changes the state of a task and never replaces an earlier one.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from agentflow.constants import ENCODING, MARKDOWN_SUFFIX, TASKS_DIR, ExitCode
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic
from agentflow.models import State

DIAGNOSES_DIR = "diagnoses"
REQUIRED_HEADINGS = ("Tái hiện", "Nguyên nhân")
_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.M)
_CODE = re.compile(r"^D-(?P<number>\d+)$")
_CRLF, _LF = "\r\n", "\n"


@dataclass(frozen=True)
class Diagnosis:
    path: Path
    # ``D-001`` outside a task, ``round-1`` inside one.
    name: str
    task_id: str | None


def problems(content: str) -> list[str]:
    if not content.strip():
        return ["the diagnosis is empty"]
    titles = {match["title"].strip().lower() for match in _HEADING.finditer(content)}
    return [f"the diagnosis has no '## {heading}' section" for heading in REQUIRED_HEADINGS if heading.lower() not in titles]


def write(workspace_dir: Path, state: State, content: str) -> Diagnosis:
    found = problems(content)
    if found:
        raise AgentflowError("; ".join(found) + f" (write at least: {', '.join('## ' + h for h in REQUIRED_HEADINGS)})", ExitCode.INVALID_INPUT)
    task = state.active_task()
    if task is not None:
        folder = workspace_dir / TASKS_DIR / task.id / DIAGNOSES_DIR
        base = f"round-{task.loop_round}"
        name, number = base, 1
        while (folder / f"{name}{MARKDOWN_SUFFIX}").exists():
            number += 1
            name = f"{base}-{number}"
        task_id: str | None = task.id
    else:
        folder = workspace_dir / DIAGNOSES_DIR
        used = [int(m["number"]) for m in (_CODE.match(p.stem) for p in folder.glob(f"D-*{MARKDOWN_SUFFIX}")) if m] if folder.is_dir() else []
        name = f"D-{max(used, default=0) + 1:03d}"
        task_id = None
    path = folder / f"{name}{MARKDOWN_SUFFIX}"
    folder.mkdir(parents=True, exist_ok=True)
    text = content.replace(_CRLF, _LF)
    write_text_atomic(path, text if text.endswith(_LF) else text + _LF)
    return Diagnosis(path, name, task_id)


def listing(workspace_dir: Path, state: State) -> list[Diagnosis]:
    """The diagnoses of the open task, or with none open the ones kept outside any task; oldest first."""
    task = state.active_task()
    folder = workspace_dir / TASKS_DIR / task.id / DIAGNOSES_DIR if task is not None else workspace_dir / DIAGNOSES_DIR
    if not folder.is_dir():
        return []
    paths = sorted(folder.glob(f"*{MARKDOWN_SUFFIX}"), key=lambda p: (p.stat().st_mtime, p.name))
    return [Diagnosis(path, path.stem, task.id if task is not None else None) for path in paths]


def read(workspace_dir: Path, name: str) -> str:
    """A diagnosis kept outside a task, by its code (``D-001``)."""
    if not _CODE.match(name):
        raise AgentflowError(f"'{name}' is not a diagnosis code (D-001, D-002, ...)", ExitCode.INVALID_INPUT)
    path = workspace_dir / DIAGNOSES_DIR / f"{name}{MARKDOWN_SUFFIX}"
    if not path.is_file():
        raise AgentflowError(f"no diagnosis {name} in {path.parent}", ExitCode.INVALID_INPUT)
    return path.read_text(encoding=ENCODING)
