"""Run with: uv run --with pyyaml --with pytest pytest tools

Checks on the smoke test's own helpers; the smoke test itself needs Docker (uv run tools/smoke_backend.py).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sample_backend as sample  # noqa: E402
import smoke_backend as sb  # noqa: E402


def test_missing_ask_rules_are_reported(tmp_path, capsys):
    settings = tmp_path / "settings.json"
    assert sb.missing_ask_rules(settings) == list(sb.MANDATORY_ASK)  # no file: all missing
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(agentflow status *)"]}}), encoding="utf-8")
    assert sb.missing_ask_rules(settings) == list(sb.MANDATORY_ASK)
    settings.write_text(json.dumps({"permissions": {"ask": ["Bash(agentflow task approve *)", "Bash(agentflow decide *)"]}}), encoding="utf-8")
    assert sb.missing_ask_rules(settings) == ["task cancel"]
    assert sb.warn_if_ask_rules_missing(settings) is False
    assert "task cancel" in capsys.readouterr().out


def test_the_readme_permissions_satisfy_the_check(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(sb.readme_permissions()), encoding="utf-8")
    assert sb.missing_ask_rules(settings) == []


def test_the_sample_repository_has_main_and_develop(tmp_path):
    repo = sample.create_repo(tmp_path)
    assert sample.git(repo, "branch", "--show-current") == "develop"
    assert {"main", "develop"} <= set(sample.git(repo, "branch", "--format=%(refname:short)").split())
    assert sample.git(repo, "status", "--porcelain") == ""
    for name in (sample.SERVER_FILE, sample.SPEC_FILE, "compose.yaml", "Dockerfile"):
        assert (repo / name).is_file()
    assert "/items" not in (repo / sample.SERVER_FILE).read_text(encoding="utf-8")
    assert '"/items"' in sample.SERVER_WITH_ITEMS and "/items" in sample.SPEC_WITH_ITEMS


def test_the_sample_server_answers_405_for_any_other_method(tmp_path):
    namespace: dict = {}
    exec(compile(sample.SKELETON[sample.SERVER_FILE], "server.py", "exec"), namespace)  # noqa: S102 - our own sample code
    handler = namespace["Handler"]
    assert callable(handler.__getattr__)
    assert not hasattr(handler, "do_SURPRISE")  # class attribute lookup only; instances answer through __getattr__


def test_the_plan_text_names_both_roles():
    text = sb.plan_text("db-engineer", "UP", "`DOWN`")
    assert "role: db-engineer" in text and "role: implementer" in text and "`UP`" in text and "`DOWN`" in text


def test_the_sample_files_contain_no_secret_like_values():
    joined = "\n".join([*sample.SKELETON.values(), sample.MIGRATION_UP, sample.SERVER_WITH_ITEMS])
    assert "password" not in joined.lower() or "no password" in joined.lower()
