"""The audit log of the pre-tool hook: which tool calls touched the files that carry a person's approval.

A line is added to ``.ThanhTan/audit.jsonl`` for every call whose path or command *mentions* a protected name. The log
is a witness, not a lock: ``task approve`` refuses when it holds a call that was let through and could have written
the step's checklist or the state. Hashes are the main layer; this one catches a hand that the hashes would miss.
"""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agentflow.constants import AUDIT_FILE, ENCODING, MARKDOWN_SUFFIX

TARGET_LIMIT = 300
_CONTEXT_BEFORE = 100
WRITE_KIND = "write"
SHELL_KIND = "shell"
ALLOW = "allow"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

PROTECTED = re.compile(
    r"state\.json|STATE\.md|integrity\.json|approve-[\w.\-]*\.md|locked-files\.json|confirmations\.json|verify-red\.json|tests-pass\.json", re.IGNORECASE
)
_STATE_FILES = re.compile(r"state\.json|integrity\.json", re.IGNORECASE)

# A command that could write: a redirect (not `2>&1`, `2>/dev/null`), a program that writes, or an interpreter that runs code.
_REDIRECT = re.compile(r"(?<![\d&<>=\-])>{1,2}(?!&)")
_WRITERS = re.compile(
    r"(?<![\w\-])(tee|cp|mv|rm|dd|truncate|install|ln|Set-Content|Add-Content|Out-File|Remove-Item|Copy-Item|Move-Item|New-Item|Clear-Content)(?![\w\-])",
    re.IGNORECASE,
)
_SED_IN_PLACE = re.compile(r"(?<![\w\-])sed\s+(?:\S+\s+)*?(?:-[a-zA-Z]*i|--in-place)", re.IGNORECASE)
_RUNTIMES = re.compile(r"(?<![\w\-])(python[\d.]*|py|node|nodejs|perl|ruby|php|deno|bun)(?:\.exe)?(?![\w\-])", re.IGNORECASE)
_SHELLS_WITH_CODE = re.compile(
    r"(?<![\w\-])(bash|sh|zsh|pwsh|powershell|cmd)(?:\.exe)?\s+(?:\S+\s+)*?(-c|-Command|-e|/c)(?![\w\-])", re.IGNORECASE
)


@dataclass(frozen=True)
class AuditEntry:
    at: str
    cli: str
    tool: str
    kind: str
    target: str
    decision: str

    @property
    def could_write(self) -> bool:
        """A file tool, or a command that has a redirect, a writing program or an interpreter in it."""
        if self.kind == WRITE_KIND:
            return True
        text = self.target
        return bool(
            _REDIRECT.search(text)
            or _WRITERS.search(text)
            or _SED_IN_PLACE.search(text)
            or _RUNTIMES.search(text)
            or _SHELLS_WITH_CODE.search(text)
        )


def now() -> str:
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def mentions_protected(text: str) -> bool:
    return PROTECTED.search(text) is not None


def shorten(text: str) -> str:
    """At most ``TARGET_LIMIT`` characters, cut around the first protected name so it stays visible."""
    if len(text) <= TARGET_LIMIT:
        return text
    found = PROTECTED.search(text)
    start = max(0, found.start() - _CONTEXT_BEFORE) if found else 0
    return text[start : start + TARGET_LIMIT]


def record(workspace_dir: Path, cli: str, tool: str | None, kind: str, target: str, decision: str) -> None:
    """Append one line. Never raises: a log that cannot be written must not stop a hook."""
    if not mentions_protected(target):
        return
    row = {"at": now(), "cli": cli, "tool": tool or "", "kind": kind, "target": shorten(target), "decision": decision}
    try:
        with (workspace_dir / AUDIT_FILE).open("a", encoding=ENCODING) as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (OSError, ValueError):
        return


def entries(workspace_dir: Path) -> Iterator[AuditEntry]:
    """Every readable line of the log; a damaged line is skipped."""
    try:
        text = (workspace_dir / AUDIT_FILE).read_text(encoding=ENCODING)
    except (OSError, UnicodeDecodeError):
        return
    for line in text.splitlines():
        try:
            data = json.loads(line)
            yield AuditEntry(*(str(data[key]) for key in ("at", "cli", "tool", "kind", "target", "decision")))
        except (ValueError, KeyError, TypeError):
            continue


def evidence(workspace_dir: Path, generated: str | None, accepted_at: str | None, step_id: str | None) -> list[AuditEntry]:
    """Calls that were let through, could have written, and touched the checklist of ``step_id`` (any step when
    ``None``), ``state.json`` or ``integrity.json`` after ``generated`` and after the last ``state accept``."""
    checklist = re.compile(rf"approve-{re.escape(step_id)}{re.escape(MARKDOWN_SUFFIX)}" if step_id else r"approve-[\w.\-]*\.md", re.IGNORECASE)
    found = []
    for entry in entries(workspace_dir):
        if entry.decision != ALLOW or not entry.could_write:
            continue
        if generated is not None and entry.at < generated:
            continue
        if accepted_at is not None and entry.at <= accepted_at:
            continue
        if _STATE_FILES.search(entry.target) or checklist.search(entry.target):
            found.append(entry)
    return found
