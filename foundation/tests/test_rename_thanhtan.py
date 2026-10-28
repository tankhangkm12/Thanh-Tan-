"""From 1.0.0 the program is called ``thanhtan``; ``agentflow`` (its name before) stays as an alias.

- ``agentflow ...`` runs the same program and says the new name on stderr, except for the commands a CLI runs for itself
  (``hook``, ``mcp``, ``guard``), whose output a program reads.
- ``THANHTAN_*`` environment variables win; the ``AGENTFLOW_*`` names are still read.
- The guard treats ``agentflow`` exactly like ``thanhtan``: the alias is no way around it.
- Approval tags are now ``thanhtan/<task>/approved``; ``agentflow/<task>/approved`` tags still count and stay protected.
"""

from pathlib import Path

import pytest
from conftest import git
from test_seal import drive_to_the_end, finish_task, say, ws  # noqa: F401  (ws is a fixture)

from thanhtan import envvars
from thanhtan.cli import ALIAS_NOTICE, legacy_main
from thanhtan.constants import ExitCode, GuardDecision, GuardRule
from thanhtan.guard import evaluate
from thanhtan.seal import approval_tag


class _OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


class _Workspaces:
    def has_workspace(self, directory):
        return True


def verdict(command):
    return evaluate(command, Path("/proj"), _OnFeature(), _Workspaces())


# ------------------------------------------------------------------ the alias


def test_the_alias_runs_the_same_program_and_names_the_new_one(capsys):
    with pytest.raises(SystemExit) as done:  # argparse ends --version with exit 0
        legacy_main(["--version"])
    assert done.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("thanhtan ")
    assert ALIAS_NOTICE in captured.err


@pytest.mark.parametrize("command", [["guard", "git status"], ["hook", "--help"]])
def test_the_alias_is_quiet_for_what_a_cli_runs_itself(command, capsys):
    try:
        legacy_main(command)
    except SystemExit:
        pass  # --help
    assert ALIAS_NOTICE not in capsys.readouterr().err


# ------------------------------------------------------------------ environment


def test_the_new_variable_wins_and_the_old_one_is_still_read():
    assert envvars.get({"THANHTAN_HOME": "/new", "AGENTFLOW_HOME": "/old"}, "THANHTAN_HOME") == "/new"
    assert envvars.get({"AGENTFLOW_HOME": "/old"}, "THANHTAN_HOME") == "/old"
    assert envvars.get({"THANHTAN_HOME": ""}, "THANHTAN_HOME") is None
    assert envvars.legacy_name("THANHTAN_PROJECT_DIR") == "AGENTFLOW_PROJECT_DIR"


# ------------------------------------------------------------------ the guard


@pytest.mark.parametrize(
    "command",
    ["agentflow task approve", "uv run agentflow task cancel", "python -m agentflow task approve", "timeout 5 agentflow task approve"],
)
def test_the_old_name_still_asks_a_person(command):
    assert verdict(command).decision is GuardDecision.ASK


@pytest.mark.parametrize("command", ["agentflow decide --suppress x --reason y", "agentflow config set a.b c", "agentflow task seal T-001"])
def test_the_old_name_still_cannot_run_a_persons_command(command):
    assert verdict(command).decision is GuardDecision.DENY


def test_a_script_that_runs_the_old_name_is_read_too():
    found = verdict("python - <<'EOF'\nimport subprocess\nsubprocess.run(['agentflow', 'task', 'approve'])\nEOF")
    assert found.decision is not GuardDecision.ALLOW


@pytest.mark.parametrize(
    "command",
    ["git tag thanhtan/T-001/approved", "git tag agentflow/T-001/approved", "git update-ref refs/tags/agentflow/T-001/approved HEAD"],
)
def test_neither_kind_of_approval_tag_can_be_forged(command):
    assert verdict(command).rule is GuardRule.APPROVAL_TAG


# ------------------------------------------------------------------ approval tags


def test_new_approvals_make_thanhtan_tags():
    assert approval_tag("T-001") == "thanhtan/T-001/approved"


def test_a_task_approved_before_1_0_0_still_counts_as_sealed(ws, monkeypatch, capsys):  # noqa: F811
    finish_task(ws, monkeypatch)
    drive_to_the_end(ws, monkeypatch)
    say(monkeypatch, "task", "approve")
    # What 0.8.0 left: the same tag, under the old prefix.
    git(ws, "tag", "-a", "agentflow/T-001/approved", "-m", "approved", approval_tag("T-001"))
    git(ws, "tag", "-d", approval_tag("T-001"))
    git(ws, "switch", "-q", "develop")
    assert say(monkeypatch, "task", "new", "second") == ExitCode.OK
    capsys.readouterr()
    assert say(monkeypatch, "task", "seal", "T-001") == ExitCode.TASK_CONFLICT
    assert "already has its approval tag" in capsys.readouterr().err
