"""Which paths a git command takes away, renames or overwrites with another commit's content.

Used by the guard to keep agents from changing locked files through git. Restoring a file from the index or from HEAD
(``git restore f``, ``git checkout -- f``) undoes a change and is left alone.
"""

import re

_OPTION = "-"
_END_OF_OPTIONS = "--"
_REMOVES = frozenset({"rm", "mv"})
_SOURCE_FLAGS = frozenset({"-s", "--source"})
_CHECKOUT, _RESTORE = "checkout", "restore"
# `git checkout <ref> -- <paths>` read as text: a ref such as `stash@{0}` is cut up by the tokenizer of the guard.
_CHECKOUT_FROM_REF = re.compile(r"\bgit\b[^;&|\n]*?\bcheckout\b(?P<ref>[^;&|\n]*?)\s--\s+(?P<paths>[^;&|\n]+)")
_A_WORD = re.compile(r"[^\s-]")


def touched_paths(subcommand: str, rest: list[str]) -> list[str]:
    """Paths of ``git <subcommand> <rest>`` that it removes, renames or overwrites from elsewhere."""
    if subcommand in _REMOVES:
        return [arg for arg in rest if not arg.startswith(_OPTION)]
    if subcommand == _CHECKOUT:
        if _END_OF_OPTIONS in rest:
            at = rest.index(_END_OF_OPTIONS)
            has_ref = any(not arg.startswith(_OPTION) for arg in rest[:at])
            return rest[at + 1 :] if has_ref else []
        positional = [arg for arg in rest if not arg.startswith(_OPTION)]
        return positional[1:] if len(positional) >= 2 else []
    if subcommand == _RESTORE:
        from_elsewhere = False
        skip = False
        paths: list[str] = []
        for arg in rest:
            if skip:
                skip = False
            elif arg in _SOURCE_FLAGS:
                from_elsewhere, skip = True, True
            elif arg.startswith("--source="):
                from_elsewhere = True
            elif not arg.startswith(_OPTION):
                paths.append(arg)
        return paths if from_elsewhere else []
    return []


def checkout_paths_in_text(command: str) -> list[str]:
    """Paths after ``--`` in a ``git checkout <ref> -- <paths>`` found anywhere in the text of a command."""
    found: list[str] = []
    for match in _CHECKOUT_FROM_REF.finditer(command):
        if _A_WORD.search(match.group("ref")):
            found += match.group("paths").split()
    return found
