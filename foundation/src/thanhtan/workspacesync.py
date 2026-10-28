"""Carrying a project's workspace to another machine through the person's own private git repository.

The repository is cloned once per machine into ``~/.ThanhTan/store/`` (``thanhtan workspace remote <url>``); each project
has a folder in it, named after the project's ``origin`` (``owner/repo``) unless the person names it. Nothing here ever
pushes to the project's own remote.

``save`` copies ``.ThanhTan/`` into that folder with a git bundle of the task branches and the approval tags (they live
in the project's git, not in the workspace), commits and pushes. ``load`` brings both back on another machine and points
the workflow at the copy of dev-core installed there.

Each save records a fingerprint of the workspace (``save.json``); each machine remembers the fingerprint it last saved or
loaded (``.ThanhTan/sync.json``). That is how it tells the two mistakes apart: ``save`` refuses when someone saved from
another machine since (load first), ``load`` refuses when this machine has work that was never saved. ``--force`` goes on.
"""

import hashlib
import json
import os
import re
import shutil
import socket
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from thanhtan.constants import (
    APPROVAL_TAG_PREFIXES,
    ENCODING,
    LEGACY_WORKSPACE_DIR,
    WORKFLOW_COPY_FILE,
    WORKSPACE_DIR,
    ExitCode,
)
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic
from thanhtan.git import run_git
from thanhtan.projectlocator import user_dir
from thanhtan.workspace import (
    WorkspacePaths,
    ensure_excluded,
    git_exclude_file,
    load_config,
    save_config,
)

STORE_DIR = "store"
MARKER_FILE = "sync.json"  # in the project's workspace: what this machine last saved or loaded
SAVE_FILE = "save.json"  # in the store, next to the copy: who saved it, when, and its fingerprint
BUNDLE_FILE = "transfer.bundle"
ORIGIN = "origin"
DEV_CORE = "dev-core"
_NOT_COPIED = frozenset({MARKER_FILE})
_NAME_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REMOTE_PATH = re.compile(r"[:/](?P<owner>[^/:]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")
# Where the CLIs keep an installed dev-core (its workflow.yaml is the one a loaded workspace should point at).
_PLUGIN_ROOTS = (
    Path(".claude") / "plugins",
    Path(".gemini") / "config" / "plugins",
    Path(".gemini") / "antigravity-cli" / "plugins",
)


@dataclass
class SyncReport:
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _fail(message: str) -> ThanhTanError:
    return ThanhTanError(message, ExitCode.WORKSPACE_SYNC)


def _git(cwd: Path, *args: str, what: str) -> str:
    done = run_git(cwd, *args)
    if done.returncode != 0:
        raise _fail(f"{what} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout


# ------------------------------------------------------------------ the store


def store_dir(environ: Mapping[str, str] | None = None) -> Path:
    return user_dir(environ) / STORE_DIR


def _require_store(environ: Mapping[str, str] | None) -> Path:
    store = store_dir(environ)
    if not (store / ".git").exists():
        raise _fail("no private repository is set up on this machine: run `thanhtan workspace remote <url>` first")
    return store


def set_remote(url: str, environ: Mapping[str, str] | None = None) -> list[str]:
    """Clone the person's repository into the store, or point an existing store at ``url``."""
    if not url.strip():
        raise _fail("give the URL of your private repository")
    store = store_dir(environ)
    if (store / ".git").exists():
        current = run_git(store, "remote", "get-url", ORIGIN)
        if current.returncode == 0 and current.stdout.strip() == url:
            return [f"store: {store} already uses {url}"]
        verb = "set-url" if current.returncode == 0 else "add"
        _git(store, "remote", verb, ORIGIN, url, what=f"git remote {verb}")
        return [f"store: {store} now uses {url}"]
    if store.exists() and any(store.iterdir()):
        raise _fail(f"{store} exists and is not a git repository; move it away first")
    store.parent.mkdir(parents=True, exist_ok=True)
    _git(store.parent, "clone", url, str(store), what=f"git clone {url}")
    return [f"store: cloned {url} into {store}"]


def _has_commits(store: Path) -> bool:
    return run_git(store, "rev-parse", "--verify", "-q", "HEAD").returncode == 0


def _pull(store: Path) -> None:
    remote_heads = run_git(store, "ls-remote", "--heads", ORIGIN)
    if remote_heads.returncode != 0:
        raise _fail(f"cannot reach your private repository: {remote_heads.stderr.strip()}")
    if not remote_heads.stdout.strip():
        return  # an empty repository: nothing to bring in yet
    if not _has_commits(store):
        branch = remote_heads.stdout.split()[1].removeprefix("refs/heads/")
        _git(store, "fetch", ORIGIN, what="git fetch")
        _git(store, "checkout", "-q", "-B", branch, f"{ORIGIN}/{branch}", what="git checkout")
        return
    _git(store, "pull", "-q", "--ff-only", what="git pull (your private repository)")


# ------------------------------------------------------------------ the project's name and fingerprint


def project_name(root: Path, explicit: str | None = None) -> str:
    """``owner/repo`` of the project's ``origin``, else the folder's name; ``explicit`` wins."""
    name = explicit
    if not name:
        origin = run_git(root, "remote", "get-url", ORIGIN)
        found = _REMOTE_PATH.search(origin.stdout.strip()) if origin.returncode == 0 else None
        name = f"{found['owner']}/{found['repo']}" if found else root.name
    parts = name.replace("\\", "/").strip("/").split("/")
    if not parts or any(not _NAME_PART.match(part) for part in parts):
        raise _fail(f"'{name}' cannot name a folder of the store (letters, digits, '.', '_', '-' and '/' only)")
    return "/".join(parts)


def fingerprint(folder: Path, skip: Iterable[str] = (*_NOT_COPIED, BUNDLE_FILE, SAVE_FILE)) -> str:
    """The sha256 of the names and contents of every file of ``folder`` but ``skip`` (at its top level)."""
    skipped = set(skip)
    combined = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        relative = path.relative_to(folder).as_posix()
        if relative in skipped:
            continue
        combined.update(relative.encode(ENCODING) + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return combined.hexdigest()


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding=ENCODING))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ------------------------------------------------------------------ branches and tags


def _refs_to_carry(root: Path, branches: Iterable[str]) -> list[str]:
    refs = [f"refs/heads/{name}" for name in dict.fromkeys(branches) if name and run_git(root, "rev-parse", "--verify", "-q", f"refs/heads/{name}").returncode == 0]
    tags = run_git(root, "for-each-ref", "--format=%(refname)", *(f"refs/tags/{prefix}" for prefix in APPROVAL_TAG_PREFIXES))
    refs += [line for line in tags.stdout.splitlines() if line.strip()]
    return refs


def _restore_refs(root: Path, bundle: Path) -> tuple[list[str], list[str]]:
    """Bring the bundle's branches and tags into the project; one that exists with another commit is left alone."""
    heads = _git(root, "bundle", "list-heads", str(bundle), what="git bundle list-heads")
    current = run_git(root, "symbolic-ref", "-q", "HEAD").stdout.strip()
    restored, kept = [], []
    for line in heads.splitlines():
        sha, _, ref = line.partition(" ")
        ref = ref.strip()
        if not ref.startswith(("refs/heads/", "refs/tags/")):
            continue
        local = run_git(root, "rev-parse", "--verify", "-q", ref)
        have = local.stdout.strip() if local.returncode == 0 else None
        if have == sha:
            continue  # already there
        if have is not None and have != sha:
            kept.append(f"{ref.removeprefix('refs/heads/').removeprefix('refs/tags/')} (this machine has other commits; not changed)")
            continue
        if ref == current:
            kept.append(f"{ref.removeprefix('refs/heads/')} (checked out; switch to another branch and load again)")
            continue
        _git(root, "fetch", "-q", str(bundle), f"{ref}:{ref}", what=f"restoring {ref}")
        restored.append(ref.removeprefix("refs/heads/").removeprefix("refs/tags/"))
    return restored, kept


# ------------------------------------------------------------------ save and load


def _uncommitted(root: Path) -> bool:
    return bool(run_git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip())


def save(
    paths: WorkspacePaths,
    task_branches: Iterable[str],
    *,
    name: str | None = None,
    force: bool = False,
    at: str,
    machine: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> SyncReport:
    store = _require_store(environ)
    _pull(store)
    project = project_name(paths.root, name)
    target = store / project
    marker = _read_json(paths.dir / MARKER_FILE)
    saved = _read_json(target / SAVE_FILE)
    if saved and not force and saved.get("fingerprint") != marker.get("fingerprint"):
        raise _fail(
            f"{project} was saved from {saved.get('machine', 'another machine')} at {saved.get('at', '?')} after this machine "
            "last saved or loaded it: run `thanhtan workspace load` first (or `save --force` to replace that copy)"
        )
    report = SyncReport()
    if _uncommitted(paths.root):
        report.warnings.append("the project has uncommitted changes: they stay on this machine (commit them and save again)")
    print_name = machine or default_machine()
    stamp = fingerprint(paths.dir)
    with tempfile.TemporaryDirectory() as scratch:
        bundle = Path(scratch) / BUNDLE_FILE
        refs = _refs_to_carry(paths.root, task_branches)
        if refs:
            _git(paths.root, "bundle", "create", "-q", str(bundle), *refs, what="git bundle create")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(paths.dir, target, ignore=lambda folder, names: [n for n in names if Path(folder) == paths.dir and n in _NOT_COPIED])
        if refs:
            shutil.copy2(bundle, target / BUNDLE_FILE)
    _write_json(target / SAVE_FILE, {"project": project, "machine": print_name, "at": at, "fingerprint": stamp, "refs": len(refs)})
    _git(store, "add", "-A", what="git add")
    if run_git(store, "diff", "--cached", "--quiet").returncode == 0:
        report.lines.append(f"workspace: {project} is already saved as it is")
    else:
        _git(store, "commit", "-q", "-m", f"save {project} from {print_name} at {at}", what="git commit")
        branch = run_git(store, "symbolic-ref", "--short", "HEAD").stdout.strip() or "main"
        _git(store, "push", "-q", "-u", ORIGIN, branch, what="git push (your private repository)")
        report.lines.append(f"workspace: saved {project} ({len(refs)} branch(es) and tag(s)) to your private repository")
    _write_json(paths.dir / MARKER_FILE, {"fingerprint": stamp, "at": at, "machine": print_name, "action": "save"})
    return report


def load(
    root: Path,
    *,
    name: str | None = None,
    force: bool = False,
    workflow: Path | None = None,
    at: str,
    machine: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Callable[[], Path] = Path.home,
) -> SyncReport:
    store = _require_store(environ)
    _pull(store)
    project = project_name(root, name)
    source = store / project
    saved = _read_json(source / SAVE_FILE)
    if not saved:
        raise _fail(f"nothing is saved for {project} in your private repository (save it on the other machine, or pass --name)")
    paths = WorkspacePaths(root)
    if (root / LEGACY_WORKSPACE_DIR).exists() and not paths.dir.exists():
        raise _fail(f"{root} has an old {LEGACY_WORKSPACE_DIR}/ folder: run `thanhtan status` once to move it, then load")
    if paths.dir.exists() and not force:
        marker = _read_json(paths.dir / MARKER_FILE)
        if not marker:
            raise _fail(f"{root} already has a workspace that was never saved: save it, or `load --force` to replace it")
        if fingerprint(paths.dir) != marker.get("fingerprint"):
            raise _fail("this machine has changes to the workspace that were never saved: save them first, or `load --force` to drop them")
    report = SyncReport()
    bundle = source / BUNDLE_FILE
    if bundle.is_file():
        restored, kept = _restore_refs(root, bundle)
        if restored:
            report.lines.append(f"restored: {', '.join(restored)}")
        report.warnings.extend(f"not restored: {item}" for item in kept)
    if paths.dir.exists():
        shutil.rmtree(paths.dir)
    shutil.copytree(source, paths.dir, ignore=lambda folder, names: [n for n in names if Path(folder) == source and n in (SAVE_FILE, BUNDLE_FILE)])
    ensure_excluded(git_exclude_file(root))
    report.lines.append(f"workspace: loaded {project}, saved from {saved.get('machine', '?')} at {saved.get('at', '?')}")
    report.lines += _repoint_workflow(paths, workflow, home)
    _write_json(paths.dir / MARKER_FILE, {"fingerprint": fingerprint(paths.dir), "at": at, "machine": machine or default_machine(), "action": "load"})
    return report


def _installed_workflows(home: Path) -> list[Path]:
    found: list[Path] = []
    for root in _PLUGIN_ROOTS:
        base = home / root
        if base.is_dir():
            found += [path for path in base.rglob(WORKFLOW_COPY_FILE) if DEV_CORE in path.parts or path.parent.name == "core"]
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def _repoint_workflow(paths: WorkspacePaths, explicit: Path | None, home: Callable[[], Path]) -> list[str]:
    config = load_config(paths)
    current = Path(config.workflow.source_path)
    if explicit is None and current.is_file():
        return []
    candidates = [explicit.resolve()] if explicit is not None else _installed_workflows(home())
    if not candidates or not candidates[0].is_file():
        return [
            f"warning: the workflow it was copied from ({current}) is not on this machine; run "
            "`thanhtan init --workflow <path to dev-core's workflow.yaml>` once"
        ]
    save_config(paths, replace(config, workflow=replace(config.workflow, source_path=str(candidates[0]))))
    return [f"workflow source: {candidates[0]} (run `thanhtan workflow sync` when no task is open, if status says it changed)"]


def status(root: Path, *, name: str | None = None, environ: Mapping[str, str] | None = None) -> list[str]:
    store = store_dir(environ)
    lines = []
    if not (store / ".git").exists():
        return ["store: not set up on this machine (`thanhtan workspace remote <url>`)"]
    remote = run_git(store, "remote", "get-url", ORIGIN).stdout.strip() or "(no remote)"
    project = project_name(root, name)
    lines.append(f"store: {store} -> {remote}")
    saved = _read_json(store / project / SAVE_FILE)
    lines.append(
        f"saved: {project} from {saved.get('machine', '?')} at {saved.get('at', '?')} (as last pulled)" if saved else f"saved: nothing for {project} yet"
    )
    workspace = root / WORKSPACE_DIR
    marker = _read_json(workspace / MARKER_FILE)
    if not workspace.is_dir():
        lines.append("this machine: no workspace")
    elif not marker:
        lines.append("this machine: never saved or loaded")
    else:
        changed = fingerprint(workspace) != marker.get("fingerprint")
        lines.append(f"this machine: last {marker.get('action', '?')} at {marker.get('at', '?')}; " + ("changed since" if changed else "unchanged since"))
    return lines


def default_machine() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname()
