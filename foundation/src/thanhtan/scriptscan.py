"""Find calls of ``thanhtan`` in the text of a script, without running or parsing it.

The guard uses it for text an interpreter runs (a here-document fed to ``python``, ``node -e "..."``, a pipe into
``perl``). It is a reading aid, not a parser: it looks for the word ``thanhtan`` (or ``agentflow``, its name before 1.0.0) and then for the words of a command
(``task approve``) among the words that follow it, so ``subprocess.run(["thanhtan", "task", "approve"])``,
``os.system('uv run thanhtan task cancel')`` and ``main(['task', 'approve'])`` after an import of thanhtan are all
found. A script that only mentions the words (``print('thanhtan task approve')``) is found too; for a guard that
errs towards asking a person, that is the right side to be wrong on.
"""

import re
from collections.abc import Iterable

_THANHTAN = re.compile(r"(?<![\w-])(?:thanhtan|agentflow)(?![\w-])", re.IGNORECASE)
# A word that starts with a letter and does not continue an option (`--suppress`) or an identifier (`__version__`).
_WORD = re.compile(r"(?<![\w-])[A-Za-z][\w-]*")
# A call may be spread over several lines: ``["thanhtan",\n "task",\n "approve"]``.
_FOLLOWING_LINES = 5


def mentioned_commands(text: str, commands: Iterable[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """The commands (each a tuple of words) whose words follow a mention of ``thanhtan`` in ``text``."""
    lines = text.splitlines()
    wanted = list(commands)
    found: list[tuple[str, ...]] = []
    for number, line in enumerate(lines):
        for match in _THANHTAN.finditer(line):
            rest = " ".join([line[match.end() :], *lines[number + 1 : number + 1 + _FOLLOWING_LINES]])
            words = _WORD.findall(rest)
            found += [command for command in wanted if command not in found and _contains(words, command)]
    return found


def _contains(words: list[str], command: tuple[str, ...]) -> bool:
    size = len(command)
    return any(tuple(words[start : start + size]) == command for start in range(len(words) - size + 1))
