"""Shared builders for the mission, roadmap and replan tests (phase B onward).

Not a test module: it holds sample documents and small helpers that several test files use.
"""

import io
import re
from pathlib import Path

from conftest import SAMPLE_WORKFLOW, git, write_workflow

from thanhtan.cli import main
from thanhtan.constants import ExitCode

# Exit codes the phase B design adds or reuses, spelled as numbers so a test about the feature does not need the
# feature to import: 22 INVALID_INPUT, 31 PROJECT_WRITE_REFUSED, 35 ROADMAP_INVALID (new).
INVALID_INPUT = 22
PROJECT_WRITE_REFUSED = 31
ROADMAP_INVALID = 35

PROFILE = """# Profile

A coffee shop ordering app.

## Mission
- why: Khách đặt món không phải xếp hàng.
- for: Khách của quán cà phê và nhân viên quầy.
- scope: Đặt món, thanh toán, báo bếp.
- out-of-scope: Giao hàng, chương trình thành viên.
- source: docs/vision.md:3

## Build
`make build`
"""

ROADMAP = """# Roadmap

### R1 - Đặt món
- status: todo
- goal: Khách đặt được món từ điện thoại.
- docs: docs/vision.md:10

### R2 - Thanh toán
- status: todo
- goal: Trả tiền bằng thẻ.
- docs: không có — chưa có tài liệu

### R3 - Báo bếp
- status: todo
- goal: Bếp nhận đơn ngay khi khách trả tiền.
- docs: https://example.com/kitchen-spec
"""

CONVENTIONS = """# Quy ước

### PC-01 - Constants
- check: review
- status: unconfirmed
- source: src/constants.py (inferred from code)
- description: Fixed values live in constants or enums.
"""

PLAN = """### C1 - Build it
- role: builder
- files: a.txt
- done-when: `true`
- docs: https://docs.example/a
"""


def sample_workflow(tmp_path: Path) -> Path:
    """The sample workflow with a plan gate on `build` and an approval on the last step `check`."""
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]
    data["steps"][2]["requires_approval"] = True
    return write_workflow(tmp_path / "plugin" / "workflow.yaml", data)


def init_workspace(repo: Path, workflow: Path, monkeypatch, capsys) -> Path:
    monkeypatch.chdir(repo)
    assert main(["init", "--workflow", str(workflow)]) == ExitCode.OK
    capsys.readouterr()
    return repo


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def say(monkeypatch, *argv: str, text: str | None = None) -> int:
    if text is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return main(list(argv))


def project_dir(repo: Path) -> Path:
    return repo / ".ThanhTan" / "project"


def roadmap_text(repo: Path) -> str:
    return (project_dir(repo) / "roadmap.md").read_text(encoding="utf-8")


def statuses(repo: Path) -> dict[str, str]:
    """Roadmap item code -> status, read from the file the way a person would."""
    found: dict[str, str] = {}
    for code, block in re.findall(r"^### (R\d+) - .*?$(.*?)(?=^### |\Z)", roadmap_text(repo), flags=re.M | re.S):
        status = re.search(r"^- status:\s*(\S+)", block, flags=re.M)
        found[code] = status.group(1) if status else "?"
    return found


def finish_task(repo: Path, monkeypatch, title: str, *extra: str) -> None:
    """Run the sample workflow to the last approval and approve it: the task ends `done` and sealed."""
    assert say(monkeypatch, "task", "new", title, *extra) == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")
    say(monkeypatch, "task", "approve")  # confirm -> build
    say(monkeypatch, "report", "--step", "build", text=PLAN)
    (repo / "a.txt").write_text(f"{title}\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    assert say(monkeypatch, "commit", f"add {title}", "--item", "C1") == ExitCode.OK
    say(monkeypatch, "task", "advance", "--result", "pass")  # build
    say(monkeypatch, "task", "advance", "--result", "pass")  # check, awaiting approval
    assert say(monkeypatch, "task", "approve") == ExitCode.OK
    git(repo, "switch", "-q", "develop")
