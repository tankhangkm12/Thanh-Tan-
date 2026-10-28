"""Path globs: ``*`` stays inside a folder, ``**`` crosses folders."""

import re
from collections.abc import Sequence


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Regex for a path glob: ``*`` stays inside a folder, ``**`` crosses folders."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def select_files(files: Sequence[str], globs: Sequence[str]) -> list[str]:
    """``files`` that match any of ``globs`` (all of them when there are no globs)."""
    if not globs:
        return list(files)
    patterns = [glob_regex(glob) for glob in globs]
    return [f for f in files if any(p.match(f) for p in patterns)]
