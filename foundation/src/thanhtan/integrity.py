"""``integrity.json``: the hash of the state thanhtan last wrote, and of every approval checklist it generated.

``task new``, ``task advance`` and ``task approve`` compare ``state.json`` with it first, so a hand edit of the state
is caught before it is acted on. A person takes an edit they have read with ``thanhtan state accept``.
This is a tripwire for a hand that does not know about it, not a lock: whoever can run code as the user can rewrite
both files, which is why the hook also keeps an audit log and why the limits are written down.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thanhtan import audit
from thanhtan.constants import CONFIG_FILE, DECISIONS_DIR, ENCODING, INTEGRITY_FILE, MARKDOWN_SUFFIX, STATE_FILE, ExitCode
from thanhtan.errors import ThanhTanError
from thanhtan.fsutil import write_text_atomic

STATE_KEY = "state_sha256"
CHECKLISTS_KEY = "checklists"
ACCEPTED_KEY = "accepted_at"
LOCK_KEY = "locked_files_sha256"
LOCK_TASK_KEY = "locked_files_task"
SETTINGS_KEY = "test_settings_sha256"
LOCK_FILE_NAME = "locked-files.json"
ACCEPT_HINT = 'a person who has looked at the change runs `thanhtan state accept --reason "..."`'
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
            raise ThanhTanError(f"{self.path.name} cannot be read ({exc}); {ACCEPT_HINT}", ExitCode.INTEGRITY_FAILED) from exc
        if not isinstance(data, dict) or not isinstance(data.get(STATE_KEY), str):
            raise ThanhTanError(f"{self.path.name} is not in the form thanhtan writes; {ACCEPT_HINT}", ExitCode.INTEGRITY_FAILED)
        return data

    def _write(self, data: dict[str, Any]) -> None:
        write_text_atomic(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _current(self) -> dict[str, Any]:
        try:
            data = self.load()
        except ThanhTanError:
            data = None  # a save overwrites what could not be read: the check has already refused it
        return data or {CHECKLISTS_KEY: {}}

    def record_state(self, digest: str) -> None:
        data = self._current()
        data[STATE_KEY] = digest
        data.setdefault(CHECKLISTS_KEY, {})
        self._write(data)

    def record_lock(self, task_id: str, digest: str) -> None:
        """The hash of the lock file of the task that is going, so a hand edit or a deletion is noticed."""
        data = self._current()
        data.setdefault(STATE_KEY, self.current_digest() or "")
        data[LOCK_KEY], data[LOCK_TASK_KEY] = digest, task_id
        self._write(data)

    def record_settings(self, digest: str) -> None:
        """The hash of the settings that decide what the tests run (``test_command``, ``test_timeout_minutes``)."""
        data = self._current()
        data.setdefault(STATE_KEY, self.current_digest() or "")
        data[SETTINGS_KEY] = digest
        self._write(data)

    def verify_lock(self, task_id: str | None, lock_digest: str | None) -> None:
        data = self.load()
        if data is None or task_id is None or data.get(LOCK_TASK_KEY) != task_id:
            return
        if lock_digest != data.get(LOCK_KEY):
            what = "is missing" if lock_digest is None else "was changed outside thanhtan (it does not match integrity.json)"
            raise ThanhTanError(f"{LOCK_FILE_NAME} of {task_id} {what}; {ACCEPT_HINT}", ExitCode.INTEGRITY_FAILED)

    def verify_settings(self, digest: str) -> None:
        data = self.load()
        if data is None:
            return
        recorded = data.get(SETTINGS_KEY)
        if recorded is None:
            self.record_settings(digest)  # a workspace from before: nothing earlier can be checked
        elif recorded != digest:
            raise ThanhTanError(
                f"{CONFIG_FILE} was changed outside thanhtan: the test_command or test_timeout_minutes setting differs from what "
                f"`thanhtan config set` last wrote; {ACCEPT_HINT}",
                ExitCode.INTEGRITY_FAILED,
            )

    def checklist(self, key: str) -> dict[str, str] | None:
        try:
            data = self.load()
        except ThanhTanError:
            return None
        return None if data is None else data.get(CHECKLISTS_KEY, {}).get(key)

    def accepted_at(self) -> str | None:
        try:
            data = self.load()
        except ThanhTanError:
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
        """Raise when ``state.json`` is not what thanhtan last wrote. A workspace without the file starts one."""
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
            raise ThanhTanError(
                f"{STATE_FILE} was changed outside thanhtan (it does not match {INTEGRITY_FILE}); {ACCEPT_HINT}",
                ExitCode.INTEGRITY_FAILED,
            )
        return Verification()

    # ------------------------------------------------------------ a person accepts

    def accept(self, reason: str, at: str, lock_digest: Callable[[str], str | None] | None = None, settings: str | None = None) -> Path | None:
        """For a person: take ``state.json`` as it is and record why. ``None`` when there was nothing to accept."""
        if not reason.strip():
            raise ThanhTanError("give the reason you accept the change: --reason \"...\"", ExitCode.INVALID_INPUT)
        digest = self.current_digest()
        data = None
        try:
            data = self.load()
        except ThanhTanError:
            pass
        previous = None if data is None else data[STATE_KEY]
        unacknowledged = audit.evidence(self.dir, None, None if data is None else data.get(ACCEPTED_KEY), None)
        extra: list[str] = []
        lock_task = None if data is None else data.get(LOCK_TASK_KEY)
        lock_now = lock_digest(lock_task) if lock_digest is not None and lock_task else None
        if data is not None:
            if lock_task and lock_digest is not None and data.get(LOCK_KEY) != lock_now:
                extra.append(f"- {LOCK_FILE_NAME} of {lock_task} sha256 before: {data.get(LOCK_KEY)}; now: {lock_now or 'missing'}")
            if settings is not None and data.get(SETTINGS_KEY) not in (None, settings):
                extra.append(f"- {CONFIG_FILE} test settings (test_command, test_timeout_minutes) sha256 before: {data.get(SETTINGS_KEY)}; now: {settings}")
        if data is not None and previous == digest and not unacknowledged and not extra:
            return None
        lines = [
            "# state accepted by a person",
            "",
            f"- Time: {at}",
            f"- Reason: {reason.strip()}",
            f"- {STATE_FILE} sha256 before: {previous or 'unknown'}",
            f"- {STATE_FILE} sha256 now: {digest or 'missing'}",
            *extra,
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
        if lock_now is not None:
            fresh[LOCK_KEY] = lock_now
        if settings is not None:
            fresh[SETTINGS_KEY] = settings
        fresh[ACCEPTED_KEY] = at
        self._write(fresh)
        return path
