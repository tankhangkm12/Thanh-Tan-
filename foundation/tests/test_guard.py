import json
from pathlib import Path

import pytest

from agentflow.constants import ExitCode, GuardDecision, GuardRule
from agentflow.errors import AgentflowError
from agentflow.guard import evaluate, parse_request, split_commands, verdict_to_dict

CWD = Path("/work/repo")
OTHER = Path("/work/other")


class Branches:
    """Repo at CWD is on `current`; OTHER is on main. Known branches: main, develop, feature/x."""

    def __init__(self, current="feature/x"):
        self.current = {CWD: current, OTHER: "main"}

    def current_branch(self, directory):
        return self.current.get(directory)

    def branch_exists(self, directory, name):
        return name in {"main", "develop", "feature/x"}


def check(command, current="feature/x"):
    return evaluate(command, CWD, Branches(current))


DENIED = [
    # push in any form
    ("git push", GuardRule.PUSH),
    ("git push origin develop --force", GuardRule.PUSH),
    ("git -C sub push", GuardRule.PUSH),
    ("git -c core.editor=vi push", GuardRule.PUSH),
    ('"C:\\Program Files\\Git\\bin\\git.exe" push', GuardRule.PUSH),
    ("GIT.EXE push", GuardRule.PUSH),
    ("git status && git push", GuardRule.PUSH),
    ("git status; git push", GuardRule.PUSH),
    ("git status || git push", GuardRule.PUSH),
    ("git status\ngit push", GuardRule.PUSH),
    ("echo y | git push", GuardRule.PUSH),
    ("xargs git push < remotes", GuardRule.PUSH),
    ("if ($LASTEXITCODE -eq 0) { git push origin develop }", GuardRule.PUSH),
    ("& git push", GuardRule.PUSH),
    ("echo $(git push)", GuardRule.PUSH),
    ("x=`git push`", GuardRule.PUSH),
    ("bash -c 'git push origin'", GuardRule.PUSH),
    ('powershell -Command "git push"', GuardRule.PUSH),
    ("cmd /c git push", GuardRule.PUSH),
    ('sh -c "bash -c \\"git push\\""', GuardRule.PUSH),
    ('eval "git push"', GuardRule.PUSH),
    # reset --hard, anywhere
    ("git reset --hard", GuardRule.RESET_HARD),
    ("git reset --hard HEAD~1", GuardRule.RESET_HARD),
    ("git reset --hard HEAD@{1}", GuardRule.RESET_HARD),
    # clean with force and directories
    ("git clean -fd", GuardRule.CLEAN_FORCE_DIRS),
    ("git clean -df", GuardRule.CLEAN_FORCE_DIRS),
    ("git clean -fdx", GuardRule.CLEAN_FORCE_DIRS),
    ("git clean -f -d", GuardRule.CLEAN_FORCE_DIRS),
    ("git clean --force -d", GuardRule.CLEAN_FORCE_DIRS),
    # force-deleting branches
    ("git branch -D feature/x", GuardRule.BRANCH_FORCE_DELETE),
    ("git branch -d -f feature/x", GuardRule.BRANCH_FORCE_DELETE),
    ("git branch --delete --force feature/x", GuardRule.BRANCH_FORCE_DELETE),
    ("git branch -df feature/x", GuardRule.BRANCH_FORCE_DELETE),
    # deleting tags
    ("git tag -d v1", GuardRule.TAG_DELETE),
    ("git tag --delete v1", GuardRule.TAG_DELETE),
]


@pytest.mark.parametrize(("command", "rule"), DENIED)
def test_denied(command, rule):
    verdict = check(command)
    assert verdict.decision is GuardDecision.DENY, command
    assert verdict.rule is rule
    assert verdict.reason


@pytest.mark.parametrize("subcommand", ["commit -m x", "merge feature/x", "rebase main", "cherry-pick abc", "revert abc", "am p.patch"])
@pytest.mark.parametrize("branch", ["main", "develop"])
def test_committing_on_protected_branch_is_denied(subcommand, branch):
    verdict = check(f"git {subcommand}", current=branch)
    assert verdict.rule is GuardRule.PROTECTED_BRANCH
    assert f"'{branch}'" in verdict.reason


@pytest.mark.parametrize(
    "command",
    [
        "git switch develop && git merge feature/x",
        "git checkout main; git commit -m x",
        "git switch -c develop && git commit -m x",
        "git -C ../other commit -m x",
        "cd ../other && git commit -m x",
    ],
)
def test_switching_to_a_protected_branch_within_the_command_is_tracked(command):
    assert check(command).rule is GuardRule.PROTECTED_BRANCH


ALLOWED = [
    ("git status", "feature/x"),
    ("git commit -m 'add push support'", "feature/x"),
    ('git commit -m "docs: never git push; reset --hard"', "feature/x"),
    ("git merge develop", "feature/x"),
    ("git rebase develop", "feature/x"),
    ("git fetch origin", "develop"),
    ("git pull --ff-only", "develop"),
    ("git log --oneline | head", "main"),
    ("git reset --soft HEAD~1", "feature/x"),
    ("git reset HEAD file.txt", "feature/x"),
    ("git clean -n -d", "feature/x"),
    ("git clean -fx", "feature/x"),
    ("git branch -d feature/x", "develop"),
    ("git branch feature/y", "develop"),
    ("git tag v1", "develop"),
    ("git tag -l", "develop"),
    ("git merge --abort", "develop"),
    ("git rebase --abort", "main"),
    ("git switch feature/x && git commit -m x", "develop"),
    ("git checkout -b feature/y && git commit -m x", "develop"),
    ("git checkout -- src/app.py", "feature/x"),
    ("git checkout src/app.py && git commit -m x", "feature/x"),
    ("grep -r 'git push' docs", "main"),
    ("agentflow commit 'msg'", "feature/x"),
    ("uv run pytest", "main"),
    ("git", "main"),
    ("", "main"),
    ("git commit -m \"unbalanced", "feature/x"),
]


@pytest.mark.parametrize(("command", "current"), ALLOWED)
def test_allowed(command, current):
    verdict = check(command, current)
    assert verdict.decision is GuardDecision.ALLOW, (command, verdict.reason)
    assert verdict.rule is None


def test_unknown_branch_allows_commits():
    assert not check("git commit -m x", current=None).denied


def test_unbalanced_quotes_still_find_push():
    assert check('git push "origin').rule is GuardRule.PUSH


def test_split_commands_respects_quotes():
    assert split_commands('git commit -m "a; b && c" && git status') == [
        ["git", "commit", "-m", "a; b && c"],
        ["git", "status"],
    ]


def test_parse_request_and_output():
    request = parse_request(json.dumps({"command": "git push", "cwd": "/x"}))
    assert request.command == "git push" and request.cwd == Path("/x")
    assert parse_request('{"command": "ls"}').cwd is None
    verdict = check("git push")
    out = json.loads(json.dumps(verdict_to_dict(verdict)))
    assert out == {"decision": "deny", "rule": "push", "reason": verdict.reason}


@pytest.mark.parametrize("text", ["not json", "[]", '{"cwd": "/x"}', '{"command": 1}', '{"command": "ls", "cwd": 3}'])
def test_parse_request_rejects_bad_input(text):
    with pytest.raises(AgentflowError) as exc:
        parse_request(text)
    assert exc.value.code is ExitCode.INVALID_INPUT


class FakeWorkspaces:
    def __init__(self, *roots):
        self.roots = {Path(root) for root in roots}

    def has_workspace(self, directory):
        return Path(directory) in self.roots


class OnFeature:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


def in_project(command, cwd="/proj", roots=("/proj",)):
    return evaluate(command, Path(cwd), OnFeature(), FakeWorkspaces(*roots))


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git commit --amend --no-edit",
        "git -c user.name=x commit -m y",
        "git -C /proj commit -m x",
        "bash -c 'git commit -m x'",
        "git add . && git commit -m x",
        "git status | git commit -F -",
    ],
)
def test_direct_commit_is_denied_in_a_workspace(command):
    verdict = in_project(command)
    assert verdict.decision is GuardDecision.DENY and verdict.rule is GuardRule.DIRECT_COMMIT


def test_direct_commit_is_allowed_without_a_workspace_and_agentflow_commit_always():
    assert in_project("git commit -m x", roots=()).decision is GuardDecision.ALLOW
    assert in_project("agentflow commit 'fix git commit'").decision is GuardDecision.ALLOW
    assert in_project("git -C /elsewhere commit -m x").decision is GuardDecision.ALLOW


@pytest.mark.parametrize(
    "command",
    ["git tag agentflow/T-001/approved", "git tag -a agentflow/T-001/approved -m x", "git update-ref refs/tags/agentflow/T-001/approved HEAD"],
)
def test_forging_an_approval_tag_is_denied(command):
    assert in_project(command, roots=()).rule is GuardRule.APPROVAL_TAG


def test_ordinary_tags_are_fine():
    assert in_project("git tag v1.0").decision is GuardDecision.ALLOW


@pytest.mark.parametrize(
    "command",
    ["agentflow decide --suppress x --reason y", "agentflow ext add e.yaml", "agentflow ext sync", "agentflow config set a.b c", "cd /proj && agentflow decide --suppress x", "agentflow project confirm --all", "agentflow project confirm PC-01"],
)
def test_person_only_commands_are_denied_in_a_workspace(command):
    assert in_project(command).rule is GuardRule.PERSON_ONLY
    assert in_project(command, roots=()).decision is GuardDecision.ALLOW


def test_other_agentflow_commands_are_allowed():
    for command in ("agentflow status", "agentflow task advance", "agentflow config get a.b", "agentflow ext list", "agentflow project", "agentflow commit decide"):
        assert in_project(command).decision is GuardDecision.ALLOW, command


# ----------------------------------------------------- shell writes into .ThanhTan/


class AnyBranch:
    def current_branch(self, directory):
        return "feature/x"

    def branch_exists(self, directory, name):
        return True


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".ThanhTan").mkdir()
    (tmp_path / ".ThanhTan" / "config.yaml").write_text("x", encoding="utf-8")
    return tmp_path


def shell(repo, command):
    return evaluate(command, repo, AnyBranch())


WRITES_DENIED = [
    "echo x > .ThanhTan/decisions/a.md",
    "echo x>.ThanhTan/decisions/a.md",
    "echo x >> .ThanhTan/decisions/a.md",
    "echo x >| .ThanhTan/decisions/a.md",
    "echo x &> .ThanhTan/log",
    "echo x 2> .ThanhTan/err",
    "printf 'a' >\".ThanhTan/decisions/a.md\"",
    "cat notes.txt | tee .ThanhTan/decisions/a.md",
    "tee -a .ThanhTan/decisions/a.md < notes.txt",
    "cp notes.txt .ThanhTan/decisions/a.md",
    "cp -r notes .ThanhTan/decisions/",
    "cp -t .ThanhTan/decisions notes.txt",
    "mv notes.txt .ThanhTan/decisions/a.md",
    "mv .ThanhTan/state.json /tmp/stolen",
    "rm .ThanhTan/state.json",
    "rm -rf .ThanhTan",
    "touch .ThanhTan/decisions/a.md",
    "truncate -s 0 .ThanhTan/state.json",
    "sed -i s/a/b/ .ThanhTan/state.json",
    "dd if=/dev/zero of=.ThanhTan/state.json",
    "ls && echo x > ./.ThanhTan/../.ThanhTan/decisions/a.md",
    "cd .ThanhTan && echo x > decisions/a.md",
    "cd src; echo x > ../.ThanhTan/decisions/a.md",
    "bash -c 'echo x > .ThanhTan/decisions/a.md'",
    'powershell -Command "Set-Content .ThanhTan/decisions/a.md x"',
    r"Set-Content -Path .ThanhTan\decisions\a.md -Value x",

    "Add-Content -Path .ThanhTan/decisions/a.md -Value x",
    "Out-File -FilePath .ThanhTan/decisions/a.md",
    "'x' | Out-File .ThanhTan/decisions/a.md",
    "echo x > .ThanhTan/decisions/a.md",
    "New-Item -ItemType File .ThanhTan/decisions/a.md",
    "ni .ThanhTan/decisions/a.md",
    "Remove-Item -Recurse -Force .ThanhTan",
    "ri .ThanhTan/state.json",
    "Clear-Content .ThanhTan/state.json",
    "Copy-Item notes.txt -Destination .ThanhTan/decisions/a.md",
    "Move-Item .ThanhTan/state.json elsewhere",
    r"del .ThanhTan\state.json",
]


@pytest.mark.parametrize("command", WRITES_DENIED)
def test_shell_writes_into_the_workspace_are_denied(repo, command):
    verdict = shell(repo, command)
    assert verdict.denied and verdict.rule == GuardRule.WORKSPACE_WRITE, command


WRITES_ALLOWED = [
    "cat .ThanhTan/state.json",
    "ls .ThanhTan/decisions",
    "grep -r x .ThanhTan",
    "cp .ThanhTan/state.json /tmp/copy.json",
    "Copy-Item .ThanhTan/state.json -Destination copy.json",
    "echo x > notes.txt",
    "echo x > /dev/null",
    "make 2>&1 | tee build.log",
    "tee build.log < notes.txt",
    "rm notes.txt",
    "mv a.txt b.txt",
    "echo .ThanhTan > ignore.txt",

    "cp a.txt src/.ThanhTan-notes/a.txt",
    "agentflow report --step plan",
    "agentflow status",
    "git status",
    "Set-Content notes.txt x",
    # A heredoc body is data for the command that reads it, whatever characters it holds.
    "agentflow report --step plan <<'EOF'\n### C1 - a > .ThanhTan/x\n- done-when: `echo y > .ThanhTan/z`\nEOF",
    "agentflow report --step plan <<-EOF\n\tcp a .ThanhTan/b\n\tEOF\necho done",
]


@pytest.mark.parametrize("command", WRITES_ALLOWED)
def test_other_shell_commands_are_allowed(repo, command):
    assert not shell(repo, command).denied, command


def test_a_command_after_a_heredoc_is_still_checked(repo):
    command = "agentflow report --step plan <<'EOF'\nbody\nEOF\necho x > .ThanhTan/decisions/a.md"
    assert shell(repo, command).rule == GuardRule.WORKSPACE_WRITE


def test_without_a_workspace_nothing_is_protected(tmp_path):
    assert not evaluate("echo x > .ThanhTan/decisions/a.md", tmp_path, AnyBranch()).denied
