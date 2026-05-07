from __future__ import annotations


class BackendError(Exception):
    """Base class for expected backend failures."""


class RunRequestError(BackendError):
    """Raised when a run payload cannot be parsed into the backend contract."""


class GraphValidationError(BackendError):
    """Raised when a graph cannot safely execute."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


class NodeExecutionError(BackendError):
    """Raised when a node callable fails or returns invalid data."""

