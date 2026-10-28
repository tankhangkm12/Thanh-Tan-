import pytest
from conftest import git

from agentflow.constants import ExitCode, StepStatus, TaskEvent, TaskStatus, TaskType
from agentflow.errors import AgentflowError
from agentflow.git import SubprocessGit
from agentflow.models import State, Task
from agentflow.state import JsonStateStore
from agentflow.tasks import (
    advance_task,
    approve_task,
    branch_name,
    cancel_task,
    new_task,
    next_task_id,
    require_active_task,
    slugify,
    write_report,
)
from agentflow.workspace import init_workspace, load_workspace_workflow

AT = "2026-10-10T10:00:00Z"


def clock():
    return AT


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Thêm đăng nhập bằng Google", "them-dang-nhap-bang-google"),
        ("ĐỔI   mật khẩu!!", "doi-mat-khau"),
        ("Fix: crash on start (v2)", "fix-crash-on-start-v2"),
        ("--- ", "task"),
        ("日本語", "task"),
        ("a" * 50, "a" * 40),
        ("word " * 12, "word-word-word-word-word-word-word-word"),
    ],
)
def test_slugify(title, slug):
    assert slugify(title) == slug
    assert len(slugify(title)) <= 40


def test_next_task_id():
    assert next_task_id(State()) == "T-001"
    tasks = (
        Task("T-002", "a", TaskStatus.DONE, "x", StepStatus.PASSED),
        Task("T-010", "b", TaskStatus.CANCELLED, "x", StepStatus.IN_PROGRESS),
    )
    assert next_task_id(State(tasks=tasks)) == "T-011"


def test_branch_name():
    assert branch_name(TaskType.HOTFIX, "T-003", "Sửa lỗi thanh toán") == "hotfix/T-003-sua-loi-thanh-toan"


@pytest.fixture
def ws(gitflow_repo, workflow_file):
    paths = init_workspace(gitflow_repo, workflow_file).paths
    workflow = load_workspace_workflow(paths)
    store = JsonStateStore(paths.dir, workflow, clock=clock)
    return paths, workflow, store, SubprocessGit(gitflow_repo)


@pytest.mark.parametrize(
    ("task_type", "base"), [(TaskType.FEATURE, "develop"), (TaskType.BUGFIX, "develop"), (TaskType.HOTFIX, "main")]
)
def test_new_task_branches_from_gitflow_base(ws, gitflow_repo, task_type, base):
    paths, workflow, store, client = ws
    (gitflow_repo / "dev.txt").write_text("only on develop", encoding="utf-8")
    git(gitflow_repo, "add", "dev.txt")
    git(gitflow_repo, "commit", "-q", "-m", "develop work")
    task = new_task(store, workflow, client, "Thêm trang chủ", task_type, clock)
    assert task.id == "T-001"
    assert task.branch == f"{task_type}/T-001-them-trang-chu"
    assert client.current_branch() == task.branch
    assert git(gitflow_repo, "merge-base", "--is-ancestor", base, "HEAD") == ""
    assert (gitflow_repo / "dev.txt").exists() is (base == "develop")
    state = store.load()
    assert state.active_task_id == "T-001"
    assert state.tasks[0].branch == task.branch
    assert state.tasks[0].current_step == "confirm"


def test_new_task_refuses_dirty_tree(ws, gitflow_repo):
    paths, workflow, store, client = ws
    (gitflow_repo / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(AgentflowError) as exc:
        new_task(store, workflow, client, "x", TaskType.FEATURE, clock)
    assert exc.value.code is ExitCode.DIRTY_WORKING_TREE
    assert client.current_branch() == "develop"
    assert store.load().tasks == ()


def test_new_task_refuses_missing_base(ws, gitflow_repo):
    paths, workflow, store, client = ws
    git(gitflow_repo, "switch", "-q", "main")
    git(gitflow_repo, "branch", "-q", "-D", "develop")
    with pytest.raises(AgentflowError) as exc:
        new_task(store, workflow, client, "x", TaskType.FEATURE, clock)
    assert exc.value.code is ExitCode.BRANCH_PROBLEM
    assert "'develop'" in str(exc.value)


def test_new_task_refuses_existing_branch(ws, gitflow_repo):
    paths, workflow, store, client = ws
    git(gitflow_repo, "branch", "feature/T-001-x")
    with pytest.raises(AgentflowError) as exc:
        new_task(store, workflow, client, "x", TaskType.FEATURE, clock)
    assert exc.value.code is ExitCode.BRANCH_PROBLEM


@pytest.mark.parametrize("finish", [None, "cancel"])
def test_new_task_refuses_while_a_task_is_in_flight(ws, gitflow_repo, finish):
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "first", TaskType.FEATURE, clock)
    if finish is None:
        with pytest.raises(AgentflowError) as exc:
            new_task(store, workflow, client, "second", TaskType.FEATURE, clock)
        assert exc.value.code is ExitCode.TASK_CONFLICT
        assert "T-001 (open)" in str(exc.value)
    else:
        cancel_task(store, workflow, clock)
        assert new_task(store, workflow, client, "second", TaskType.FEATURE, clock).id == "T-002"


def test_new_task_refuses_empty_title(ws):
    paths, workflow, store, client = ws
    with pytest.raises(AgentflowError) as exc:
        new_task(store, workflow, client, "   ", TaskType.FEATURE, clock)
    assert exc.value.code is ExitCode.INVALID_INPUT


def test_lifecycle_through_the_store(ws):
    # Sample workflow: confirm (approval) -> build -> check (on_fail build), max 2 rounds.
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    assert advance_task(store, workflow, TaskEvent.PASS, clock).step_status is StepStatus.AWAITING_APPROVAL
    assert approve_task(store, workflow, paths.dir, clock).task.current_step == "build"
    advance_task(store, workflow, TaskEvent.PASS, clock)
    reworked = advance_task(store, workflow, TaskEvent.FAIL, clock)
    assert (reworked.current_step, reworked.loop_round) == ("build", 1)
    advance_task(store, workflow, TaskEvent.PASS, clock)
    done = advance_task(store, workflow, TaskEvent.PASS, clock)
    assert done.status is TaskStatus.DONE
    state = store.load()
    assert state.active_task_id is None
    assert state.tasks[0].status is TaskStatus.DONE
    with pytest.raises(AgentflowError) as exc:
        advance_task(store, workflow, TaskEvent.PASS, clock)
    assert exc.value.code is ExitCode.NO_ACTIVE_TASK


def test_override_of_blocked_task_writes_a_decision(ws):
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    advance_task(store, workflow, TaskEvent.PASS, clock)
    approve_task(store, workflow, paths.dir, clock)
    advance_task(store, workflow, TaskEvent.FAIL, clock)  # build has no on_fail: blocked at once
    assert store.load().active_task().status is TaskStatus.BLOCKED

    result = approve_task(store, workflow, paths.dir, clock, reason="flaky CI, checked by hand")
    assert result.task.status is TaskStatus.OPEN
    assert result.decision_file is not None
    assert result.decision_file.parent == paths.dir / "decisions"
    assert result.decision_file.name == "T-001-20261010T100000Z-override.md"
    text = result.decision_file.read_text(encoding="utf-8")
    assert "- Blocked at: step 'build'" in text
    assert "- Reason: flaky CI, checked by hand" in text


def test_normal_approval_writes_no_decision(ws):
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    advance_task(store, workflow, TaskEvent.PASS, clock)
    assert approve_task(store, workflow, paths.dir, clock).decision_file is None
    assert [p.name for p in (paths.dir / "decisions").iterdir()] == [".gitkeep"]


def test_cancel_clears_active_task(ws):
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    assert cancel_task(store, workflow, clock).status is TaskStatus.CANCELLED
    assert store.load().active_task_id is None


def test_write_report(ws):
    paths, workflow, store, client = ws
    task = new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    path = write_report(paths.dir, workflow, task, "confirm", "# Confirm\r\n\r\nAll good")
    assert path == paths.dir / "tasks" / "T-001" / "reports" / "confirm.md"
    assert path.read_bytes() == b"# Confirm\n\nAll good\n"
    write_report(paths.dir, workflow, task, "confirm", "second\n")
    assert path.read_text(encoding="utf-8") == "second\n"


@pytest.mark.parametrize(("step", "content", "code"), [("ghost", "x", ExitCode.UNKNOWN_STEP), ("confirm", " \n", ExitCode.INVALID_INPUT)])
def test_write_report_rejects(ws, step, content, code):
    paths, workflow, store, client = ws
    task = new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    with pytest.raises(AgentflowError) as exc:
        write_report(paths.dir, workflow, task, step, content)
    assert exc.value.code is code


def test_a_report_can_only_be_written_for_the_current_step(ws):
    paths, workflow, store, client = ws
    task = new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    for other in ("build", "check"):
        with pytest.raises(AgentflowError) as exc:
            write_report(paths.dir, workflow, task, other, "x")
        assert exc.value.code is ExitCode.REPORT_REFUSED and "confirm" in str(exc.value)
    assert not (paths.dir / "tasks" / "T-001" / "reports").exists()


def test_a_report_of_a_step_that_passed_is_final(ws):
    paths, workflow, store, client = ws
    task = new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    write_report(paths.dir, workflow, task, "confirm", "the confirmation")
    task = advance_task(store, workflow, TaskEvent.PASS, clock)  # confirm needs approval: awaiting_approval
    with pytest.raises(AgentflowError) as exc:
        write_report(paths.dir, workflow, task, "confirm", "rewritten after the pass")
    assert exc.value.code is ExitCode.REPORT_REFUSED
    assert (paths.dir / "tasks" / "T-001" / "reports" / "confirm.md").read_text(encoding="utf-8") == "the confirmation\n"
    task = approve_task(store, workflow, paths.dir, clock).task  # now at build
    with pytest.raises(AgentflowError) as exc:
        write_report(paths.dir, workflow, task, "confirm", "still final")
    assert exc.value.code is ExitCode.REPORT_REFUSED
    assert write_report(paths.dir, workflow, task, "build", "fine").name == "build.md"


def test_no_report_for_a_task_that_is_not_open(ws):
    paths, workflow, store, client = ws
    new_task(store, workflow, client, "t", TaskType.FEATURE, clock)
    task = cancel_task(store, workflow, clock)
    with pytest.raises(AgentflowError) as exc:
        write_report(paths.dir, workflow, task, "confirm", "x")
    assert exc.value.code is ExitCode.REPORT_REFUSED


def test_require_active_task():
    with pytest.raises(AgentflowError) as exc:
        require_active_task(State())
    assert exc.value.code is ExitCode.NO_ACTIVE_TASK
