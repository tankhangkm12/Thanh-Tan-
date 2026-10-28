"""``thanhtan permissions install``: the Claude Code rules of README Bước 4, merged into the settings file."""

import json

import pytest

from thanhtan.constants import ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.permissions import install, merge, shipped_rules


def settings(root):
    return json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def test_an_empty_project_gets_every_rule(tmp_path):
    path, result = install(tmp_path)
    assert result.changed and path == tmp_path / ".claude" / "settings.json"
    rules = shipped_rules()
    permissions = settings(tmp_path)["permissions"]
    for name in ("allow", "ask", "deny"):
        assert permissions[name] == rules[name]
    assert permissions["disableBypassPermissionsMode"] == "disable"


def test_the_persons_rules_stay_and_old_names_go(tmp_path):
    (tmp_path / ".claude").mkdir()
    old = {
        "model": "sonnet",
        "permissions": {
            "allow": ["Bash(mvn test *)", "Bash(agentflow status *)", "mcp__plugin_dev-core_agentflow__status", "Bash(thanhtan task approve *)"],
            "deny": ["Edit(./.agentflow/state.json)"],
        },
    }
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(old), encoding="utf-8")
    _path, result = install(tmp_path)
    data = settings(tmp_path)
    allow = data["permissions"]["allow"]
    assert data["model"] == "sonnet" and allow[0] == "Bash(mvn test *)"
    assert not [rule for rule in allow + data["permissions"]["deny"] if "agentflow" in rule]
    assert "Bash(thanhtan task approve *)" not in allow and "Bash(thanhtan task approve *)" in data["permissions"]["ask"]
    assert "Bash(agentflow status *)" in result.removed and "Bash(thanhtan status *)" in result.added


def test_installing_twice_changes_nothing(tmp_path):
    install(tmp_path)
    _path, result = install(tmp_path)
    assert not result.changed


def test_check_writes_nothing(tmp_path):
    _path, result = install(tmp_path, check=True)
    assert result.changed and not (tmp_path / ".claude" / "settings.json").exists()


def test_a_bypass_setting_of_the_person_is_kept(tmp_path):
    result = merge({"permissions": {"disableBypassPermissionsMode": "allow"}}, shipped_rules())
    assert result.settings["permissions"]["disableBypassPermissionsMode"] == "allow" and result.notes


def test_broken_settings_are_not_overwritten(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ThanhTanError) as refused:
        install(tmp_path)
    assert refused.value.code == ExitCode.INVALID_INPUT
    assert (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8") == "{not json"


def test_the_user_settings_file_can_be_the_target(tmp_path):
    path, _result = install(tmp_path / "project", user_home=tmp_path / "home")
    assert path == tmp_path / "home" / ".claude" / "settings.json" and path.is_file()
