"""Phase B left a few branches without a test; this file covers them (they ship in phase C's commit).

- `keep_previous`: two versions replaced in the same second must both survive in `project/history/`.
- `project_write` of the conventions: what an agent can and cannot make of a convention.
- `roadmap.describe` and `roadmap.next_item`, used by `thanhtan status`, outside the command line.

All of it describes behaviour that already exists: these tests are green. The mutation check in the report shows they
fail when the code they cover is broken.
"""

import pytest
from sdd_helpers import init_workspace, project_dir, sample_workflow

from thanhtan.confirmations import Confirmations
from thanhtan.constants import ExitCode, ProjectSection, RoadmapStatus
from thanhtan.errors import ThanhTanError
from thanhtan.project import keep_previous
from thanhtan.roadmap import RoadmapItem, describe, next_item, unconfirmed_codes
from thanhtan.services import WorkspaceServices
from thanhtan.workspace import find_workspace

STAMP = "2026-10-17T10:00:00Z"
CONVENTIONS = """# Quy ước

### PC-01 - Constants
- check: review
- status: unconfirmed
- source: src/constants.py (inferred from code)
- description: Fixed values live in constants or enums.

### PC-02 - Interface first
- check: plan
- rule: item-order
- status: unconfirmed
- source: docs/CONTRIBUTING.md:12
- description: Interfaces come before implementations.

## Câu hỏi mở

### S1 - pytest or unittest?
- docs: docs/testing.md:5
- code: Makefile:14
"""


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    return init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)


@pytest.fixture
def service(ws):
    return WorkspaceServices(find_workspace(ws))


def conventions_file(ws):
    return project_dir(ws) / "conventions.md"


def history(ws, name):
    folder = project_dir(ws) / "history"
    return sorted(folder.glob(f"{name}-*.md")) if folder.is_dir() else []


def refused(service, text):
    with pytest.raises(ThanhTanError) as exc:
        service.write_project(ProjectSection.CONVENTIONS, text)
    return exc.value


# --------------------------------------------------------------- keep_previous


def test_two_versions_saved_in_the_same_second_both_survive(tmp_path, monkeypatch):
    monkeypatch.setattr("thanhtan.project.utc_now", lambda: STAMP)
    paths = [keep_previous(tmp_path, "profile", text) for text in ("one", "two", "three")]
    assert len(set(paths)) == 3
    assert [path.read_text(encoding="utf-8") for path in paths] == ["one", "two", "three"]
    assert len(list((tmp_path / "project" / "history").glob("profile-*.md"))) == 3


def test_the_first_version_of_a_second_keeps_the_plain_name(tmp_path, monkeypatch):
    monkeypatch.setattr("thanhtan.project.utc_now", lambda: STAMP)
    first = keep_previous(tmp_path, "profile", "one")
    second = keep_previous(tmp_path, "profile", "two")
    assert first.name == "profile-20261017T100000Z.md" and second.name != first.name


def test_versions_of_different_documents_never_collide(tmp_path, monkeypatch):
    monkeypatch.setattr("thanhtan.project.utc_now", lambda: STAMP)
    a = keep_previous(tmp_path, "profile", "p")
    b = keep_previous(tmp_path, "roadmap", "r")
    assert a.read_text(encoding="utf-8") == "p" and b.read_text(encoding="utf-8") == "r"


def test_rewriting_a_document_twice_in_one_second_keeps_both_older_versions(ws, service, monkeypatch):
    monkeypatch.setattr("thanhtan.project.utc_now", lambda: STAMP)
    for text in ("# Profile v1\n", "# Profile v2\n", "# Profile v3\n"):
        service.write_project(ProjectSection.PROFILE, text)
    assert (project_dir(ws) / "profile.md").read_text(encoding="utf-8") == "# Profile v3\n"
    assert sorted(path.read_text(encoding="utf-8") for path in history(ws, "profile")) == ["# Profile v1\n", "# Profile v2\n"]


def test_writing_the_same_text_again_keeps_no_history(ws, service):
    service.write_project(ProjectSection.PROFILE, "# Profile\n")
    service.write_project(ProjectSection.PROFILE, "# Profile\n")
    assert history(ws, "profile") == []


# ------------------------------------------------- project_write of the conventions


def test_conventions_are_stored_and_counted(ws, service):
    info = service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    assert (info.conventions, info.open_questions) == (2, 1)
    text = conventions_file(ws).read_text(encoding="utf-8")
    assert "### PC-01 - Constants" in text and "### S1 - pytest or unittest?" in text


def test_a_convention_an_agent_writes_as_confirmed_is_stored_as_unconfirmed(ws, service):
    info = service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS.replace("status: unconfirmed", "status: confirmed", 1))
    assert info.demoted == ("PC-01",)
    assert "- status: confirmed" not in conventions_file(ws).read_text(encoding="utf-8")


def test_a_plain_new_convention_is_not_reported_as_demoted(ws, service):
    assert service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS).demoted == ()


def confirm_first(ws, monkeypatch=None):
    path = conventions_file(ws)
    path.write_text(path.read_text(encoding="utf-8").replace("status: unconfirmed", "status: confirmed", 1), encoding="utf-8")


def test_a_confirmed_convention_written_back_unchanged_stays_confirmed(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_first(ws)
    info = service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    assert info.demoted == ()
    assert "- status: confirmed" in conventions_file(ws).read_text(encoding="utf-8")


def test_a_confirmed_convention_that_an_agent_changed_goes_back_to_unconfirmed(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_first(ws)
    changed = CONVENTIONS.replace("Fixed values live in constants or enums.", "Fixed values live in one module.")
    info = service.write_project(ProjectSection.CONVENTIONS, changed)
    assert info.demoted == ("PC-01",)
    assert "- status: confirmed" not in conventions_file(ws).read_text(encoding="utf-8")


def test_a_confirmed_convention_cannot_be_left_out(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_first(ws)
    before = conventions_file(ws).read_text(encoding="utf-8")
    without = CONVENTIONS.split("### PC-01")[0] + "### PC-02" + CONVENTIONS.split("### PC-02")[1]
    error = refused(service, without)
    assert int(error.code) == ExitCode.PROJECT_WRITE_REFUSED and "PC-01" in str(error)
    assert conventions_file(ws).read_text(encoding="utf-8") == before


def test_an_unconfirmed_convention_can_be_left_out(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    without = CONVENTIONS.split("### PC-02")[0].rstrip() + "\n"
    assert service.write_project(ProjectSection.CONVENTIONS, without).conventions == 1


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (CONVENTIONS.replace("- check: review\n", ""), "check"),
        (CONVENTIONS.replace("- source: src/constants.py (inferred from code)\n", ""), "source"),
        (CONVENTIONS.replace("- description: Fixed values live in constants or enums.\n", ""), "description"),
        (CONVENTIONS.replace("## Câu hỏi mở", "### PC-01 - Again\n- check: review\n- source: x\n- description: y\n\n## Câu hỏi mở"), "duplicate"),
        (CONVENTIONS.replace("- rule: item-order", "- rule: made-up"), "rule"),
    ],
    ids=["no check", "no source", "no description", "duplicate code", "unknown plan rule"],
)
def test_conventions_that_break_the_format_are_refused_and_the_old_file_stays(ws, service, text, problem):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    before = conventions_file(ws).read_text(encoding="utf-8")
    error = refused(service, text)
    assert int(error.code) == ExitCode.CONVENTIONS_INVALID and problem in str(error)
    assert conventions_file(ws).read_text(encoding="utf-8") == before


def test_conventions_that_changed_are_kept_in_the_history(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS.replace("Interfaces come before", "Interfaces always come before"))
    assert len(history(ws, "conventions")) == 1


def test_windows_line_ends_are_stored_as_unix_line_ends(ws, service):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS.replace("\n", "\r\n"))
    assert b"\r" not in conventions_file(ws).read_bytes()


def test_conventions_are_not_written_while_a_task_is_open(ws, service, monkeypatch):
    from thanhtan.cli import main

    assert main(["task", "new", "t"]) == ExitCode.OK
    error = refused(service, CONVENTIONS)
    assert int(error.code) == ExitCode.PROJECT_WRITE_REFUSED
    assert not conventions_file(ws).exists()


# ------------------------------------------------------ describe and next_item


def item(code, status="todo", title="Mục"):
    return RoadmapItem(code, title, RoadmapStatus(status), "một mục tiêu", "không có — chưa có")


def test_a_confirmed_item_is_described_by_its_label_alone(tmp_path):
    confirmations = Confirmations(tmp_path)
    one = item("R1", title="Đặt món")
    confirmations.confirm("R1", one.content)
    assert describe(one, confirmations) == "R1 - Đặt món"


def test_an_item_nobody_confirmed_says_so(tmp_path):
    assert describe(item("R1", title="Đặt món"), Confirmations(tmp_path)) == "R1 - Đặt món (unconfirmed)"


def test_moving_an_item_to_another_status_does_not_unconfirm_it(tmp_path):
    confirmations = Confirmations(tmp_path)
    confirmations.confirm("R1", item("R1", "todo").content)
    assert describe(item("R1", "doing"), confirmations) == "R1 - Mục"


def test_changing_the_goal_of_an_item_unconfirms_it(tmp_path):
    confirmations = Confirmations(tmp_path)
    confirmations.confirm("R1", item("R1").content)
    changed = RoadmapItem("R1", "Mục", RoadmapStatus.TODO, "một mục tiêu khác", "không có — chưa có")
    assert describe(changed, confirmations).endswith("(unconfirmed)")


def test_unconfirmed_codes_lists_what_nobody_confirmed_in_file_order(tmp_path):
    confirmations = Confirmations(tmp_path)
    items = [item("R1"), item("R2"), item("R3")]
    confirmations.confirm("R2", items[1].content)
    assert unconfirmed_codes(items, confirmations) == ["R1", "R3"]


def test_the_next_item_is_a_doing_item_without_a_task_before_any_todo_item():
    items = [item("R1", "todo"), item("R2", "doing"), item("R3", "doing")]
    assert next_item(items, set()).code == "R2"


def test_a_doing_item_with_an_open_task_is_passed_over_for_the_next_doing_item():
    items = [item("R1", "todo"), item("R2", "doing"), item("R3", "doing")]
    assert next_item(items, {"R2"}).code == "R3"


def test_when_every_doing_item_is_busy_the_first_todo_item_is_next():
    items = [item("R1", "done"), item("R2", "doing"), item("R3", "todo"), item("R4", "todo")]
    assert next_item(items, {"R2"}).code == "R3"


def test_a_busy_todo_item_is_passed_over_too():
    assert next_item([item("R1", "todo"), item("R2", "todo")], {"R1"}).code == "R2"


def test_done_and_dropped_items_are_never_next():
    assert next_item([item("R1", "done"), item("R2", "dropped")], set()) is None


def test_no_items_means_no_suggestion():
    assert next_item([], set()) is None


@pytest.mark.parametrize("busy", [set(), frozenset(), [], ("R9",), {"R9"}])
def test_the_busy_collection_may_be_any_collection_and_may_name_codes_that_are_not_there(busy):
    assert next_item([item("R1", "todo")], busy).code == "R1"
