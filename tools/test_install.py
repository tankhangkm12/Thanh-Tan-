"""tools/install.py: one command installs or updates thanhtan and the plugins, with a Python that uv manages.

The programs are faked: each test says what is on PATH and what each command answers, and reads the commands that ran.

Run with: uv run --with pyyaml --with pytest pytest tools
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import install  # noqa: E402

THANHTAN = install.repo_version("thanhtan")
CORE = install.repo_version(install.CORE)


class FakeRunner(install.Runner):
    def __init__(self, on_path=("uv", "git", "docker", "thanhtan", "claude", "agy"), answers=None):
        self.on_path = set(on_path)
        self.answers = answers or {}
        self.calls: list[list[str]] = []

    def which(self, name):
        return f"/bin/{name}" if name in self.on_path else None

    def run(self, args):
        self.calls.append(list(args))
        key = " ".join(args)
        for prefix, answer in self.answers.items():
            if key.startswith(prefix):
                return answer(args) if callable(answer) else answer
        if key == "thanhtan --version":
            return install.Result(0, f"thanhtan {THANHTAN}\n")
        if key == "claude plugin list --json":
            return install.Result(0, json.dumps([{"id": f"dev-core@{install.MARKETPLACE}", "version": CORE, "enabled": True}]))
        if key == "claude plugin marketplace list":
            return install.Result(0, f"{install.MARKETPLACE}\n")
        if key == "agy plugin list":
            return install.Result(0, '[{"name": "dev-core"}]')
        return install.Result(0, "")

    def ran(self, *prefix):
        return [call for call in self.calls if call[: len(prefix)] == list(prefix)]


def test_thanhtan_is_installed_with_a_python_that_uv_manages(capsys):
    runner = FakeRunner()
    assert install.main([], runner) == 0
    assert runner.ran("uv", "python", "install", "3.12")
    (command,) = runner.ran("uv", "tool", "install")
    assert command[command.index("--python") + 1] == "3.12" and "--managed-python" in command and "--reinstall" in command
    assert command[-1] == str(install.FOUNDATION)


def test_an_old_uv_without_managed_python_still_installs(capsys):
    def tool(args):
        return install.Result(2, "error: unexpected argument '--managed-python' found") if "--managed-python" in args else install.Result(0, "")

    runner = FakeRunner(answers={"uv tool install": tool})
    assert install.main([], runner) == 0
    assert len(runner.ran("uv", "tool", "install")) == 2


def test_a_file_held_by_an_open_session_says_to_close_it(capsys):
    runner = FakeRunner(answers={"uv tool install": install.Result(2, "error: failed to remove thanhtan.exe: Access is denied. (os error 5)")})
    assert install.main([], runner) == 1
    assert "close those sessions" in capsys.readouterr().out
    assert not runner.ran("claude")  # stops before the plugins


def test_both_clis_get_dev_core_and_a_known_plugin_is_updated(capsys):
    runner = FakeRunner()
    assert install.main([], runner) == 0
    assert runner.ran("claude", "plugin", "marketplace", "update", install.MARKETPLACE)
    assert runner.ran("claude", "plugin", "update", f"dev-core@{install.MARKETPLACE}")
    assert runner.ran("agy", "plugin", "install", str(install.PLUGIN_DIRS[install.CORE]))


def test_a_first_install_adds_the_marketplace_and_installs(capsys):
    runner = FakeRunner(answers={"claude plugin marketplace list": install.Result(0, ""), "claude plugin list --json": install.Result(0, "[]")})
    install.main(["--only", "claude"], runner)
    assert runner.ran("claude", "plugin", "marketplace", "add", str(install.REPO))
    assert runner.ran("claude", "plugin", "install", f"dev-core@{install.MARKETPLACE}")
    assert not runner.ran("agy")


def test_backend_and_design_add_their_plugins(capsys):
    runner = FakeRunner()
    install.main(["--only", "agy", "--backend", "--design"], runner)
    installed = [call[-1] for call in runner.ran("agy", "plugin", "install")]
    assert installed == [str(install.PLUGIN_DIRS[name]) for name in ("dev-core", "dev-backend", "design-core", "design-architecture")]


def test_check_changes_nothing_and_reports_an_old_version(capsys):
    runner = FakeRunner(answers={"thanhtan --version": install.Result(0, "thanhtan 0.1.0\n")})
    assert install.main(["--check"], runner) == 1
    assert not runner.ran("uv", "tool") and not runner.ran("claude", "plugin", "install") and not runner.ran("agy", "plugin", "install")
    out = capsys.readouterr().out
    assert "PATH has 0.1.0" in out and "Run without --check" in out


def test_a_missing_cli_is_skipped_with_a_warning(capsys):
    runner = FakeRunner(on_path=("uv", "git", "docker", "thanhtan", "claude"))
    assert install.main([], runner) == 0
    assert not runner.ran("agy")
    assert "[warn] agy on PATH" in capsys.readouterr().out


def test_without_uv_nothing_is_done(capsys):
    runner = FakeRunner(on_path=("git", "claude"))
    assert install.main([], runner) == 1
    assert runner.calls == [] or all(call[0] == "docker" for call in runner.calls)


def test_projects_are_never_touched(capsys):
    runner = FakeRunner()
    install.main(["--backend", "--design"], runner)
    assert not [call for call in runner.calls if call[0] == "thanhtan" and call[1:] != ["--version"]]


def test_the_old_agentflow_tool_is_removed_first(capsys):
    runner = FakeRunner(answers={"uv tool list": install.Result(0, "agentflow v0.8.0\n- agentflow\nruff v0.1\n")})
    assert install.main([], runner) == 0
    uninstall = runner.ran("uv", "tool", "uninstall", "agentflow")
    assert uninstall and runner.calls.index(uninstall[0]) < runner.calls.index(runner.ran("uv", "tool", "install")[0])
    assert "remove the old agentflow tool" in capsys.readouterr().out


def test_without_an_old_tool_nothing_is_uninstalled(capsys):
    runner = FakeRunner(answers={"uv tool list": install.Result(0, "ruff v0.1\n")})
    install.main([], runner)
    assert not runner.ran("uv", "tool", "uninstall")


def test_uv_s_own_words_are_shown_when_the_install_fails(capsys):
    runner = FakeRunner(answers={"uv tool install": install.Result(2, "error: No space left on device")})
    assert install.main([], runner) == 1
    assert "No space left on device" in capsys.readouterr().out


LOCKED = "error: failed to remove thanhtan.exe: Access is denied. (os error 5)"
LISTED = "4242 thanhtan C:\\Users\\T\\.local\\bin\\thanhtan.exe\n"


def windows_runner(say_yes: bool) -> FakeRunner:
    attempts = []

    def tool(args):
        attempts.append(args)
        return install.Result(2, LOCKED) if len(attempts) == 1 else install.Result(0, "")

    runner = FakeRunner(answers={"uv tool install": tool, "powershell -NoProfile -Command Get-Process": install.Result(0, LISTED)})
    runner.windows = True
    runner.asked = []
    runner.ask = lambda question: runner.asked.append(question) or say_yes
    return runner


def test_on_windows_the_locking_processes_are_named_and_stopped_when_the_person_agrees(capsys):
    runner = windows_runner(say_yes=True)
    assert install.main([], runner) == 0
    assert runner.asked and "1 process" in runner.asked[0]
    assert runner.ran("powershell", "-NoProfile", "-Command", "Stop-Process -Force -Id 4242")
    assert len(runner.ran("uv", "tool", "install")) == 2


def test_on_windows_nothing_is_stopped_without_a_yes(capsys):
    runner = windows_runner(say_yes=False)
    assert install.main([], runner) == 1
    out = capsys.readouterr().out
    assert "4242 thanhtan" in out and "Access is denied" in out
    assert not [call for call in runner.calls if "Stop-Process" in " ".join(call)]
