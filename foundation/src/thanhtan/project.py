"""The project documents under ``.ThanhTan/project/`` and what a person does to them (confirming them).

A person confirms conventions (``PC-01``, a ``status:`` line in the file), and the mission, the profile, the
architecture and roadmap items (``mission``, ``profile``, ``architecture``, ``R3``: a hash in ``confirmations.json``).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from thanhtan.confirmations import Confirmations, project_path
from thanhtan.constants import (
    ENCODING,
    HISTORY_DIR,
    MARKDOWN_SUFFIX,
    PROJECT_DIR,
    ConfirmState,
    ConfirmUnit,
    ConventionPrefix,
    ConventionStatus,
    ExitCode,
    ProjectSection,
)
from thanhtan.conventions import ConventionDoc, parse_conventions, render_conventions, validate_conventions
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic
from thanhtan.mission import mission_warnings, parse_mission
from thanhtan.roadmap import find_item, is_code, items_of, read_roadmap, unconfirmed_codes
from thanhtan.state import utc_now

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_UNITS = {ConfirmUnit.MISSION, ConfirmUnit.PROFILE, ConfirmUnit.ARCHITECTURE}


def conventions_path(workspace_dir: Path) -> Path:
    return workspace_dir / PROJECT_DIR / f"{ProjectSection.CONVENTIONS}{MARKDOWN_SUFFIX}"


def document_path(workspace_dir: Path, section: ProjectSection) -> Path:
    return project_path(workspace_dir, f"{section}{MARKDOWN_SUFFIX}")


def load_conventions(workspace_dir: Path) -> ConventionDoc | None:
    """The project's conventions, or ``None`` when no scout has written them yet."""
    path = conventions_path(workspace_dir)
    if not path.is_file():
        return None
    return parse_conventions(path.read_text(encoding=ENCODING), ConventionPrefix.PROJECT)


@dataclass(frozen=True)
class ConfirmResult:
    confirmed: tuple[str, ...]
    already: tuple[str, ...]
    unconfirmed: tuple[str, ...]
    open_questions: tuple[str, ...]


def confirm_conventions(workspace_dir: Path, codes: Sequence[str], everything: bool) -> ConfirmResult:
    """For a person: mark conventions as confirmed (all of them, or the named ones) and rewrite the file."""
    if bool(codes) == everything:
        raise ThanhTanError("name the conventions to confirm (PC-01 PC-02 ...) or use --all, not both", ExitCode.INVALID_INPUT)
    doc = load_conventions(workspace_dir)
    if doc is None or not doc.conventions:
        raise ThanhTanError("there are no project conventions yet: run the setup skill first", ExitCode.INVALID_INPUT)
    problems = validate_conventions(doc)
    if problems:
        raise ThanhTanError(
            "conventions.md has problems, fix them first:\n- " + "\n- ".join(problems), ExitCode.CONVENTIONS_INVALID
        )
    known = {item.code for item in doc.conventions}
    missing = [code for code in codes if code not in known]
    if missing:
        raise ThanhTanError(f"no such convention: {', '.join(missing)} (have: {', '.join(sorted(known))})", ExitCode.INVALID_INPUT)
    wanted = known if everything else set(codes)
    confirmed: list[str] = []
    already: list[str] = []
    updated = []
    for item in doc.conventions:
        if item.code in wanted and item.status is ConventionStatus.CONFIRMED:
            already.append(item.code)
        elif item.code in wanted:
            confirmed.append(item.code)
            item = replace(item, status=ConventionStatus.CONFIRMED)
        updated.append(item)
    if confirmed:
        write_text_atomic(conventions_path(workspace_dir), render_conventions(replace(doc, conventions=tuple(updated))))
    left = tuple(item.code for item in updated if item.status is ConventionStatus.UNCONFIRMED)
    return ConfirmResult(tuple(confirmed), tuple(already), left, tuple(q.code for q in doc.questions))


def unconfirmed_conventions(workspace_dir: Path) -> tuple[str, ...]:
    """Codes of the project conventions no person has confirmed yet (none when there is no file)."""
    doc = load_conventions(workspace_dir)
    if doc is None:
        return ()
    return tuple(item.code for item in doc.conventions if item.status is ConventionStatus.UNCONFIRMED)


# ------------------------------------------------------------------ history


def keep_previous(workspace_dir: Path, name: str, previous_text: str) -> Path:
    """Save the version of a project document that is about to be replaced, in ``project/history/``."""
    folder = project_path(workspace_dir, HISTORY_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _NON_ALNUM.sub("", utc_now())
    target = folder / f"{name}-{stamp}{MARKDOWN_SUFFIX}"
    counter = 1
    while target.exists():
        counter += 1
        target = folder / f"{name}-{stamp}-{counter}{MARKDOWN_SUFFIX}"
    write_text_atomic(target, previous_text)
    return target


# ------------------------------------------------- what is confirmed, and how


def read_document(workspace_dir: Path, section: ProjectSection) -> str | None:
    path = document_path(workspace_dir, section)
    return path.read_text(encoding=ENCODING) if path.is_file() else None


def mission_state(workspace_dir: Path, confirmations: Confirmations) -> ConfirmState:
    profile = read_document(workspace_dir, ProjectSection.PROFILE)
    mission = parse_mission(profile) if profile is not None else None
    if mission is None:
        return ConfirmState.MISSING
    return ConfirmState.CONFIRMED if confirmations.is_confirmed(ConfirmUnit.MISSION, mission.text) else ConfirmState.UNCONFIRMED


def document_state(workspace_dir: Path, section: ProjectSection, confirmations: Confirmations) -> ConfirmState:
    text = read_document(workspace_dir, section)
    if text is None:
        return ConfirmState.MISSING
    return ConfirmState.CONFIRMED if confirmations.is_confirmed(str(section), text) else ConfirmState.UNCONFIRMED


def roadmap_state(workspace_dir: Path, confirmations: Confirmations) -> tuple[ConfirmState, list[str]]:
    """The roadmap as a whole, and the codes of the items nobody confirmed."""
    if read_roadmap(workspace_dir) is None:
        return ConfirmState.MISSING, []
    left = unconfirmed_codes(items_of(workspace_dir), confirmations)
    return (ConfirmState.UNCONFIRMED if left else ConfirmState.CONFIRMED), left


def status_lines(workspace_dir: Path) -> list[str]:
    """What ``thanhtan project status`` prints: one line per document, then the confirmed items an agent removed."""
    confirmations = Confirmations.load(workspace_dir)
    lines = [
        f"{ConfirmUnit.MISSION}: {mission_state(workspace_dir, confirmations)}",
        f"{ConfirmUnit.PROFILE}: {document_state(workspace_dir, ProjectSection.PROFILE, confirmations)}",
        f"{ConfirmUnit.ARCHITECTURE}: {document_state(workspace_dir, ProjectSection.ARCHITECTURE, confirmations)}",
    ]
    doc = load_conventions(workspace_dir)
    if doc is None:
        lines.append(f"{ConfirmUnit.CONVENTIONS}: {ConfirmState.MISSING}")
    else:
        left = unconfirmed_conventions(workspace_dir)
        lines.append(f"{ConfirmUnit.CONVENTIONS}: {ConfirmState.UNCONFIRMED} ({', '.join(left)})" if left else f"{ConfirmUnit.CONVENTIONS}: {ConfirmState.CONFIRMED}")
    state, left = roadmap_state(workspace_dir, confirmations)
    lines.append(f"{ConfirmUnit.ROADMAP}: {state} ({', '.join(left)})" if left else f"{ConfirmUnit.ROADMAP}: {state}")
    lines += [f"removed: {code} (confirmed)" for code in confirmations.removed]
    return lines


@dataclass(frozen=True)
class ProjectConfirmResult:
    confirmed: tuple[str, ...]
    already: tuple[str, ...]
    # Set when conventions were part of the request.
    conventions: ConfirmResult | None


def confirm_project(workspace_dir: Path, tokens: Sequence[str], everything: bool) -> ProjectConfirmResult:
    """For a person: confirm conventions, the mission, the profile, the architecture and roadmap items by name.

    ``everything`` keeps its old meaning (every convention). A name that cannot be confirmed stops the whole request.
    """
    if bool(tokens) == everything:
        raise ThanhTanError(
            "name what to confirm (PC-01, mission, profile, architecture, R1 ...) or use --all for every convention, not both",
            ExitCode.INVALID_INPUT,
        )
    units = [token for token in tokens if token in _UNITS]
    roadmap_codes = [token for token in tokens if token not in _UNITS and is_code(token)]
    convention_codes = [token for token in tokens if token not in _UNITS and not is_code(token)]
    confirmations = Confirmations.load(workspace_dir)
    texts, problems = _confirmable_texts(workspace_dir, units, roadmap_codes)
    if convention_codes:
        doc = load_conventions(workspace_dir)
        known = {item.code for item in doc.conventions} if doc is not None else set()
        unknown = [code for code in convention_codes if code not in known]
        if unknown:
            problems.append(f"no such convention: {', '.join(unknown)}" + ("" if known else " (this project has no conventions yet)"))
    if problems:
        raise ThanhTanError("; ".join(problems), ExitCode.INVALID_INPUT)
    conventions = confirm_conventions(workspace_dir, convention_codes, everything) if (everything or convention_codes) else None
    confirmed: list[str] = []
    already: list[str] = []
    for token in tokens:
        if token in texts:
            if confirmations.is_confirmed(token, texts[token]):
                already.append(token)
            else:
                confirmations.confirm(token, texts[token])
                confirmed.append(token)
        elif conventions is not None:
            (confirmed if token in conventions.confirmed else already).append(token)
    if everything and conventions is not None:
        confirmed, already = list(conventions.confirmed), list(conventions.already)
    if texts:
        confirmations.save()
    return ProjectConfirmResult(tuple(confirmed), tuple(already), conventions)


def _confirmable_texts(workspace_dir: Path, units: Sequence[str], roadmap_codes: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    problems: list[str] = []
    profile = read_document(workspace_dir, ProjectSection.PROFILE)
    for unit in units:
        if unit == ConfirmUnit.MISSION:
            if profile is None:
                problems.append("there is no profile yet, so there is no mission to confirm (run the setup skill)")
                continue
            found = mission_warnings(profile)
            mission = parse_mission(profile)
            if found or mission is None:
                problems.append("the mission cannot be confirmed yet: " + "; ".join(found))
            else:
                texts[unit] = mission.text
        elif unit == ConfirmUnit.PROFILE:
            if profile is None:
                problems.append("there is no profile yet (run the setup skill)")
            else:
                texts[unit] = profile
        else:
            text = read_document(workspace_dir, ProjectSection.ARCHITECTURE)
            if text is None:
                problems.append("there is no architecture document yet (run the setup skill)")
            else:
                texts[unit] = text
    if roadmap_codes:
        items = items_of(workspace_dir)
        if read_roadmap(workspace_dir) is None:
            problems.append("this project has no roadmap yet (the setup skill proposes one)")
        for code in roadmap_codes:
            item = find_item(items, code) if items else None
            if item is not None:
                texts[code] = item.content
            elif items:
                problems.append(f"no roadmap item {code} (items: {', '.join(i.code for i in items)})")
    return texts, problems
