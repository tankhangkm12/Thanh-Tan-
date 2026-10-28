import pytest

from thanhtan.cli import main
from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.knowledge import (
    SKELETON_DIRS,
    SKELETON_FILES,
    add_personal_convention,
    init_store,
    pull_files,
    push_file,
)
from thanhtan.userconfig import knowledge_dir, save_knowledge_dir


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "fake-home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


@pytest.fixture
def store(tmp_path):
    folder = tmp_path / "store"
    init_store(folder)
    return folder


@pytest.fixture
def workspace(tmp_path):
    folder = tmp_path / "project" / ".ThanhTan"
    (folder / "knowledge").mkdir(parents=True)
    (folder / "tasks" / "T-001" / "lessons").mkdir(parents=True)
    return folder


def refuses(call, code=None):
    with pytest.raises(ThanhTanError) as exc:
        call()
    if code is not None:
        assert exc.value.code is code
    return str(exc.value)


# ------------------------------------------------------------ user config


def test_the_default_store_is_knowledge_in_the_home_folder(home):
    assert knowledge_dir() == home / "knowledge"


def test_the_store_path_comes_from_the_user_config(home, tmp_path):
    save_knowledge_dir(tmp_path / "elsewhere")
    assert knowledge_dir() == tmp_path / "elsewhere"


# -------------------------------------------------------------------- init


def test_init_creates_the_skeleton(tmp_path):
    created = init_store(tmp_path / "kb")
    for name in SKELETON_FILES:
        assert (tmp_path / "kb" / name).is_file()
    for name in SKELETON_DIRS:
        assert (tmp_path / "kb" / name).is_dir()
    assert {"index.md", "conventions.md", "sources.md"} <= set(SKELETON_FILES) and {"lessons", "patterns", "semgrep"} <= set(SKELETON_DIRS)
    assert created and init_store(tmp_path / "kb") == []  # a second run adds nothing


def test_init_never_overwrites_what_the_person_wrote(tmp_path):
    init_store(tmp_path / "kb")
    (tmp_path / "kb" / "conventions.md").write_text("### KC-01 - mine\n", encoding="utf-8")
    init_store(tmp_path / "kb")
    assert (tmp_path / "kb" / "conventions.md").read_text(encoding="utf-8") == "### KC-01 - mine\n"


def test_init_command_records_the_folder(tmp_path, capsys):
    target = tmp_path / "my-kb"
    assert main(["knowledge", "init", "--dir", str(target)]) == ExitCode.OK
    assert (target / "index.md").is_file() and knowledge_dir() == target
    assert "knowledge store" in capsys.readouterr().out


# -------------------------------------------------------------------- pull


def test_pull_copies_chosen_files_keeping_their_place(store, workspace):
    (store / "lessons" / "retries.md").write_text("back off", encoding="utf-8")
    (store / "semgrep" / "no-literals.yaml").write_text("rules: []", encoding="utf-8")
    copied = pull_files(store, workspace, ["lessons/retries.md", str(store / "semgrep" / "no-literals.yaml")])
    assert [path.relative_to(workspace / "knowledge").as_posix() for path in copied] == ["lessons/retries.md", "semgrep/no-literals.yaml"]
    assert (workspace / "knowledge" / "lessons" / "retries.md").read_text(encoding="utf-8") == "back off"


@pytest.mark.parametrize("name", ["../outside.md", "lessons/../../outside.md", "missing.md", "lessons", "C:/Windows/win.ini", "/etc/hosts"])
def test_pull_refuses_anything_outside_the_store_or_missing(store, workspace, tmp_path, name):
    (tmp_path / "outside.md").write_text("secret", encoding="utf-8")
    refuses(lambda: pull_files(store, workspace, [name]))
    assert not list((workspace / "knowledge").rglob("*.md"))


def test_pull_stops_before_copying_when_one_file_is_wrong(store, workspace):
    (store / "lessons" / "a.md").write_text("a", encoding="utf-8")
    refuses(lambda: pull_files(store, workspace, ["lessons/a.md", "nope.md"]))
    assert not (workspace / "knowledge" / "lessons" / "a.md").exists()


def test_pull_needs_an_initialised_store(tmp_path, workspace):
    assert "knowledge init" in refuses(lambda: pull_files(tmp_path / "nothing", workspace, ["a.md"]))


# -------------------------------------------------------------------- push


def lesson(workspace, name="L1.md", text="# Retry\nback off\n"):
    path = workspace / "tasks" / "T-001" / "lessons" / name
    path.write_text(text, encoding="utf-8")
    return path


def test_push_copies_a_workspace_file_into_the_store(store, workspace):
    target = push_file(store, workspace, lesson(workspace), "lessons")
    assert target == store / "lessons" / "L1.md" and target.read_text(encoding="utf-8") == "# Retry\nback off\n"


def test_push_can_file_under_patterns_and_keeps_existing_files(store, workspace):
    push_file(store, workspace, lesson(workspace), "patterns")
    assert (store / "patterns" / "L1.md").is_file()
    refuses(lambda: push_file(store, workspace, lesson(workspace, text="other"), "patterns"), ExitCode.INVALID_INPUT)
    assert (store / "patterns" / "L1.md").read_text(encoding="utf-8") == "# Retry\nback off\n"


def test_push_takes_only_files_from_the_workspace(store, workspace, tmp_path):
    outside = tmp_path / "project" / "secrets.md"
    outside.write_text("x", encoding="utf-8")
    refuses(lambda: push_file(store, workspace, outside, "lessons"), ExitCode.INVALID_INPUT)
    refuses(lambda: push_file(store, workspace, workspace / "tasks" / "missing.md", "lessons"), ExitCode.INVALID_INPUT)
    assert not list((store / "lessons").glob("*.md"))


def test_push_refuses_an_unknown_place(store, workspace):
    refuses(lambda: push_file(store, workspace, lesson(workspace), "semgrep"), ExitCode.INVALID_INPUT)


# ----------------------------------------------------- personal conventions


def test_add_personal_convention_continues_the_numbering(store):
    first = add_personal_convention(store, "Small commits", "review", None, "Commit small.", "answer to Q1 of T-001")
    second = add_personal_convention(store, "Interface first", "plan", "item-order", "Interfaces first.", "answer to Q2 of T-001")
    assert (first, second) == ("KC-01", "KC-02")
    text = (store / "conventions.md").read_text(encoding="utf-8")
    assert "### KC-02 - Interface first" in text and "- rule: item-order" in text and "- source: answer to Q2 of T-001" in text


# ------------------------------------------------------------------ the CLI


@pytest.fixture
def project(gitflow_repo, workflow_file, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(workflow_file)]) == ExitCode.OK
    target = tmp_path / "kb"
    assert main(["knowledge", "init", "--dir", str(target)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo, target


def test_pull_and_push_through_the_cli(project, capsys):
    repo, kb = project
    (kb / "lessons" / "x.md").write_text("learned", encoding="utf-8")
    assert main(["knowledge", "pull", "lessons/x.md"]) == ExitCode.OK
    assert (repo / ".ThanhTan" / "knowledge" / "lessons" / "x.md").read_text(encoding="utf-8") == "learned"
    mine = repo / ".ThanhTan" / "tasks" / "note.md"
    mine.parent.mkdir(exist_ok=True)
    mine.write_text("note", encoding="utf-8")
    assert main(["knowledge", "push", str(mine)]) == ExitCode.OK
    assert (kb / "lessons" / "note.md").read_text(encoding="utf-8") == "note"
    assert main(["knowledge", "push", str(mine), "--as", "patterns"]) == ExitCode.OK
    assert (kb / "patterns" / "note.md").is_file()
    capsys.readouterr()
    assert main(["knowledge", "pull", "../nope.md"]) == ExitCode.INVALID_INPUT
