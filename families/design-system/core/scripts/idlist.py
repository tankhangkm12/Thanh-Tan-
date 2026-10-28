"""The ID prefixes shared by the check scripts, loaded from `core/data/ids.yaml` (not run on its own).

    import idlist
    IDS = idlist.load()          # IDS.kinds, IDS.backlink_kinds, IDS.homes, IDS.id_re(), IDS.kind_of("SVC-order")
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ENCODING = "utf-8"
DEFAULT = Path(__file__).resolve().parent.parent / "data" / "ids.yaml"
NAME = r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*"


@dataclass(frozen=True)
class Ids:
    kinds: tuple[str, ...]
    backlink_kinds: tuple[str, ...]
    homes: dict[str, str]
    placeholder_name: str = "[xX]+"

    def id_re(self, kinds: tuple[str, ...] | list[str] | None = None) -> re.Pattern:
        """An ID of one of `kinds` (default: all) not glued to other word characters: `TC-01` is not a `C-01`."""
        chosen = sorted(kinds if kinds is not None else self.kinds, key=len, reverse=True)
        return re.compile(r"(?<![A-Za-z0-9_-])((?:%s)-%s)(?![A-Za-z0-9_])" % ("|".join(map(re.escape, chosen)), NAME))

    def kind_of(self, ident: str) -> str:
        return ident.split("-", 1)[0]

    def is_placeholder(self, ident: str) -> bool:
        """`FR-xx`, `SVC-xxx`: the name is only placeholder letters."""
        return re.fullmatch(self.placeholder_name, ident.split("-", 1)[1] if "-" in ident else "") is not None


def load(path: Path = DEFAULT) -> Ids:
    """Raises ValueError (message in Vietnamese) when the file is unusable."""
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path}: phải là một mapping")

    def names(key: str) -> tuple[str, ...]:
        value = data.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and re.fullmatch(r"[A-Z]+", v) for v in value):
            raise ValueError(f"{path}: {key} phải là danh sách tiền tố chữ hoa (ví dụ FR)")
        if len(set(value)) != len(value):
            raise ValueError(f"{path}: {key} có tiền tố trùng")
        return tuple(value)

    kinds, backlinks = names("kinds"), names("backlink_kinds")
    if set(backlinks) - set(kinds):
        raise ValueError(f"{path}: backlink_kinds có tiền tố không nằm trong kinds: {sorted(set(backlinks) - set(kinds))}")
    homes = data.get("homes")
    if not isinstance(homes, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.endswith(".md") and not v.startswith("/") for k, v in homes.items()):
        raise ValueError(f"{path}: homes phải là {{tiền tố: đường dẫn .md tương đối}}")
    if set(homes) - set(kinds):
        raise ValueError(f"{path}: homes có tiền tố không nằm trong kinds: {sorted(set(homes) - set(kinds))}")
    placeholder = data.get("placeholder_name", "[xX]+")
    try:
        re.compile(placeholder)
    except (re.error, TypeError) as error:
        raise ValueError(f"{path}: placeholder_name không phải regex hợp lệ: {error}") from error
    return Ids(kinds, backlinks, dict(homes), placeholder)
