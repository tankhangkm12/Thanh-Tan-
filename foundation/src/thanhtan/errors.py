"""The single exception type thanhtan raises for expected failures."""

from thanhtan.constants import ExitCode


class ThanhTanError(Exception):
    """An expected failure: the CLI prints the message and exits with ``code``."""

    def __init__(self, message: str, code: ExitCode) -> None:
        super().__init__(message)
        self.code = code
