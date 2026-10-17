"""Phase B2: `.agentflow/project/roadmap.md`, the project's list of goals (R1, R2, ...).

Each item is `### R<n> - title` with `- status: todo|doing|done|dropped`, `- goal:` and `- docs:`. An agent proposes the
list through the `project_write` tool (section `roadmap`); only a person confirms items (`project confirm R1`) or changes
a status (`agentflow roadmap set R4 dropped`). The order of the file is the order of priority.
"""

import json

import pytest
from mcp_helpers import call
from sdd_helpers import PROJECT_WRITE_REFUSED, ROADMAP, ROADMAP_INVALID, init_workspace, project_dir, roadmap_text, run, sample_workflow, statuses

from agentflow.constants import CliKind, ExitCode, GuardDecision, GuardRule, HookEvent
from agentflow.errors import AgentflowError
from agentflow.git import GitBranchLookup
from agentflow.guard import evaluate
from agentflow.hook import handle_hook
from agentflow.mcp_server import build_server
from agentflow.services import WorkspaceServices
from agentflow.workspace import find_workspace

# Spelled as a string so these tests do not need the ProjectSection member that phase B adds.
SECTION = "roadmap"


@pytest.fixture
def ws(gitflow_repo, tmp_path, monkeypatch, capsys):
    return init_workspace(gitflow_repo, sample_workflow(tmp_path), monkeypatch, capsys)


@pytest.fixture
def service(ws):
    return WorkspaceServices(find_workspace(ws))


def write(service, text=ROADMAP):
    return service.write_project(SECTION, text)


def refuses(service, text, code):
    with pytest.raises(AgentflowError) as exc:
        write(service, text)
    assert int(exc.value.code) == code, str(exc.value)
    return str(exc.value)


def item(code, title="Mục", status=None, goal="Một mục tiêu.", docs="không có — chưa có", extra=""):
    lines = [f"### {code} - {title}"]
    if status:
        lines.append(f"- status: {status}")
    if goal is not None:
        lines.append(f"- goal: {goal}")
    if docs is not None:
        lines.append(f"- docs: {docs}")
    return "\n".join(lines) + ("\n" + extra.rstrip("\n") if extra else "") + "\n"


def roadmap(*items):
    return "# Roadmap\n\n" + "\n".join(items)


# --------------------------------------------------------------- the format


def test_a_valid_roadmap_is_stored_with_a_status_on_every_item(service, ws):
    write(service, roadmap(item("R1", "Một"), item("R2", "Hai", docs="https://example.com/x")))
    assert statuses(ws) == {"R1": "todo", "R2": "todo"}
    text = roadmap_text(ws)
    assert "### R1 - Một" in text and "- goal: Một mục tiêu." in text and "https://example.com/x" in text


def test_the_order_of_the_file_is_kept(service, ws):
    """Regression for the new parser: it must not sort the items."""
    write(service, roadmap(item("R3", "C"), item("R1", "A"), item("R2", "B")))
    assert list(statuses(ws)) == ["R3", "R1", "R2"]


REFUSED = {
    "no items": "# Roadmap\n\nNothing yet.\n",
    "a duplicate code": roadmap(item("R1"), item("R1")),
    "a code that is not R and digits": roadmap(item("R1x")),
    "a lower case code": roadmap(item("r1")),
    "a heading without a title": roadmap("### R1\n- goal: g\n- docs: không có — x\n"),
    "a missing goal": roadmap(item("R1", goal=None)),
    "an empty goal": roadmap(item("R1", goal="")),
    "missing docs": roadmap(item("R1", docs=None)),
    "an unknown field": roadmap(item("R1", extra="- confirmed: yes\n")),
    "an unknown status": roadmap(item("R1", status="finished")),
    "docs that are neither a link, a file:line nor 'không có'": roadmap(item("R1", docs="maybe later")),
}


@pytest.mark.parametrize("text", REFUSED.values(), ids=REFUSED.keys())
def test_a_roadmap_that_breaks_the_format_is_refused_and_the_old_one_stays(service, ws, text):
    write(service)
    before = roadmap_text(ws)
    refuses(service, text, ROADMAP_INVALID)
    assert roadmap_text(ws) == before


def test_a_refused_roadmap_names_what_is_wrong(service):
    message = refuses(service, roadmap(item("R1"), item("R1"), item("R2", goal=None)), ROADMAP_INVALID)
    assert "R1" in message and "R2" in message


def test_nothing_is_written_while_a_task_is_open(service, ws, capsys):
    """Regression: green before phase B (the rule already covers every project section)."""
    run(capsys, "task", "new", "t")
    refuses(service, ROADMAP, PROJECT_WRITE_REFUSED)
    assert not (project_dir(ws) / "roadmap.md").exists()


# ------------------------------------------------- what an agent may not decide


def test_a_new_item_is_always_todo_and_the_agent_is_told(service, ws):
    info = write(service, roadmap(item("R1", status="done"), item("R2", status="doing")))
    assert statuses(ws) == {"R1": "todo", "R2": "todo"}
    assert any("R1" in w for w in info.warnings) and any("R2" in w for w in info.warnings)


def test_the_status_of_an_item_that_exists_is_kept_whatever_the_agent_writes(service, ws, capsys):
    write(service)
    run(capsys, "roadmap", "set", "R1", "doing")
    info = write(service, ROADMAP.replace("### R1 - Đặt món\n- status: todo", "### R1 - Đặt món\n- status: done"))
    assert statuses(ws)["R1"] == "doing"
    assert any("R1" in w for w in info.warnings)


def test_an_item_without_a_status_line_keeps_its_current_status(service, ws, capsys):
    write(service)
    run(capsys, "roadmap", "set", "R2", "dropped")
    write(service, roadmap(item("R1", "Đặt món"), item("R2", "Thanh toán"), item("R3", "Báo bếp")))
    assert statuses(ws) == {"R1": "todo", "R2": "dropped", "R3": "todo"}


def test_an_unconfirmed_todo_item_may_be_left_out_freely(service, ws):
    write(service)
    info = write(service, ROADMAP.split("### R3")[0])
    assert list(statuses(ws)) == ["R1", "R2"]
    assert info.warnings == ()


def confirmed_roadmap(service, capsys, *codes):
    write(service)
    assert run(capsys, "project", "confirm", *codes)[0] == ExitCode.OK


def test_a_confirmed_todo_item_may_still_be_left_out_but_the_agent_is_told(service, ws, capsys):
    confirmed_roadmap(service, capsys, "R1", "R2", "R3")
    info = write(service, ROADMAP.split("### R3")[0])
    assert list(statuses(ws)) == ["R1", "R2"]
    assert any("R3" in warning and "confirmed" in warning for warning in info.warnings), info.warnings
    assert not any("R1" in warning or "R2" in warning for warning in info.warnings)


def test_the_removal_of_a_confirmed_item_is_kept_in_the_history(service, ws, capsys):
    confirmed_roadmap(service, capsys, "R3")
    before = roadmap_text(ws)
    write(service, ROADMAP.split("### R3")[0])
    kept = snapshots(ws, "roadmap")
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == before and "### R3 - Báo bếp" in before


def test_the_project_status_shows_a_confirmed_item_that_was_removed(service, ws, capsys):
    confirmed_roadmap(service, capsys, "R2", "R3")
    write(service, roadmap(item("R1", "Đặt món", goal="Khách đặt được món từ điện thoại.", docs="docs/vision.md:10")))
    _, out, _ = run(capsys, "project", "status")
    assert "removed: R2 (confirmed)" in out.splitlines() and "removed: R3 (confirmed)" in out.splitlines()


def test_an_unconfirmed_item_that_was_removed_leaves_no_trace_in_the_status(service, ws, capsys):
    write(service)
    write(service, ROADMAP.split("### R3")[0])
    _, out, _ = run(capsys, "project", "status")
    assert "removed:" not in out


def test_putting_a_removed_item_back_clears_the_note_and_the_old_confirmation(service, ws, capsys):
    confirmed_roadmap(service, capsys, "R3")
    write(service, ROADMAP.split("### R3")[0])
    write(service)
    _, out, _ = run(capsys, "project", "status")
    assert "removed:" not in out and "roadmap: unconfirmed (R1, R2, R3)" in out


def test_the_note_about_a_removed_item_survives_other_rewrites(service, ws, capsys):
    confirmed_roadmap(service, capsys, "R3")
    write(service, ROADMAP.split("### R3")[0])
    write(service, ROADMAP.split("### R3")[0].replace("Trả tiền bằng thẻ.", "Trả tiền bằng thẻ hoặc ví."))
    _, out, _ = run(capsys, "project", "status")
    assert "removed: R3 (confirmed)" in out.splitlines()


@pytest.mark.parametrize("status", ["doing", "done", "dropped"])
def test_a_confirmed_item_that_has_moved_on_still_cannot_be_left_out(service, ws, capsys, status):
    confirmed_roadmap(service, capsys, "R3")
    run(capsys, "roadmap", "set", "R3", status)
    before = roadmap_text(ws)
    refuses(service, ROADMAP.split("### R3")[0], PROJECT_WRITE_REFUSED)
    assert roadmap_text(ws) == before


@pytest.mark.parametrize("status", ["doing", "done", "dropped"])
def test_an_item_that_has_moved_on_cannot_be_left_out(service, ws, capsys, status):
    write(service)
    run(capsys, "roadmap", "set", "R3", status)
    before = roadmap_text(ws)
    message = refuses(service, roadmap(item("R1", "Đặt món"), item("R2", "Thanh toán")), PROJECT_WRITE_REFUSED)
    assert "R3" in message and roadmap_text(ws) == before


def test_an_agent_cannot_make_an_item_confirmed_by_any_text(service, ws, capsys):
    write(service)
    refuses(service, roadmap(item("R1", extra="- confirmed: yes\n")), ROADMAP_INVALID)
    code, out, _ = run(capsys, "project", "status")
    assert "roadmap: unconfirmed" in out


# ------------------------------------------------------------- confirmation


def test_items_are_confirmed_one_by_one(service, ws, capsys):
    write(service)
    code, out, _ = run(capsys, "project", "confirm", "R1")
    assert code == ExitCode.OK and "confirmed: R1" in out
    _, out, _ = run(capsys, "roadmap", "list")
    lines = {line.split()[0]: line for line in out.splitlines() if line.startswith("R")}
    assert "unconfirmed" not in lines["R1"] and "unconfirmed" in lines["R2"] and "unconfirmed" in lines["R3"]


def test_the_project_status_names_the_unconfirmed_items(service, ws, capsys):
    write(service)
    run(capsys, "project", "confirm", "R1")
    _, out, _ = run(capsys, "project", "status")
    line = next(line for line in out.splitlines() if line.startswith("roadmap: "))
    assert line.startswith("roadmap: unconfirmed") and "R2" in line and "R3" in line and "R1" not in line
    run(capsys, "project", "confirm", "R2", "R3")
    _, out, _ = run(capsys, "project", "status")
    assert "roadmap: confirmed" in out


def test_confirming_an_item_that_does_not_exist_changes_nothing(service, ws, capsys):
    write(service)
    code, _, err = run(capsys, "project", "confirm", "R1", "R9")
    assert code == 22 and "R9" in err
    _, out, _ = run(capsys, "project", "status")
    assert "roadmap: unconfirmed (R1, R2, R3)" in out


def test_a_rewrite_with_the_same_content_keeps_the_confirmation(service, ws, capsys):
    write(service)
    run(capsys, "project", "confirm", "R1", "R2")
    write(service)
    _, out, _ = run(capsys, "roadmap", "list")
    assert "unconfirmed" not in next(l for l in out.splitlines() if l.startswith("R1"))


def test_changing_the_goal_of_one_item_unconfirms_only_that_item(service, ws, capsys):
    write(service)
    run(capsys, "project", "confirm", "R1", "R2")
    write(service, ROADMAP.replace("Trả tiền bằng thẻ.", "Trả tiền bằng thẻ hoặc ví."))
    _, out, _ = run(capsys, "roadmap", "list")
    lines = {line.split()[0]: line for line in out.splitlines() if line.startswith("R")}
    assert "unconfirmed" not in lines["R1"] and "unconfirmed" in lines["R2"]


CHANGES = {
    "the title": ("### R2 - Thanh toán", "### R2 - Thanh toán online"),
    "the goal": ("- goal: Trả tiền bằng thẻ.", "- goal: Trả tiền bằng ví."),
    "the docs": ("- docs: không có — chưa có tài liệu", "- docs: https://example.com/pay"),
}


@pytest.mark.parametrize(("old", "new"), CHANGES.values(), ids=CHANGES.keys())
def test_any_change_to_the_content_of_a_confirmed_item_makes_it_unconfirmed_again(service, ws, capsys, old, new):
    confirmed_roadmap(service, capsys, "R1", "R2", "R3")
    assert old in ROADMAP
    write(service, ROADMAP.replace(old, new))
    _, out, _ = run(capsys, "project", "status")
    assert "roadmap: unconfirmed (R2)" in out.splitlines()


def test_reordering_the_items_keeps_their_confirmation(service, ws, capsys):
    write(service)
    run(capsys, "project", "confirm", "R1", "R2", "R3")
    write(service, roadmap(item("R3", "Báo bếp", goal="Bếp nhận đơn ngay khi khách trả tiền.", docs="https://example.com/kitchen-spec"),
                           item("R1", "Đặt món", goal="Khách đặt được món từ điện thoại.", docs="docs/vision.md:10"),
                           item("R2", "Thanh toán", goal="Trả tiền bằng thẻ.", docs="không có — chưa có tài liệu")))
    assert list(statuses(ws)) == ["R3", "R1", "R2"]
    _, out, _ = run(capsys, "project", "status")
    assert "roadmap: confirmed" in out


def test_a_status_change_by_a_person_does_not_unconfirm(service, ws, capsys):
    write(service)
    run(capsys, "project", "confirm", "R1")
    run(capsys, "roadmap", "set", "R1", "doing")
    _, out, _ = run(capsys, "roadmap", "list")
    line = next(l for l in out.splitlines() if l.startswith("R1"))
    assert "[doing]" in line and "unconfirmed" not in line


# ------------------------------------------------------------- the commands


def test_list_shows_code_status_and_title_in_file_order(service, ws, capsys):
    write(service)
    code, out, _ = run(capsys, "roadmap", "list")
    assert code == ExitCode.OK
    rows = [line for line in out.splitlines() if line.startswith("R")]
    assert [row.split()[0] for row in rows] == ["R1", "R2", "R3"]
    assert rows[0].startswith("R1 [todo] Đặt món") and "unconfirmed" in rows[0]


def test_list_without_a_roadmap_says_so(ws, capsys):
    code, out, _ = run(capsys, "roadmap", "list")
    assert code == ExitCode.OK and "no roadmap" in out


def test_set_changes_one_status_and_says_what_changed(service, ws, capsys):
    write(service)
    code, out, _ = run(capsys, "roadmap", "set", "R2", "dropped")
    assert code == ExitCode.OK and "R2: todo -> dropped" in out
    assert statuses(ws) == {"R1": "todo", "R2": "dropped", "R3": "todo"}


@pytest.mark.parametrize("status", ["todo", "doing", "done", "dropped"])
def test_set_accepts_each_status(service, ws, capsys, status):
    write(service)
    assert run(capsys, "roadmap", "set", "R1", status)[0] == ExitCode.OK
    assert statuses(ws)["R1"] == status


def test_set_refuses_an_unknown_item_and_an_unknown_status(service, ws, capsys):
    write(service)
    assert run(capsys, "roadmap", "set", "R9", "done")[0] == 22
    with pytest.raises(SystemExit) as exc:
        run(capsys, "roadmap", "set", "R1", "finished")
    assert exc.value.code == ExitCode.USAGE
    assert statuses(ws)["R1"] == "todo"


def test_set_without_a_roadmap_is_refused(ws, capsys):
    assert run(capsys, "roadmap", "set", "R1", "done")[0] == 22


def test_a_person_may_set_a_status_while_a_task_is_open(service, ws, capsys):
    write(service)
    run(capsys, "task", "new", "t")
    assert run(capsys, "roadmap", "set", "R3", "dropped")[0] == ExitCode.OK


# --------------------------------------------------------------------- history


def snapshots(ws, stem):
    folder = project_dir(ws) / "history"
    return sorted(folder.glob(f"{stem}-*.md")) if folder.is_dir() else []


def test_overwriting_a_project_document_keeps_the_previous_version(service, ws):
    write(service)
    assert snapshots(ws, "roadmap") == []
    first = roadmap_text(ws)
    write(service, ROADMAP.replace("Trả tiền bằng thẻ.", "Trả tiền bằng thẻ hoặc ví."))
    kept = snapshots(ws, "roadmap")
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == first
    write(service, ROADMAP.replace("Trả tiền bằng thẻ.", "Trả tiền bằng ví."))
    assert len(snapshots(ws, "roadmap")) == 2


def test_the_profile_is_kept_the_same_way(service, ws):
    service.write_project("profile", "# Profile v1\n")
    service.write_project("profile", "# Profile v2\n")
    kept = snapshots(ws, "profile")
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == "# Profile v1\n"


# --------------------------------------------------- guard, hook and the tool


class Workspaces:
    def __init__(self, root):
        self.root = root

    def has_workspace(self, directory):
        return directory == self.root


class OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


@pytest.mark.parametrize("command", ["agentflow roadmap set R1 done", "agentflow roadmap set R2 dropped", "cd . && agentflow roadmap set R1 doing"])
def test_changing_a_roadmap_status_is_a_persons_command(ws, command):
    verdict = evaluate(command, ws, OnFeature(), Workspaces(ws))
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.PERSON_ONLY


@pytest.mark.parametrize("command", ["agentflow project confirm R1", "agentflow project confirm mission R2"])
def test_confirming_roadmap_items_and_the_mission_stays_a_persons_command(ws, command):
    """Regression: `project confirm` was already for a person; the new codes must not open a way round it."""
    assert evaluate(command, ws, OnFeature(), Workspaces(ws)).rule is GuardRule.PERSON_ONLY


@pytest.mark.parametrize("command", ["agentflow roadmap list", "agentflow project status"])
def test_reading_the_roadmap_and_the_project_status_is_allowed(ws, command):
    """Regression: green before phase B; the new read commands must not be swept up with the person-only ones."""
    assert evaluate(command, ws, OnFeature(), Workspaces(ws)).decision is GuardDecision.ALLOW


def test_regression_the_file_tools_cannot_write_the_roadmap(ws):
    """Green before phase B (the whole workspace is protected); it must stay so for the new file."""
    target = str(project_dir(ws) / "roadmap.md")
    payload = json.dumps({"cwd": str(ws), "tool_name": "Write", "tool_input": {"file_path": target, "content": "x"}})
    out = json.loads(handle_hook(HookEvent.PRE_TOOL, CliKind.CLAUDE, payload, GitBranchLookup()))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_project_write_tool_accepts_the_roadmap_section_and_enforces_its_rules(ws):
    server = build_server(WorkspaceServices(find_workspace(ws)))
    ok = call(server, "project_write", section=SECTION, content=ROADMAP)
    assert not ok.is_error and statuses(ws) == {"R1": "todo", "R2": "todo", "R3": "todo"}
    bad = call(server, "project_write", section=SECTION, content=roadmap(item("R1"), item("R1")))
    assert bad.is_error and "R1" in bad.content[0].text
    forged = call(server, "project_write", section=SECTION, content=ROADMAP.replace("status: todo", "status: done", 1))
    assert not forged.is_error and statuses(ws)["R1"] == "todo"
