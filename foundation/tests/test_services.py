import pytest
from conftest import SAMPLE_WORKFLOW, write_workflow

from agentflow.cli import main
from agentflow.constants import ActionKind, ExitCode, ProjectSection
from agentflow.errors import AgentflowError
from agentflow.interfaces import WorkspaceService
from agentflow.services import WorkspaceServices
from agentflow.workspace import find_workspace

GOOD_PLAN = """### C1 - Build it
- role: builder
- done-when: `pytest`
- docs: không có — internal change
"""


@pytest.fixture
def repo(gitflow_repo, tmp_path, monkeypatch, capsys):
    data = {**SAMPLE_WORKFLOW, "steps": [dict(step) for step in SAMPLE_WORKFLOW["steps"]]}
    data["steps"][1]["gates"] = ["plan-valid"]  # the "build" step plays the plan step
    path = write_workflow(tmp_path / "plugin" / "workflow.yaml", data)
    monkeypatch.chdir(gitflow_repo)
    assert main(["init", "--workflow", str(path)]) == ExitCode.OK
    capsys.readouterr()
    return gitflow_repo


@pytest.fixture
def service(repo):
    return WorkspaceServices(find_workspace(repo))


def refuses(call, code):
    with pytest.raises(AgentflowError) as exc:
        call()
    assert exc.value.code is code
    return str(exc.value)


def test_it_implements_the_protocol(service):
    assert isinstance(service, WorkspaceService)


def test_status_and_next_without_a_task(service):
    status = service.status()
    assert status.active_task is None and status.workflow == "sample" and status.next
    assert service.next_step().kind == ActionKind.START_TASK


def test_status_follows_the_task_as_it_changes(service, repo):
    main(["task", "new", "A task"])
    task = service.status().active_task
    assert (task.id, task.current_step, task.step_status, task.max_rounds) == ("T-001", "confirm", "in_progress", 2)
    assert service.next_step().kind == ActionKind.CONTINUE
    main(["task", "advance", "--result", "pass"])
    assert service.next_step().kind == ActionKind.AWAIT_APPROVAL
    assert service.status().active_task.step_status == "awaiting_approval"


def test_report_write_is_the_same_as_the_cli_and_returns_the_path(service, repo):
    main(["task", "new", "t"])
    info = service.write_report("confirm", "# Confirmed\nall clear")
    assert info.path.endswith("confirm.md") and info.bytes == len("# Confirmed\nall clear\n")
    assert (repo / ".ThanhTan" / "tasks" / "T-001" / "reports" / "confirm.md").read_text(encoding="utf-8").startswith("# Confirmed")


def test_report_write_follows_the_rules_of_the_cli(service):
    refuses(lambda: service.write_report("confirm", "x"), ExitCode.NO_ACTIVE_TASK)
    main(["task", "new", "t"])
    refuses(lambda: service.write_report("ghost", "x"), ExitCode.UNKNOWN_STEP)
    refuses(lambda: service.write_report("confirm", "  "), ExitCode.INVALID_INPUT)
    assert "current step 'confirm'" in refuses(lambda: service.write_report("build", "x"), ExitCode.REPORT_REFUSED)
    service.write_report("confirm", "done")
    main(["task", "advance", "--result", "pass"])
    assert "final" in refuses(lambda: service.write_report("confirm", "changed my mind"), ExitCode.REPORT_REFUSED)


def test_plan_check_reports_problems_as_a_result(service):
    refuses(service.plan_check, ExitCode.NO_ACTIVE_TASK)
    main(["task", "new", "t"])
    main(["task", "advance", "--result", "pass"])
    main(["task", "approve"])  # now at "build", the plan step
    refuses(service.plan_check, ExitCode.PLAN_INVALID)  # no plan report yet
    service.write_report("build", "### C1 - x\n- role: nobody\n")
    result = service.plan_check()
    assert not result.ok and any("unknown role" in problem for problem in result.problems)
    service.write_report("build", GOOD_PLAN)
    assert service.plan_check().ok and service.plan_check().problems == ()


def test_scan_summary_without_results(service):
    assert service.scan_summary().tools == ()
    main(["task", "new", "t"])
    summary = service.scan_summary()
    assert summary.task == "T-001" and summary.tools == () and summary.blocking == ()


# ------------------------------------------------------------ project documents


def test_project_write_stores_the_section(service, repo):
    info = service.write_project(ProjectSection.PROFILE, "# Profile\r\nA web shop\r\n")
    path = repo / ".ThanhTan" / "project" / "profile.md"
    assert info.path == str(path) and path.read_bytes() == b"# Profile\nA web shop\n"
    service.write_project(ProjectSection.PROFILE, "# Profile v2")
    assert path.read_text(encoding="utf-8") == "# Profile v2\n"


def test_project_write_rejects_empty_content_and_unknown_sections(service):
    refuses(lambda: service.write_project(ProjectSection.SOURCES, " \n"), ExitCode.INVALID_INPUT)
    with pytest.raises(ValueError):
        ProjectSection("secrets")


def test_project_documents_are_not_written_while_a_task_is_open(service, repo):
    main(["task", "new", "t"])
    message = refuses(lambda: service.write_project(ProjectSection.PROFILE, "# P"), ExitCode.PROJECT_WRITE_REFUSED)
    assert "task" in message and not (repo / ".ThanhTan" / "project" / "profile.md").exists()
    main(["task", "cancel"])
    service.write_project(ProjectSection.PROFILE, "# P")


# ------------------------------------------------------------------- knowledge


@pytest.fixture
def knowledge(repo):
    root = repo / ".ThanhTan" / "knowledge"
    (root / "lessons").mkdir(parents=True, exist_ok=True)
    (root / "lessons" / "retries.md").write_text("# Retries\nAlways back off.\nNever retry a POST.\n", encoding="utf-8")
    (root / "conventions.md").write_text("Prefer Enums over strings.\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG not text")
    return root


def test_knowledge_search_finds_lines_case_insensitively(service, knowledge):
    hits = service.knowledge_search("RETRY", 10)
    assert [(hit.file, hit.line) for hit in hits] == [("lessons/retries.md", 3)]
    assert "Never retry" in hits[0].text
    assert service.knowledge_search("enums", 10)[0].file == "conventions.md"
    assert service.knowledge_search("nothing like this", 10) == []


def test_knowledge_search_limits_and_ignores_empty_queries(service, knowledge):
    assert len(service.knowledge_search("e", 1)) == 1
    refuses(lambda: service.knowledge_search("  ", 5), ExitCode.INVALID_INPUT)
    assert not [hit for hit in service.knowledge_search("png", 10)]  # binary files are not searched


def test_knowledge_read_returns_a_file_inside_the_workspace_copy(service, knowledge):
    assert service.knowledge_read("lessons/retries.md").content.startswith("# Retries")
    assert service.knowledge_read("conventions.md").file == "conventions.md"


@pytest.mark.parametrize("name", ["../config.yaml", "..\\config.yaml", "/etc/hosts", "C:/Windows/win.ini", "lessons/../../state.json", "missing.md", "lessons", "image.png"])
def test_knowledge_read_stays_inside_the_knowledge_folder(service, knowledge, name):
    with pytest.raises(AgentflowError) as exc:
        service.knowledge_read(name)
    assert exc.value.code in {ExitCode.KNOWLEDGE_NOT_FOUND, ExitCode.INVALID_INPUT}


# --------------------------------------------------------- conventions document

CONVENTIONS = """# Quy ước

### PC-01 - Constants
- check: review
- status: unconfirmed
- source: src/constants.py (suy ra từ code)
- description: Fixed values live in constants or enums.

### PC-02 - Interface first
- check: plan
- rule: item-order
- source: docs/CONTRIBUTING.md:12
- description: Interfaces come before their implementations.

## Câu hỏi mở

### S1 - pytest or unittest?
- docs: docs/testing.md:5
- code: Makefile:14
"""


def conventions_path(repo):
    return repo / ".ThanhTan" / "project" / "conventions.md"


def confirm_by_hand(repo, code):
    """What a person does (or `agentflow project confirm`): flip the status of one convention in the file."""
    path = conventions_path(repo)
    text = path.read_text(encoding="utf-8")
    start = text.index(f"### {code} -")
    end = text.find("###", start + 3)
    block = text[start : end if end != -1 else len(text)]
    path.write_text(text.replace(block, block.replace("status: unconfirmed", "status: confirmed")), encoding="utf-8")


def test_conventions_are_stored_in_their_canonical_form(service, repo):
    info = service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    assert (info.conventions, info.open_questions, info.demoted) == (2, 1, ())
    stored = conventions_path(repo).read_text(encoding="utf-8")
    assert "### PC-02 - Interface first" in stored and "status: unconfirmed" in stored and "## Câu hỏi mở" in stored


def test_conventions_with_problems_are_refused_and_nothing_is_written(service, repo):
    message = refuses(
        lambda: service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS.replace("- check: review", "- check: lint")),
        ExitCode.CONVENTIONS_INVALID,
    )
    assert "PC-01" in message and "check" in message
    assert not conventions_path(repo).exists()


def test_an_agent_cannot_confirm_a_convention(service, repo):
    forged = CONVENTIONS.replace("- status: unconfirmed", "- status: confirmed")
    info = service.write_project(ProjectSection.CONVENTIONS, forged)
    assert info.demoted == ("PC-01",) and "status: confirmed" not in conventions_path(repo).read_text(encoding="utf-8")


def test_rewriting_a_confirmed_convention_unchanged_keeps_it_confirmed(service, repo):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_by_hand(repo, "PC-01")
    info = service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)  # the scout writes the same text again
    assert info.demoted == ()
    stored = conventions_path(repo).read_text(encoding="utf-8")
    assert stored.index("status: confirmed") < stored.index("### PC-02")


def test_changing_a_confirmed_convention_sets_it_back_to_unconfirmed(service, repo):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_by_hand(repo, "PC-01")
    changed = CONVENTIONS.replace("Fixed values live in constants or enums.", "Fixed values live in constants only.")
    info = service.write_project(ProjectSection.CONVENTIONS, changed)
    assert info.demoted == ("PC-01",)
    reread = conventions_path(repo).read_text(encoding="utf-8")
    assert "status: confirmed" not in reread and "constants only" in reread
    # ...even when the agent copies `status: confirmed` along with its edit.
    confirm_by_hand(repo, "PC-01")
    again = changed.replace("constants only", "constants and enums").replace("- status: unconfirmed", "- status: confirmed", 1)
    assert service.write_project(ProjectSection.CONVENTIONS, again).demoted == ("PC-01",)


@pytest.mark.parametrize("field", ["check", "rule", "source", "title"])
def test_every_part_of_a_confirmed_convention_counts_as_content(service, repo, field):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_by_hand(repo, "PC-02")
    edits = {
        "check": ("- check: plan", "- check: review"),
        "rule": ("- rule: item-order", "- rule: item-order\n- overrides: KC-01"),
        "source": ("docs/CONTRIBUTING.md:12", "docs/CONTRIBUTING.md:99"),
        "title": ("Interface first", "Interfaces first"),
    }
    old, new = edits[field]
    text = CONVENTIONS.replace(old, new)
    if field == "check":
        text = text.replace("- rule: item-order\n", "")
    assert service.write_project(ProjectSection.CONVENTIONS, text).demoted == ("PC-02",)


def test_a_confirmed_convention_cannot_be_deleted_by_an_agent(service, repo):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    confirm_by_hand(repo, "PC-02")
    before = conventions_path(repo).read_text(encoding="utf-8")
    without = CONVENTIONS.split("### PC-02")[0] + "## Câu hỏi mở\n\n### S1 - pytest or unittest?\n- docs: a\n- code: b\n"
    message = refuses(lambda: service.write_project(ProjectSection.CONVENTIONS, without), ExitCode.PROJECT_WRITE_REFUSED)
    assert "PC-02" in message and "person" in message
    assert conventions_path(repo).read_text(encoding="utf-8") == before


def test_an_unconfirmed_convention_may_be_deleted_and_added(service, repo):
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    only_second = CONVENTIONS.replace(CONVENTIONS.split("### PC-02")[0].split("# Quy ước\n")[1], "\n")
    info = service.write_project(ProjectSection.CONVENTIONS, only_second)
    assert info.conventions == 1 and "PC-01" not in conventions_path(repo).read_text(encoding="utf-8")


def test_other_sections_are_not_parsed_as_conventions(service):
    assert service.write_project(ProjectSection.ARCHITECTURE, "### not a convention\njust text").conventions == 0


def test_conventions_lists_what_is_enforced(service, repo):
    assert list(service.conventions()) == []
    service.write_project(ProjectSection.CONVENTIONS, CONVENTIONS)
    items = {item.code: item for item in service.conventions()}
    assert set(items) == {"PC-01", "PC-02"} and not items["PC-01"].enforced and items["PC-01"].source == "project"
    confirm_by_hand(repo, "PC-02")
    assert {item.code: item.enforced for item in service.conventions()} == {"PC-01": False, "PC-02": True}
