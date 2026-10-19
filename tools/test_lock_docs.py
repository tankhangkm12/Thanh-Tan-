"""Chặng E-lock (workflow, prompts, skills, documents, versions): the approved tests are locked, and the documents say how and where it ends.

The real `core/workflow.yaml` locks at `test-spec` (`lock_on_approval`), the steps after `plan` and `test-spec` carry the gate
`locked-files-intact`, and the checklist of `test-spec` lists the files that will be locked. The tester declares test
infrastructure under `## Hạ tầng test`, the implementer never touches the locked files, and the person changes an approved
test with `agentflow tests amend`. USAGE, README, architecture, CHANGELOG and the dev-backend README describe it, with its
limits. The versions go up here: agentflow 0.6.0, dev-core 0.5.0, dev-backend 0.3.0.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / build.DEFAULT_PLUGIN
BACKEND = REPO / "families" / "software-dev" / "backend"
USAGE = REPO / "families" / "software-dev" / "USAGE.md"
ARCHITECTURE = REPO / "docs" / "architecture.md"
README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"
RELEASE = REPO / "docs" / "release.md"
BACKEND_README = BACKEND / "README.md"

AGENTFLOW_VERSION, CORE_VERSION, BACKEND_VERSION = "0.6.0", "0.5.0", "0.3.0"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def workflow() -> dict:
    return yaml.safe_load(read(CORE / "workflow.yaml"))


def step(name: str) -> dict:
    return next(s for s in workflow()["steps"] if s["id"] == name)


def role(name: str) -> str:
    return read(CORE / build.ROLES_DIR / f"{name}.md")


def skill(name: str) -> str:
    return read(CORE / "skills" / name / "SKILL.md")


def section(text: str, heading: str, level: int = 2) -> str:
    marks = "#" * level
    found = re.search(rf"^{marks} {re.escape(heading)}\s*$(.*?)(?=^#{{1,{level}}} |\Z)", text, flags=re.M | re.S)
    assert found, f"no '{marks} {heading}' section"
    return found.group(1)


def unreleased() -> str:
    found = re.search(r"^## \[?Unreleased\]?.*?$(.*?)(?=^## |\Z)", read(CHANGELOG), flags=re.M | re.S | re.I)
    assert found
    return found.group(1)


# ------------------------------------------------------------------ the workflow


def test_only_the_test_spec_step_locks_what_it_approved():
    locking = [s["id"] for s in workflow()["steps"] if s.get("lock_on_approval")]
    assert locking == ["test-spec"]


def test_the_checklist_of_test_spec_lists_the_files_that_will_be_locked_and_asks_about_them():
    spec = step("test-spec")
    assert "locked-files" in spec["approval_items"] and "spec-items" in spec["approval_items"]
    joined = " ".join(spec["approval_checklist"]).lower()
    assert "khóa" in joined and "hạ tầng" in joined


@pytest.mark.parametrize("name", ["implement", "test", "security", "review"])
def test_every_step_after_the_lock_refuses_a_changed_locked_file(name):
    assert "locked-files-intact" in step(name).get("gates", [])


def test_the_test_step_checks_the_lock_before_it_runs_the_tests():
    gates = step("test")["gates"]
    assert gates.index("locked-files-intact") < gates.index("tests-pass")


@pytest.mark.parametrize("name", ["confirm", "plan", "test-spec"])
def test_the_steps_before_the_lock_do_not_have_the_gate(name):
    """Regression: the lock does not exist before the approval of test-spec, so the gate there would only fail."""
    assert "locked-files-intact" not in step(name).get("gates", [])


def test_the_generated_documents_are_up_to_date_with_the_workflow():
    assert build.check(CORE) == []
    assert "khóa" in build.checklists_block(CORE).lower()


# ------------------------------------------------------------------ the tester


@pytest.mark.parametrize(
    "needle",
    ["## Hạ tầng test", "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "jest.config", "vitest.config", "Makefile", "package.json", "agentflow tests check"],
)
def test_the_tester_declares_the_test_infrastructure_and_checks_the_lock(needle):
    assert needle in role("tester")


def test_the_tester_knows_what_the_lock_covers_and_when_it_starts():
    text = role("tester")
    assert re.search(r"lock(ed)?.{0,200}(approv|person)", text, flags=re.I | re.S)
    assert re.search(r"(build script|test runner|runs the tests).{0,200}(declare|list)", text, flags=re.I | re.S)


def test_the_tester_checks_the_lock_before_it_runs_the_tests_and_fails_the_step_when_it_changed():
    text = role("tester")
    step_test = text[text.index("## Step `test`") :]
    assert "agentflow tests check" in step_test
    assert re.search(r"changed.{0,200}--result fail|--result fail.{0,200}changed", step_test, flags=re.S)


def test_the_tester_may_make_test_configuration_in_the_test_spec_step_and_knows_shared_files_are_locked_by_their_test_settings():
    text = role("tester")
    assert re.search(r"(create|add|write).{0,160}(conftest|pytest\.ini).{0,300}(test-spec|before|approval)", text, flags=re.I | re.S)
    assert re.search(r"(pyproject\.toml|setup\.cfg|package\.json).{0,300}(test settings|test section|only)", text, flags=re.I | re.S)


def test_the_tester_never_adds_test_configuration_after_the_approval():
    text = role("tester")
    assert re.search(r"(never|do not|must not).{0,60}(create|add).{0,100}(conftest|pytest\.ini)", text, flags=re.I | re.S)


# ------------------------------------------------------------------ the implementer and the skills


def test_the_implementer_is_told_the_files_are_locked_and_what_to_do_instead():
    text = role("implementer")
    assert "locked" in text.lower() and "agentflow tests amend" in text
    assert re.search(r"(a )?person.{0,80}(runs|only)|only (a )?person", text, flags=re.I | re.S)
    assert re.search(r"(never|do not|must not).{0,60}(create|add).{0,100}(conftest|pytest\.ini|configuration)", text, flags=re.I | re.S)
    assert re.search(r"(stop|tell the person)", text, flags=re.I)


def test_the_implementer_is_told_it_may_still_change_the_other_parts_of_a_shared_file():
    text = role("implementer")
    assert re.search(r"(dependenc|other (part|section))", text, flags=re.I) and re.search(r"(pyproject\.toml|setup\.cfg|package\.json)", text)


def test_the_implementer_is_told_that_the_hook_and_the_gates_both_look():
    text = role("implementer")
    assert re.search(r"(hook|gate).{0,200}(hash|locked-files-intact|tests check)", text, flags=re.I | re.S)


def test_the_approve_skill_tells_the_person_the_lock_starts_now_and_how_to_change_a_test_later():
    text = skill("approve")
    assert "locked-files.json" in text and "agentflow tests amend" in text
    assert re.search(r"(never|do not).{0,80}agentflow tests amend|agentflow tests amend.{0,120}(person|their)", text, flags=re.I | re.S)


def test_the_continue_skill_says_the_tests_are_locked_after_test_spec_and_what_the_implementer_does_when_one_is_wrong():
    text = skill("continue")
    assert re.search(r"locked", text, flags=re.I) and "tests amend" in text


def test_no_prompt_or_skill_lets_an_agent_run_the_amend_command():
    """Regression for the day the prompts name the command: each mention says it is the person's."""
    for text in [role("tester"), role("implementer"), role("reviewer"), skill("approve"), skill("continue"), skill("start")]:
        for found in re.finditer(r"agentflow tests amend", text):
            around = text[max(0, found.start() - 200) : found.end() + 200].lower()
            assert re.search(r"person|never|do not|only", around), around


# ------------------------------------------------------------------ USAGE


def test_usage_has_a_section_on_the_locked_tests_with_the_files_the_hash_and_the_way_in():
    body = section(read(USAGE), "Khóa test đã duyệt")
    for needle in (
        "locked-files.json",
        "sha256",
        "## Hạ tầng test",
        "conftest.py",
        "pytest.ini",
        "pyproject.toml",
        "agentflow tests check",
        "locked-files-intact",
        "tests-pass",
        "agentflow tests amend",
        "--reason",
        "agentflow commit",
        "decisions/",
        "verify-red.json",
        "reverified",
        "mã cũ",
        "[tool.pytest",
        "setup.cfg",
        "package.json",
        "--accept-green",
    ):
        assert needle in body, needle


def test_usage_says_who_is_stopped_and_when_the_lock_ends():
    body = section(read(USAGE), "Khóa test đã duyệt")
    assert re.search(r"mọi role|mọi agent|bất kỳ agent", body) and re.search(r"(task xong|hủy task|task `done`)", body)
    assert re.search(r"(tạo mới|tạo thêm).{0,100}(conftest|cấu hình test)", body, flags=re.S | re.I)


def test_usage_walks_the_person_through_changing_an_approved_test():
    body = section(read(USAGE), "Khóa test đã duyệt")
    steps = [body.index(needle) for needle in ("agentflow tests amend", "agentflow commit")]
    assert steps == sorted(steps)
    assert re.search(r"cửa sổ", body) and re.search(r"(chặn|từ chối).{0,200}(mã cũ|xanh)|(mã cũ|xanh).{0,200}(chặn|từ chối)", body, flags=re.S | re.I)
    assert re.search(r"--accept-green.{0,200}(lý do|--reason)|(lý do|--reason).{0,200}--accept-green", body, flags=re.S)
    assert re.search(r"(phần|mục) cấu hình test.{0,200}(dependency|phụ thuộc)|(dependency|phụ thuộc).{0,200}(phần|mục) cấu hình test", body, flags=re.S | re.I)


def test_usage_lists_what_the_lock_does_not_reach():
    body = section(read(USAGE), "Giới hạn của khóa test", level=3)
    for needle in ("python -c", "Makefile", "package.json", "tester khai", "sandbox", "tests check"):
        assert needle in body, needle
    assert re.search(r"không phải sandbox|không (biến|làm).{0,40}không thể", body)


def test_usage_puts_the_amend_command_among_the_persons_commands():
    body = section(read(USAGE), "Lệnh của người")
    assert "agentflow tests amend" in body and "--reason" in body


def test_usage_troubleshooting_covers_the_new_refusals():
    body = section(read(USAGE), "Xử lý tình huống")
    for needle in ("locked-files-intact", "agentflow tests check", "agentflow tests amend", "verify-red.json", "config.yaml", "agentflow state accept", "Hạ tầng test"):
        assert needle in body, needle


def test_usage_names_the_whole_loop_with_the_lock_in_it():
    """Regression: the loop was already written down; it has to stay so while the lock section is added."""
    text = read(USAGE)
    loop = r"setup.{0,30}(→|->)\s*mission.{0,40}roadmap.{0,40}(→|->).{0,60}confirm\s*(→|->)\s*plan\s*(→|->)\s*test-spec\s*(→|->)\s*implement\s*(→|->)\s*test\s*(→|->)\s*security\s*(→|->)\s*review\s*(→|->)\s*\**replan"
    assert re.search(loop, text, flags=re.S)


# ------------------------------------------------------------------ README, architecture, backend README


def test_readme_names_the_lock_and_the_upgrade_steps():
    text = read(README)
    for needle in ("Khóa test", "agentflow tests amend", "locked-files-intact", "uv tool install --force --reinstall ./foundation", "agentflow workflow sync", f"agentflow {AGENTFLOW_VERSION}"):
        assert needle in text, needle
    assert re.search(r"claude plugin update", text) and re.search(r"agy plugin install", text)


def test_architecture_describes_the_lock_its_files_and_its_gates():
    text = read(ARCHITECTURE)
    for needle in (
        "lock_on_approval",
        "locked-files-intact",
        "locked-files.json",
        "locked_files_sha256",
        "agentflow tests check",
        "agentflow tests amend",
        "reverified",
        "Hạ tầng test",
        "PYTEST_ADDOPTS",
        "test_command",
        "--accept-green",
        "[tool.pytest",
        "scope",
    ):
        assert needle in text, needle


def test_architecture_has_a_section_for_the_lock_with_its_layers_and_honest_limits():
    body = section(read(ARCHITECTURE), "Khóa test đã duyệt", level=3)
    for layer in ("hook", "agentflow commit", "gate", "hash", "integrity.json", "tests amend"):
        assert layer in body, layer
    assert re.search(r"python -c", body) and re.search(r"Makefile|package.json", body)
    assert re.search(r"không phải sandbox|không (biến|làm).{0,40}không thể", body)
    assert re.search(r"Windows", body) and re.search(r"sandbox", body)


def test_the_protection_table_of_architecture_has_a_row_for_the_lock():
    body = section(read(ARCHITECTURE), "Mô hình bảo vệ duyệt", level=3)
    assert re.search(r"^\|[^|\n]*(Khóa test|locked-files)[^|\n]*\|", body, flags=re.M)


def test_architecture_lists_the_amend_command_among_the_ones_only_a_person_runs():
    body = section(read(ARCHITECTURE), "commit và guard", level=3)
    assert "tests amend" in body


def test_the_backend_readme_says_the_migration_tests_are_locked_too():
    text = read(BACKEND_README)
    assert re.search(r"khóa.{0,300}(test|migration)", text, flags=re.S | re.I) and "agentflow tests amend" in text


# ------------------------------------------------------------------ CHANGELOG


@pytest.mark.parametrize(
    "needle",
    [
        "lock_on_approval",
        "locked-files-intact",
        "agentflow tests check",
        "agentflow tests amend",
        "Hạ tầng test",
        "reverified",
        "PYTEST_ADDOPTS",
        "locked_files_sha256",
        "--accept-green",
        "[tool.pytest",
    ],
)
def test_the_changelog_records_the_lock(needle):
    assert needle in unreleased()


def test_the_changelog_says_what_the_lock_file_holds():
    assert re.search(r"locked-files\.json.{0,300}(sha256|hash)", unreleased(), flags=re.S)


def test_the_changelog_gives_the_numbers_and_the_upgrade_steps():
    text = read(CHANGELOG)
    assert f"agentflow {AGENTFLOW_VERSION}, dev-core {CORE_VERSION}, dev-backend {BACKEND_VERSION}" in text
    assert "uv tool install --force --reinstall ./foundation" in unreleased()
    assert "agentflow workflow sync" in unreleased()


def test_the_release_notes_carry_the_same_numbers():
    assert f"agentflow {AGENTFLOW_VERSION}" in read(RELEASE) and f"dev-core {CORE_VERSION}" in read(RELEASE) and f"dev-backend {BACKEND_VERSION}" in read(RELEASE)


# ------------------------------------------------------------------ versions


def test_agentflow_has_its_new_version():
    assert re.search(rf'^version = "{re.escape(AGENTFLOW_VERSION)}"', read(REPO / "foundation" / "pyproject.toml"), flags=re.M)


def test_the_lock_file_of_agentflow_has_its_new_version():
    assert re.search(rf'name = "agentflow"\s*\nversion = "{re.escape(AGENTFLOW_VERSION)}"', read(REPO / "foundation" / "uv.lock"))


@pytest.mark.parametrize(
    "plugin, version",
    [(CORE, CORE_VERSION), (BACKEND, BACKEND_VERSION)],
    ids=["dev-core", "dev-backend"],
)
def test_a_plugin_manifest_has_the_new_version(plugin, version):
    """The manifest of Claude Code; the one of Antigravity (`plugin.json` at the plugin root) carries no version."""
    assert json.loads(read(plugin / ".claude-plugin" / "plugin.json"))["version"] == version


def test_the_backend_readme_names_its_version():
    assert f"phiên bản {BACKEND_VERSION}" in read(BACKEND_README)


def test_the_backend_still_depends_on_the_core():
    """Regression: the version bump does not touch the dependency."""
    assert json.loads(read(BACKEND / ".claude-plugin" / "plugin.json"))["dependencies"] == ["dev-core"]
