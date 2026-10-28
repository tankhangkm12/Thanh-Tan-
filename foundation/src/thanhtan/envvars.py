"""Reading thanhtan's environment variables: ``THANHTAN_*``, or the ``AGENTFLOW_*`` name they had before 1.0.0."""

from collections.abc import Mapping

from thanhtan.constants import ENV_PREFIX, LEGACY_ENV_PREFIX


def legacy_name(name: str) -> str:
    return LEGACY_ENV_PREFIX + name.removeprefix(ENV_PREFIX) if name.startswith(ENV_PREFIX) else name


def get(env: Mapping[str, str], name: str) -> str | None:
    """The value of ``name``, else of its old name; empty values count as unset."""
    return env.get(name) or env.get(legacy_name(name)) or None
