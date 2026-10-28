"""Lessons a reviewer proposes at the end of a task. They are only proposals: a person decides which go to their store."""

import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from agentflow.constants import ENCODING, LESSONS_DIR, LESSONS_HEADING, MARKDOWN_SUFFIX, TASKS_DIR
from agentflow.fsutil import write_text_atomic

_SECTION = re.compile(r"^##\s+(.*?)\s*$")
_LESSON = re.compile(r"^###\s+(L[0-9]+)\b\s*(?:[—–:-]+\s*)?(.*?)\s*$")


@dataclass(frozen=True)
class Lesson:
    code: str
    title: str
    body: str = ""


def parse_lessons(report: str) -> list[Lesson]:
    """The ``### L1 - title`` entries under ``## Bài học đề xuất``; the section ends at the next ``##`` heading."""
    lessons: list[Lesson] = []
    inside = False
    current: tuple[str, str] | None = None
    body: list[str] = []

    def close() -> None:
        if current is not None:
            lessons.append(Lesson(current[0], current[1], "\n".join(body).strip()))

    for line in report.replace("\r\n", "\n").split("\n"):
        section = _SECTION.match(line)
        if section:
            close()
            current, body = None, []
            inside = section.group(1).strip().lower() == LESSONS_HEADING.lower()
            continue
        if not inside:
            continue
        lesson = _LESSON.match(line)
        if lesson:
            close()
            current, body = (lesson.group(1), lesson.group(2)), []
        elif current is not None:
            body.append(line)
    close()
    return lessons


def lesson_path(workspace_dir: Path, task_id: str, code: str) -> Path:
    return workspace_dir / TASKS_DIR / task_id / LESSONS_DIR / f"{code}{MARKDOWN_SUFFIX}"


def write_lessons(workspace_dir: Path, task_id: str, lessons: Sequence[Lesson]) -> list[Path]:
    """One file per lesson under ``tasks/<task>/lessons/``, replacing what an earlier seal left there."""
    folder = workspace_dir / TASKS_DIR / task_id / LESSONS_DIR
    shutil.rmtree(folder, ignore_errors=True)
    paths: list[Path] = []
    for lesson in lessons:
        path = lesson_path(workspace_dir, task_id, lesson.code)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = f"# {lesson.title}\n\n{lesson.body}\n" if lesson.body else f"# {lesson.title}\n"
        write_text_atomic(path, text)
        paths.append(path)
    return paths


def read_lessons(report_path: Path) -> list[Lesson]:
    return parse_lessons(report_path.read_text(encoding=ENCODING)) if report_path.is_file() else []
