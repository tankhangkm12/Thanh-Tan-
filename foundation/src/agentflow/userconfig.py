"""Per-user settings, outside every repository: ``~/.ThanhTan/user.yaml`` (or under ``AGENTFLOW_HOME``)."""

from collections.abc import Mapping
from pathlib import Path

import yaml

from agentflow.constants import (
    DEFAULT_KNOWLEDGE_DIR_NAME,
    ENCODING,
    USER_CONFIG_FILE,
    UserConfigKey,
)
from agentflow.fsutil import write_text_atomic
from agentflow.projectlocator import user_dir


def _load(environ: Mapping[str, str] | None) -> dict:
    path = user_dir(environ) / USER_CONFIG_FILE
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding=ENCODING))
    except (yaml.YAMLError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def knowledge_dir(environ: Mapping[str, str] | None = None) -> Path:
    """The person's knowledge store: ``knowledge_dir`` in the user config, else ``~/knowledge``."""
    configured = _load(environ).get(UserConfigKey.KNOWLEDGE_DIR)
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser()
    return Path.home() / DEFAULT_KNOWLEDGE_DIR_NAME


def save_knowledge_dir(path: Path, environ: Mapping[str, str] | None = None) -> None:
    data = _load(environ)
    data[UserConfigKey.KNOWLEDGE_DIR.value] = str(path)
    target = user_dir(environ) / USER_CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(target, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
