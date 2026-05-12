from __future__ import annotations


class BackendError(Exception):
    pass


class RunRequestError(BackendError):
    pass


class GraphValidationError(BackendError):
    pass


class NodeExecutionError(BackendError):
    pass
