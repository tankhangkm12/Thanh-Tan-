import hashlib
import subprocess

import pytest
import yaml
from conftest import write_workflow

from agentflow.constants import ExitCode, StepStatus, TaskStatus
from agentflow.errors import AgentflowError
from agentflow.models import State, Task
from agentflow.state import JsonStateStore
from agentflow.workspace import (
    WorkspacePaths,
    ensure_excluded,
    find_workspace,
    git_exclude_file,
    init_workspace,
    load_config,
    load_workspace_workflow,
)


def git_status(repo):
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def test_init_creates_full_tree(git_repo, workflow_file):
    result = init_workspace(git_repo, workflow_file)
    ws = result.paths.dir
    for name in ["state.json", "STATE.md", "config.yaml", "workflow.yaml"]:
        assert (ws / name).is_file(), name
    for name in ["decisions", "tasks", "project", "knowledge"]:
        assert (ws / name / ".gitkeep").is_file(), name
    assert (ws / "workflow.yaml").read_bytes() == workflow_file.read_bytes()
    assert result.workflow_copied and result.exclude_added
    assert ".ThanhTan/state.json" in result.created


def test_init_keeps_workspace_out_of_git(git_repo, workflow_file):
    init_workspace(git_repo, workflow_file)
    assert git_status(git_repo) == ""
    exclude = git_exclude_file(git_repo).read_text(encoding="utf-8")
    assert exclude.splitlines().count(".ThanhTan/") == 1
    assert not (git_repo / ".gitignore").exists()


def test_config_records_source_and_sha(git_repo, workflow_file):
    paths = init_workspace(git_repo, workflow_file).paths
    config = load_config(paths)
    assert config.workflow.family == "sample"
    assert config.workflow.source_path == str(workflow_file.resolve())
    assert config.workflow.sha256 == hashlib.sha256(workflow_file.read_bytes()).hexdigest()


def test_init_from_subdirectory_uses_repo_root(git_repo, workflow_file):
    sub = git_repo / "src" / "deep"
    sub.mkdir(parents=True)
    paths = init_workspace(sub, workflow_file).paths
    assert paths.root.samefile(git_repo)


def test_init_outside_git_fails_and_writes_nothing(tmp_path, workflow_file):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(AgentflowError) as exc:
        init_workspace(plain, workflow_file)
    assert exc.value.code is ExitCode.NOT_GIT_REPO
    assert not (plain / ".ThanhTan").exists()


def test_invalid_workflow_fails_before_writing(git_repo, tmp_path, workflow_data):
    del workflow_data["family"]
    bad = write_workflow(tmp_path / "bad" / "workflow.yaml", workflow_data)
    with pytest.raises(AgentflowError) as exc:
        init_workspace(git_repo, bad)
    assert exc.value.code is ExitCode.INVALID_WORKFLOW
    assert not (git_repo / ".ThanhTan").exists()


def test_rerun_preserves_state_and_copy(git_repo, workflow_file, workflow_data):
    paths = init_workspace(git_repo, workflow_file).paths
    store = JsonStateStore(paths.dir, load_workspace_workflow(paths))
    task = Task("T-001", "keep me", TaskStatus.OPEN, "build", StepStatus.IN_PROGRESS, branch="feature/x")
    saved = store.save(State(active_task_id="T-001", tasks=(task,)))
    copy_before = paths.workflow_copy.read_bytes()

    workflow_data["steps"][1]["name"] = "Build (changed upstream)"
    write_workflow(workflow_file, workflow_data)
    result = init_workspace(git_repo, workflow_file)

    assert result.created == ()
    assert not result.exclude_added and not result.workflow_copied
    assert store.load() == saved
    assert paths.workflow_copy.read_bytes() == copy_before
    assert git_exclude_file(git_repo).read_text(encoding="utf-8").splitlines().count(".ThanhTan/") == 1


def test_rerun_restores_deleted_files(git_repo, workflow_file):
    paths = init_workspace(git_repo, workflow_file).paths
    paths.state_md.unlink()
    (paths.dir / "tasks" / ".gitkeep").unlink()
    result = init_workspace(git_repo, workflow_file)
    assert ".ThanhTan/STATE.md" in result.created
    assert paths.state_md.is_file()
    assert (paths.dir / "tasks" / ".gitkeep").is_file()


def test_rerun_with_other_family_is_refused(git_repo, workflow_file, tmp_path, workflow_data):
    paths = init_workspace(git_repo, workflow_file).paths
    config_before = paths.config.read_bytes()
    workflow_data["family"] = "other"
    other = write_workflow(tmp_path / "other" / "workflow.yaml", workflow_data)
    with pytest.raises(AgentflowError) as exc:
        init_workspace(git_repo, other)
    assert exc.value.code is ExitCode.WORKFLOW_MISMATCH
    assert paths.config.read_bytes() == config_before


def test_rerun_with_new_location_updates_source_path(git_repo, workflow_file, tmp_path, workflow_data):
    paths = init_workspace(git_repo, workflow_file).paths
    moved = write_workflow(tmp_path / "plugin-v2" / "workflow.yaml", workflow_data)
    init_workspace(git_repo, moved)
    assert load_config(paths).workflow.source_path == str(moved.resolve())


def test_ensure_excluded_respects_existing_forms(tmp_path):
    exclude = tmp_path / "info" / "exclude"
    exclude.parent.mkdir()
    exclude.write_text("# comment\n/.ThanhTan", encoding="utf-8")
    assert ensure_excluded(exclude) is False
    exclude.write_text("*.log", encoding="utf-8")  # no trailing newline
    assert ensure_excluded(exclude) is True
    assert exclude.read_text(encoding="utf-8") == "*.log\n.ThanhTan/\n"


def test_find_workspace(git_repo, workflow_file):
    with pytest.raises(AgentflowError) as exc:
        find_workspace(git_repo)
    assert exc.value.code is ExitCode.NO_WORKSPACE
    init_workspace(git_repo, workflow_file)
    assert find_workspace(git_repo).root.samefile(git_repo)


def test_config_file_is_plain_yaml(git_repo, workflow_file):
    paths: WorkspacePaths = init_workspace(git_repo, workflow_file).paths
    data = yaml.safe_load(paths.config.read_text(encoding="utf-8"))
    assert set(data) == {"schema_version", "workflow"}
