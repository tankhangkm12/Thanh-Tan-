"""The person's own knowledge store, outside every repository, and what moves between it and a workspace.

Only a person runs these (the guard refuses an agent): ``init`` makes the folder, ``pull`` copies chosen files from
it into ``.ThanhTan/knowledge/`` for the agents to read, ``push`` copies a lesson from the workspace back into it.
Agents never write to the store.
"""

import shutil
from pathlib import Path

from thanhtan.conventions import parse_conventions
from thanhtan.constants import (
    CONVENTIONS_FILE,
    ENCODING,
    GITKEEP_FILE,
    KNOWLEDGE_DIR,
    ConventionField,
    ConventionPrefix,
    ExitCode,
    KnowledgePlace,
)
from thanhtan.errors import ThanhTanError

SKELETON_FILES = {
    "index.md": "# Knowledge store\n\nWhere your lessons, patterns and conventions live. Copy what a project needs into it with\n"
    "`thanhtan knowledge pull <file>`; bring a lesson back with `thanhtan knowledge push <file>`.\n",
    CONVENTIONS_FILE: "# My conventions\n\nRules you want in every project, as `### KC-01 - title` with check/source/description lines\n"
    "(the same format as a project's conventions.md).\n",
    "sources.md": "# Sources\n\nBooks, articles and documents these notes come from.\n",
}
SKELETON_DIRS = ("lessons", "patterns", "semgrep")


def init_store(store: Path) -> list[str]:
    """Create the store's skeleton; what already exists is left alone. Returns what was created."""
    created: list[str] = []
    store.mkdir(parents=True, exist_ok=True)
    for name, text in SKELETON_FILES.items():
        path = store / name
        if not path.exists():
            path.write_text(text, encoding=ENCODING)
            created.append(name)
    for name in SKELETON_DIRS:
        folder = store / name
        if not folder.exists():
            folder.mkdir()
            (folder / GITKEEP_FILE).touch()
            created.append(f"{name}/")
    return created


def _require_store(store: Path) -> Path:
    if not store.is_dir():
        raise ThanhTanError(f"no knowledge store at {store}: run `thanhtan knowledge init` first", ExitCode.INVALID_INPUT)
    return store.resolve()


def _inside(root: Path, path: Path) -> bool:
    return path == root or root in path.parents


def pull_files(store: Path, workspace_dir: Path, names: list[str]) -> list[Path]:
    """Copy files of the store into ``.ThanhTan/knowledge/``, keeping their place. All or nothing."""
    root = _require_store(store)
    chosen: list[tuple[Path, Path]] = []
    for name in names:
        given = Path(name)
        source = (given if given.is_absolute() else root / given).resolve()
        if not _inside(root, source):
            raise ThanhTanError(f"'{name}' is not inside the knowledge store ({root})", ExitCode.INVALID_INPUT)
        if not source.is_file():
            raise ThanhTanError(f"no file '{name}' in the knowledge store", ExitCode.INVALID_INPUT)
        chosen.append((source, workspace_dir / KNOWLEDGE_DIR / source.relative_to(root)))
    for source, target in chosen:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return [target for _, target in chosen]


def push_file(store: Path, workspace_dir: Path, file: Path, place: str) -> Path:
    """Copy a file of the workspace (a lesson) into the store; an existing file is never replaced."""
    root = _require_store(store)
    try:
        folder = KnowledgePlace(place)
    except ValueError:
        raise ThanhTanError(f"'{place}' is not a place for pushed files (one of: {', '.join(KnowledgePlace)})", ExitCode.INVALID_INPUT) from None
    source = file.resolve()
    if not _inside(workspace_dir.resolve(), source) or not source.is_file():
        raise ThanhTanError(f"'{file}' is not a file inside {workspace_dir}", ExitCode.INVALID_INPUT)
    target = root / folder.value / source.name
    if target.exists():
        raise ThanhTanError(f"{target} already exists: rename the file or remove the old one yourself", ExitCode.INVALID_INPUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def add_personal_convention(
    store: Path, title: str, check: str, rule: str | None, description: str, source: str,
    layers: str | None = None, scope: str | None = None,
) -> str:  # fmt: skip
    """Append a convention to the store's ``conventions.md`` and return its code (KC-NN)."""
    root = _require_store(store)
    path = root / CONVENTIONS_FILE
    existing = path.read_text(encoding=ENCODING) if path.is_file() else SKELETON_FILES[CONVENTIONS_FILE]
    numbers = [int(c.code.split("-")[1]) for c in parse_conventions(existing, ConventionPrefix.PERSONAL).conventions]
    code = f"{ConventionPrefix.PERSONAL}-{max(numbers, default=0) + 1:02d}"
    lines = [f"### {code} - {title}", f"- check: {check}"]
    if rule:
        lines.append(f"- rule: {rule}")
    lines += [f"- {key}: {value}" for key, value in ((ConventionField.LAYERS, layers), (ConventionField.SCOPE, scope)) if value]
    lines += [f"- source: {source}", f"- description: {description}"]
    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    path.write_text(existing + separator + "\n".join(lines) + "\n\n", encoding=ENCODING)
    return code
