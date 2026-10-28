"""Load the JSON Schemas shipped with thanhtan and validate data against them."""

import json
from functools import cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

from thanhtan.constants import ENCODING, PACKAGE_NAME, SCHEMAS_DIR

ROOT_LOCATION = "<root>"
PATH_SEPARATOR = "/"


@cache
def load_schema(file_name: str) -> dict[str, Any]:
    text = files(PACKAGE_NAME).joinpath(SCHEMAS_DIR, file_name).read_text(encoding=ENCODING)
    return json.loads(text)


def schema_errors(data: Any, file_name: str) -> list[str]:
    """Readable ``location: message`` lines; an empty list means ``data`` is valid."""
    validator = Draft202012Validator(load_schema(file_name))
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    return [f"{_location(error.absolute_path)}: {error.message}" for error in errors]


def _location(path: Any) -> str:
    parts = [str(part) for part in path]
    return PATH_SEPARATOR.join(parts) if parts else ROOT_LOCATION
