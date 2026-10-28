"""What a person confirmed in the project documents, kept as hashes in ``.ThanhTan/project/confirmations.json``.

A document (or a part of one: the mission, a roadmap item) is confirmed while its text still hashes to what the person
confirmed. Nothing is written into the document itself, so an agent that rewrites it cannot leave a "confirmed" mark
behind: any change makes it unconfirmed again, and writing back the very same text makes it confirmed again.
Only thanhtan writes this file (the hook keeps agents out of ``.ThanhTan/``).
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from thanhtan.constants import CONFIRMATIONS_FILE, ENCODING, PROJECT_DIR, SCHEMA_VERSION
from thanhtan.fsutil import write_text_atomic
from thanhtan.mdutil import normalize_newlines

_CONFIRMED = "confirmed"
_REMOVED = "removed"
_VERSION = "schema_version"
_JSON_INDENT = 2


def normalized(text: str) -> str:
    """Text without carriage returns, trailing white space on each line and blank lines around it."""
    return "\n".join(line.rstrip() for line in normalize_newlines(text).split("\n")).strip()


def digest(text: str) -> str:
    return hashlib.sha256(normalized(text).encode(ENCODING)).hexdigest()


def project_path(workspace_dir: Path, name: str) -> Path:
    return workspace_dir / PROJECT_DIR / name


@dataclass
class Confirmations:
    """The store. ``confirmed`` maps a key (``mission``, ``profile``, ``architecture``, ``R3``) to a hash;
    ``removed`` lists the confirmed roadmap items an agent has since taken out of the roadmap."""

    workspace_dir: Path
    confirmed: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, workspace_dir: Path) -> "Confirmations":
        path = project_path(workspace_dir, CONFIRMATIONS_FILE)
        store = cls(workspace_dir)
        if not path.is_file():
            return store
        try:
            data = json.loads(path.read_text(encoding=ENCODING))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return store  # an unreadable store confirms nothing
        if isinstance(data, dict):
            confirmed = data.get(_CONFIRMED)
            removed = data.get(_REMOVED)
            if isinstance(confirmed, dict):
                store.confirmed = {str(key): str(value) for key, value in confirmed.items() if isinstance(value, str)}
            if isinstance(removed, list):
                store.removed = [str(code) for code in removed]
        return store

    def is_confirmed(self, key: str, current_text: str) -> bool:
        return self.confirmed.get(key) == digest(current_text)

    def confirm(self, key: str, current_text: str) -> None:
        self.confirmed[key] = digest(current_text)

    def forget(self, key: str) -> None:
        self.confirmed.pop(key, None)

    def mark_removed(self, code: str) -> None:
        if code not in self.removed:
            self.removed.append(code)

    def clear_removed(self, code: str) -> None:
        self.removed = [item for item in self.removed if item != code]

    def save(self) -> None:
        path = project_path(self.workspace_dir, CONFIRMATIONS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {_VERSION: SCHEMA_VERSION, _CONFIRMED: dict(sorted(self.confirmed.items())), _REMOVED: self.removed}
        write_text_atomic(path, json.dumps(data, indent=_JSON_INDENT, ensure_ascii=False) + "\n")
