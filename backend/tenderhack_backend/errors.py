from __future__ import annotations


class DomainError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        retryable: bool = False,
        current_case_version: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.current_case_version = current_case_version


def not_found() -> DomainError:
    return DomainError("NOT_FOUND", "Ресурс не найден", status_code=404)
