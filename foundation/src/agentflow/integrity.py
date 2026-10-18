"""``integrity.json``: the hash of the state agentflow last wrote, and of every approval checklist it generated.

``task new``, ``task advance`` and ``task approve`` compare ``state.json`` with it first, so a hand edit of the state
is caught before it is acted on. A person takes an edit they have read with ``agentflow state accept``.
This is a tripwire for a hand that does not know about it, not a lock: whoever can run code as the user can rewrite
both files, which is why the hook also keeps an audit log and why the limits are written down.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentflow import audit
from agentflow.constants import DECISIONS_DIR, ENCODING, INTEGRITY_FILE, MARKDOWN_SUFFIX, STATE_FILE, ExitCode
from agentflow.errors import AgentflowError
from agentflow.fsutil import write_text_atomic

STATE_KEY = "state_sha256"
CHECKLISTS_KEY = "checklists"
ACCEPTED_KEY = "accepted_at"
ACCEPT_HINT = 'a person who has looked at the change runs `agentflow state accept --reason "..."`'
ACCEPT_SUFFIX = "-state-accept"
NOTHING_TO_ACCEPT = "nothing to accept: state.json matches integrity.json and the audit log shows no write to it"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Verification:
    warning: str | None = None


class Integrity:
    def __init__(self, workspace_dir: Path) -> None:
        self.dir = workspace_dir
        self.path = workspace_dir / INTEGRITY_FILE
        self.state_path = workspace_dir / STATE_FILE

    # ------------------------------------------------------------ the file

    def load(self) -> dict[str, Any] | None:
        """``None`` when the file does not exist; an error when it exists but cannot be read."""
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text(encoding=ENCODING))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise AgentflowError(f"{self.path.name} cannot be read ({exc}); {ACCEPT_HINT}", ExitCode.INTEGRITY_FAILED) from exc
        if not isinstance(data, dict) or not isinstance(data.get(STATE_KEY), str):
            raise AgentflowError(f"{self.path.name} is not in the form agentflow writes; {ACCEPT_HINT}", ExitCode.INTEGRITY_FAILED)
        return data

    def _write(self, data: dict[str, Any]) -> None:
        write_text_atomic(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _current(self) -> dict[str, Any]:
        try:
            data = self.load()
        except AgentflowError:
            data = None  # a save overwrites what could not be read: the check has already refused it
        return data or {CHECKLISTS_KEY: {}}

    def record_state(self, digest: str) -> None:
        data = self._current()
        data[STATE_KEY] = digest
        data.setdefault(CHECKLISTS_KEY, {})
        self._write(data)

    def checklist(self, key: str) -> dict[str, str] | None:
        try:
            data = self.load()
        except AgentflowError:
            return None
        return None if data is None else data.get(CHECKLISTS_KEY, {}).get(key)

    def accepted_at(self) -> str | None:
        try:
            data = self.load()
        except AgentflowError:
            return None
        return None if data is None else data.get(ACCEPTED_KEY)

    def set_checklist(self, key: str, record: dict[str, str]) -> None:
        data = self._current()
        data.setdefault(STATE_KEY, self.current_digest() or "")
        data.setdefault(CHECKLISTS_KEY, {})[key] = record
        self._write(data)

    def current_digest(self) -> str | None:
        return sha256_hex(self.state_path.read_bytes()) if self.state_path.is_file() else None

    # ------------------------------------------------------------ checking

    def verify(self, has_tasks: bool) -> Verification:
        """Raise when ``state.json`` is not what agentflow last wrote. A workspace without the file starts one."""
        digest = self.current_digest()
        data = self.load()
        if data is None:
            if digest is not None:
                self.record_state(digest)
            if not has_tasks:
                return Verification()
            return Verification(
                f"{INTEGRITY_FILE} was missing, so it was started from the current {STATE_FILE}: nothing earlier could be checked"
            )
        if digest is not None and data[STATE_KEY] != digest:
            raise AgentflowError(
                f"{STATE_FILE} was changed outside agentflow (it does not match {INTEGRITY_FILE}); {ACCEPT_HINT}",
                ExitCode.INTEGRITY_FAILED,
            )
        return Verification()

    # ------------------------------------------------------------ a person accepts

    def accept(self, reason: str, at: str) -> Path | None:
        """For a person: take ``state.json`` as it is and record why. ``None`` when there was nothing to accept."""
        if not reason.strip():
            raise AgentflowError("give the reason you accept the change: --reason \"...\"", ExitCode.INVALID_INPUT)
        digest = self.current_digest()
        data = None
        try:
            data = self.load()
        except AgentflowError:
            pass
        previous = None if data is None else data[STATE_KEY]
        unacknowledged = audit.evidence(self.dir, None, None if data is None else data.get(ACCEPTED_KEY), None)
        if data is not None and previous == digest and not unacknowledged:
            return None
        lines = [
            "# state accepted by a person",
            "",
            f"- Time: {at}",
            f"- Reason: {reason.strip()}",
            f"- {STATE_FILE} sha256 before: {previous or 'unknown'}",
            f"- {STATE_FILE} sha256 now: {digest or 'missing'}",
            "",
            "## Calls in the audit log that could have written the state or a checklist",
            *([f"- {e.at} {e.tool}: {e.target}" for e in unacknowledged] or ["- none"]),
            "",
            f"## {STATE_FILE} as accepted",
            "",
            "```json",
            self.state_path.read_text(encoding=ENCODING).rstrip("\n") if self.state_path.is_file() else "",
            "```",
        ]
        stamp = "".join(ch for ch in at if ch.isalnum())
        path = self.dir / DECISIONS_DIR / f"{stamp}{ACCEPT_SUFFIX}{MARKDOWN_SUFFIX}"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, "\n".join(lines) + "\n")
        fresh = data or {CHECKLISTS_KEY: {}}
        fresh[STATE_KEY] = digest or ""
        fresh[ACCEPTED_KEY] = at
        self._write(fresh)
        return path
