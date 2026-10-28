"""The per-project workspace: ``<git root>/.ThanhTan/``, kept out of git via ``.git/info/exclude``.

Before 0.8.0 it was called ``.agentflow/``. The first command that finds a project with only the old folder moves it to the
new name (``migrate_legacy_workspace``); a project that has both is refused until a person keeps one.
"""

import sys
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from agentflow.constants import (
    CONFIG_FILE,
    CONFIG_SCHEMA_FILE,
    ENCODING,
    EXCLUDE_ENTRY,
    GIT_EXCLUDE_PATH,
    GIT_PATH_ARGS,
    GIT_TOPLEVEL_ARGS,
    GITKEEP_FILE,
    LEGACY_WORKSPACE_DIR,
    STATE_FILE,
    STATE_MD_FILE,
    WORKFLOW_COPY_FILE,
    WORKSPACE_DIR,
    WORKSPACE_SUBDIRS,
    ExitCode,
)
from agentflow.errors import AgentflowError
from agentflow.fsutil import file_sha256, write_bytes_atomic, write_text_atomic
from agentflow.git import run_git
from agentflow.models import (
    State,
    Workflow,
    WorkflowRef,
    WorkspaceConfig,
    config_from_dict,
    config_to_dict,
)
from agentflow.state import JsonStateStore
from agentflow.validation import schema_errors
from agentflow.workflow import load_workflow

CONFIG_HEADER = "# Managed by agentflow. Run `agentflow init` or `agentflow workflow sync` to change it.\n"
_SLASH = "/"
# Lines in an exclude file that already keep the workspace out of git.
EXCLUDE_EQUIVALENTS = frozenset(
    {EXCLUDE_ENTRY, WORKSPACE_DIR, _SLASH + EXCLUDE_ENTRY, _SLASH + WORKSPACE_DIR}
)


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path

    @property
    def dir(self) -> Path:
        return self.root / WORKSPACE_DIR

    @property
    def state(self) -> Path:
        return self.dir / STATE_FILE

    @property
    def state_md(self) -> Path:
        return self.dir / STATE_MD_FILE

    @property
    def config(self) -> Path:
        return self.dir / CONFIG_FILE

    @property
    def workflow_copy(self) -> Path:
        return self.dir / WORKFLOW_COPY_FILE


@dataclass(frozen=True)
class InitResult:
    paths: WorkspacePaths
    created: tuple[str, ...]
    exclude_added: bool
    workflow_copied: bool


# --------------------------------------------------------------------- git


def git_toplevel(cwd: Path) -> Path:
    result = run_git(cwd, *GIT_TOPLEVEL_ARGS)
    if result.returncode != 0:
        raise AgentflowError(f"not inside a git repository: {cwd}", ExitCode.NOT_GIT_REPO)
    return Path(result.stdout.strip())


def git_exclude_file(root: Path) -> Path:
    """The repository's ``info/exclude`` (resolved by git, so worktrees work too)."""
    result = run_git(root, *GIT_PATH_ARGS, GIT_EXCLUDE_PATH)
    if result.returncode != 0:
        raise AgentflowError(f"cannot locate git exclude file: {result.stderr.strip()}", ExitCode.NOT_GIT_REPO)
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else root / path


def ensure_excluded(exclude_file: Path, entry: str = EXCLUDE_ENTRY) -> bool:
    """Add ``entry`` (by default the workspace) to the exclude file; return True if it was missing."""
    equivalents = EXCLUDE_EQUIVALENTS if entry == EXCLUDE_ENTRY else frozenset({entry, _SLASH + entry})
    existing = exclude_file.read_bytes().decode(ENCODING, errors="replace") if exclude_file.exists() else ""
    if any(line.strip() in equivalents for line in existing.splitlines()):
        return False
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if existing == "" or existing.endswith("\n") else "\n"
    with exclude_file.open("ab") as handle:
        handle.write(f"{separator}{entry}\n".encode(ENCODING))
    return True


# ------------------------------------------------------------------ config


def load_config(paths: WorkspacePaths) -> WorkspaceConfig:
    if not paths.config.is_file():
        raise AgentflowError(
            f"no agentflow workspace in {paths.root} (run `agentflow init --workflow <file>`)", ExitCode.NO_WORKSPACE
        )
    try:
        data = yaml.safe_load(paths.config.read_text(encoding=ENCODING))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AgentflowError(f"{paths.config}: cannot read config: {exc}", ExitCode.INVALID_CONFIG) from exc
    problems = schema_errors(data, CONFIG_SCHEMA_FILE)
    if problems:
        raise AgentflowError(f"{paths.config}: invalid config: {'; '.join(problems)}", ExitCode.INVALID_CONFIG)
    return config_from_dict(data)


def save_config(paths: WorkspacePaths, config: WorkspaceConfig) -> None:
    body = yaml.safe_dump(config_to_dict(config), sort_keys=False, allow_unicode=True)
    write_text_atomic(paths.config, CONFIG_HEADER + body)


# --------------------------------------------------------------- workspace


def migrate_legacy_workspace(root: Path) -> bool:
    """Move ``<root>/.agentflow/`` to ``<root>/.ThanhTan/`` when only the old one is there; True when it was moved."""
    legacy = root / LEGACY_WORKSPACE_DIR
    if not (legacy / CONFIG_FILE).is_file():
        return False
    target = root / WORKSPACE_DIR
    if target.exists():
        raise AgentflowError(
            f"{root} has both {LEGACY_WORKSPACE_DIR}/ (before 0.8.0) and {WORKSPACE_DIR}/: keep one. Usually you delete or "
            f"rename the old {LEGACY_WORKSPACE_DIR}/ after checking that {WORKSPACE_DIR}/ holds your tasks",
            ExitCode.WORKSPACE_CONFLICT,
        )
    try:
        legacy.rename(target)
    except OSError as exc:
        raise AgentflowError(
            f"cannot rename {legacy} to {WORKSPACE_DIR}/ ({exc}). Close the Claude Code and Antigravity sessions that use "
            f"this project (a running session keeps files open on Windows), then run `agentflow status` again",
            ExitCode.WORKSPACE_CONFLICT,
        ) from exc
    try:
        ensure_excluded(git_exclude_file(root))
    except AgentflowError:
        pass  # init adds it; the move itself is what matters
    print(f"agentflow: moved {LEGACY_WORKSPACE_DIR}/ to {WORKSPACE_DIR}/ (the workspace's new name)", file=sys.stderr)
    return True


def find_workspace(cwd: Path) -> WorkspacePaths:
    paths = WorkspacePaths(git_toplevel(cwd))
    migrate_legacy_workspace(paths.root)
    if not paths.config.is_file():
        raise AgentflowError(
            f"no agentflow workspace in {paths.root} (run `agentflow init --workflow <file>`)", ExitCode.NO_WORKSPACE
        )
    return paths


class GitWorkspaceLookup:
    """``WorkspaceLookup`` that asks git for the repository root; unknown or missing directories read as no workspace."""

    def has_workspace(self, directory: Path) -> bool:
        try:
            find_workspace(directory)
        except AgentflowError:
            return False
        return True


def load_workspace_workflow(paths: WorkspacePaths) -> Workflow:
    """The workflow actually in use: the copy inside the workspace."""
    return load_workflow(paths.workflow_copy)


def copy_workflow(source: Path, paths: WorkspacePaths) -> str:
    """Copy the source bytes unchanged into the workspace; return their sha256."""
    write_bytes_atomic(paths.workflow_copy, source.read_bytes())
    return file_sha256(paths.workflow_copy)


def init_workspace(cwd: Path, workflow_path: Path) -> InitResult:
    """Create or complete the workspace. Never overwrites existing state or the workflow copy."""
    paths = WorkspacePaths(git_toplevel(cwd))
    migrate_legacy_workspace(paths.root)
    source = workflow_path.resolve()
    workflow = load_workflow(source)  # fail before touching anything
    existing = load_config(paths) if paths.config.is_file() else None
    if existing is not None and existing.workflow.family != workflow.family:
        raise AgentflowError(
            f"workspace uses family '{existing.workflow.family}', {source} is family '{workflow.family}'",
            ExitCode.WORKFLOW_MISMATCH,
        )

    created: list[str] = []
    for directory in (paths.dir, *(paths.dir / name for name in WORKSPACE_SUBDIRS)):
        if not directory.is_dir():
            directory.mkdir(parents=True)
            created.append(_relative(paths, directory))
        keep = directory / GITKEEP_FILE
        if directory != paths.dir and not keep.exists():
            keep.touch()

    workflow_copied = not paths.workflow_copy.is_file()
    if workflow_copied:
        copy_workflow(source, paths)
        created.append(_relative(paths, paths.workflow_copy))
    copy_sha = file_sha256(paths.workflow_copy)

    if existing is None:
        save_config(paths, WorkspaceConfig(WorkflowRef(workflow.family, str(source), copy_sha)))
        created.append(_relative(paths, paths.config))
    else:
        ref = replace(existing.workflow, source_path=str(source), sha256=copy_sha)
        save_config(paths, replace(existing, workflow=ref))

    store = JsonStateStore(paths.dir, load_workspace_workflow(paths))
    if not paths.state.is_file():
        store.save(State())
        created += [_relative(paths, paths.state), _relative(paths, paths.state_md)]
    elif not paths.state_md.is_file():
        store.write_state_md(store.load())
        created.append(_relative(paths, paths.state_md))
    else:
        store.load()  # validate existing state against the workflow in use

    exclude_added = ensure_excluded(git_exclude_file(paths.root))
    return InitResult(paths, tuple(created), exclude_added, workflow_copied)


def _relative(paths: WorkspacePaths, path: Path) -> str:
    return path.relative_to(paths.root).as_posix()
