"""Phase D-guard (D5): the permissions block in README Bước 4 is safe to paste and matches what the hook enforces.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"

# Commands of a person: none of them may be allowed by a rule (the hook denies or asks, and a rule must not undo that).
PERSON_COMMANDS = [
    "task approve",
    "task cancel",
    "task seal",
    "decide",
    "project confirm",
    "roadmap set",
    "replan done",
    "replan skip",
    "ext add",
    "ext sync",
    "config set",
    "knowledge init",
    "knowledge pull",
    "knowledge push",
    "role grant",
    "role revoke",
    "role sync",
]
EDIT_DENIES = [
    "Edit(./.claude/settings.json)",
    "Edit(./.claude/settings.local.json)",
    "Edit(./.agentflow/state.json)",
    "Edit(./.agentflow/**/state.json)",
]
SHELLS = ("Bash", "PowerShell")


def step4() -> str:
    text = README.read_text(encoding="utf-8")
    found = re.search(r"^### Bước 4\b.*?$(.*?)(?=^#{1,3} )", text, flags=re.M | re.S)
    assert found, "README has no '### Bước 4' section"
    return found.group(0)


def rules() -> dict:
    block = re.search(r"```json\n(.*?)\n```", step4(), flags=re.S)
    assert block, "README Bước 4 has no JSON block"
    return json.loads(block.group(1))["permissions"]


def test_the_block_is_valid_json_with_the_three_rule_lists():
    permissions = rules()
    for name in ("allow", "ask", "deny"):
        assert isinstance(permissions[name], list) and permissions[name], name
        assert all(isinstance(rule, str) for rule in permissions[name])


def test_bypass_mode_is_switched_off_in_the_block():
    assert rules()["disableBypassPermissionsMode"] == "disable"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("command", ["agentflow task approve", "agentflow task cancel"])
def test_approving_and_cancelling_are_asked_in_both_shells(shell, command):
    assert f"{shell}({command} *)" in rules()["ask"]


def test_decide_is_not_among_the_asked_commands_because_the_hook_denies_it():
    """Q-D1: `decide` stays a person's command (denied by the hook); an ask rule would promise a prompt that never comes."""
    assert not [rule for rule in rules()["ask"] if "decide" in rule]


@pytest.mark.parametrize("rule", EDIT_DENIES)
def test_the_files_that_hold_the_rules_and_the_state_cannot_be_edited_by_the_agent(rule):
    assert rule in rules()["deny"]


def test_no_allow_rule_opens_the_door_to_arbitrary_code():
    for rule in rules()["allow"]:
        lowered = rule.lower()
        assert "python" not in lowered and "uv run" not in lowered and "uvx" not in lowered, rule
        assert not re.fullmatch(r"(Bash|PowerShell)(\(\*\))?", rule), rule
        assert not re.match(r"(Bash|PowerShell)\(\*", rule), rule


@pytest.mark.parametrize("command", PERSON_COMMANDS)
def test_no_allow_rule_covers_a_command_of_a_person(command):
    for rule in rules()["allow"]:
        assert f"agentflow {command}" not in rule, rule


def test_every_allow_rule_for_the_shells_starts_with_agentflow():
    for rule in rules()["allow"]:
        match = re.fullmatch(r"(?:Bash|PowerShell)\((.*)\)", rule)
        if match:
            assert match.group(1).startswith("agentflow "), rule


# ------------------------------------------------------------------ the text around it


def test_the_text_says_why_a_bash_rule_is_not_a_boundary_and_the_hook_is_the_main_layer():
    text = step4()
    assert "uv run" in text and "python -m" in text
    assert "hook" in text.lower()
    assert "đường dẫn đầy đủ" in text


def test_the_text_warns_against_running_in_bypass_mode_and_names_the_setting():
    text = step4()
    assert "bypassPermissions" in text and "disableBypassPermissionsMode" in text


def test_the_text_says_the_setting_also_stops_the_user_from_turning_bypass_on_in_that_project():
    text = step4()
    assert re.search(r"disableBypassPermissionsMode.{0,500}(chính bạn|cả bạn|bạn cũng)|(chính bạn|cả bạn|bạn cũng).{0,500}disableBypassPermissionsMode", text, flags=re.S)


def test_the_text_says_which_rules_hold_in_every_mode():
    text = step4()
    assert re.search(r"deny.{0,200}mọi chế độ|mọi chế độ.{0,200}deny", text, flags=re.S)
    assert re.search(r"allow.{0,200}không có tác dụng.{0,80}bypassPermissions", text, flags=re.S)


def test_the_text_states_that_there_is_no_sandbox_on_native_windows():
    text = step4()
    assert "sandbox" in text.lower() and "Windows" in text


def test_the_old_claim_that_a_python_rule_was_tried_and_is_fine_is_gone():
    text = step4()
    assert "quy tắc `Bash(python *)` cho phép" not in text
    assert "Bash(python *)" not in "\n".join(rules()["allow"])
    # The advice not to do it stays, in whatever words, next to the commands it is about.
    assert re.search(r"không.{0,40}`Bash\(python \*\)`|`Bash\(python \*\)`.{0,120}(rủi ro|nguy hiểm|không nên|tránh)", text, flags=re.S)


def test_the_text_does_not_promise_that_decide_asks():
    text = step4()
    intro = text.split("```json")[0]
    assert "agentflow decide" not in intro.split("**ask**")[-1].split(".")[0]
