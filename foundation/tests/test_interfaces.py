from collections.abc import Sequence
from pathlib import Path

from agentflow.constants import GuardDecision, GuardRule
from agentflow.interfaces import (
    BranchLookup,
    CommandRunner,
    GitClient,
    SecretScanner,
    StateStore,
    ToolProbe,
    WorkflowSource,
)
from agentflow.models import (
    CommandResult,
    GuardVerdict,
    ProbeResult,
    ScanResult,
    State,
    Workflow,
    workflow_from_dict,
)


class FakeWorkflowSource:
    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow

    def load(self) -> Workflow:
        return self._workflow

    def fingerprint(self) -> str:
        return "0" * 64


class FakeStateStore:
    def __init__(self) -> None:
        self.state = State()

    def load(self) -> State:
        return self.state

    def save(self, state: State) -> State:
        self.state = state.stamped("2026-01-01T00:00:00Z")
        return self.state


class FakeToolProbe:
    def which(self, name: str) -> str | None:
        return None

    def run(self, args: Sequence[str]) -> ProbeResult:
        return ProbeResult(returncode=0, stdout="")


class FakeCommandRunner:
    def which(self, name: str) -> str | None:
        return name

    def run(self, args: Sequence[str], cwd: Path | None, timeout: int) -> CommandResult:
        return CommandResult(0, "", "")


class FakeGit:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.branch: str | None = "develop"
        self.branches = {"main", "develop"}
        self.staged = False
        self.commits: list[str] = []
        self.tags: set[str] = set()

    def current_branch(self) -> str | None:
        return self.branch

    def is_clean(self) -> bool:
        return not self.staged

    def branch_exists(self, name: str) -> bool:
        return name in self.branches

    def create_branch(self, name: str, base: str) -> None:
        self.branches.add(name)
        self.branch = name

    def has_staged_changes(self) -> bool:
        return self.staged

    def staged_files(self) -> list[str]:
        return []

    def commit(self, message: str) -> str:
        self.commits.append(message)
        self.staged = False
        return "0" * 40

    def rev_parse(self, ref: str) -> str:
        return "0" * 40

    def tag_exists(self, name: str) -> bool:
        return name in self.tags

    def create_tag(self, name: str, target: str, message: str) -> None:
        self.tags.add(name)

    def commits_between(self, base: str, head: str) -> list:
        return []

    def changed_files(self, base: str, head: str) -> list[str]:
        return []

    def identity(self) -> str:
        return "Test <test@example.invalid>"


class FakeScanner:
    def scan_staged(self, repo: Path) -> ScanResult:
        return ScanResult(clean=True, output="")


class FakeBranchLookup:
    def current_branch(self, directory: Path) -> str | None:
        return "develop"

    def branch_exists(self, directory: Path, name: str) -> bool:
        return True


ALL_PROTOCOLS = (WorkflowSource, StateStore, ToolProbe, CommandRunner, GitClient, SecretScanner, BranchLookup)


def test_fakes_satisfy_protocols(workflow_data, tmp_path):
    assert isinstance(FakeWorkflowSource(workflow_from_dict(workflow_data)), WorkflowSource)
    assert isinstance(FakeStateStore(), StateStore)
    assert isinstance(FakeToolProbe(), ToolProbe)
    assert isinstance(FakeCommandRunner(), CommandRunner)
    assert isinstance(FakeGit(tmp_path), GitClient)
    assert isinstance(FakeScanner(), SecretScanner)
    assert isinstance(FakeBranchLookup(), BranchLookup)


def test_object_missing_methods_does_not_satisfy_protocols():
    assert not any(isinstance(object(), protocol) for protocol in ALL_PROTOCOLS)


def test_guard_verdict_denied():
    assert GuardVerdict(GuardDecision.DENY, GuardRule.PUSH, "no").denied
    assert not GuardVerdict(GuardDecision.ALLOW).denied


def test_state_store_contract_round_trip():
    store: StateStore = FakeStateStore()
    written = store.save(State(active_task_id=None))
    assert written.updated_at is not None
    assert store.load() == written
