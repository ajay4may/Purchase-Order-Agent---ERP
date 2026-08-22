"""Stable service errors exposed through the typed API contract."""

from __future__ import annotations


class ParserError(Exception):
    """An expected failure that maps to a stable external error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class UnsupportedFormatError(ParserError):
    def __init__(self, message: str) -> None:
        super().__init__("UNSUPPORTED_FORMAT", message, status_code=415)


class CorruptDocumentError(ParserError):
    def __init__(self, message: str) -> None:
        super().__init__("CORRUPT_DOCUMENT", message, status_code=422)


class EncryptedDocumentError(ParserError):
    def __init__(self, message: str) -> None:
        super().__init__("ENCRYPTED_DOCUMENT", message, status_code=422)


class ConfigurationError(ParserError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFIGURATION_ERROR", message, status_code=503)


class UpstreamServiceError(ParserError):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(code, message, retryable=retryable, status_code=502)
