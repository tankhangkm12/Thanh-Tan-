"""Small file helpers: hashing and atomic writes (write a temp file, then replace)."""

import hashlib
import os
from pathlib import Path

from thanhtan.constants import ENCODING, TMP_SUFFIX

_CHUNK_SIZE = 1 << 16


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + TMP_SUFFIX)
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_text_atomic(path: Path, text: str) -> None:
    # Always LF line endings, whatever the platform.
    write_bytes_atomic(path, text.encode(ENCODING))
