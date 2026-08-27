"""Extractor interface used to isolate Azure and native format readers."""

from __future__ import annotations

from typing import Protocol

from app.models import RawDocument


class DocumentExtractor(Protocol):
    async def extract(self, file_name: str, mime_type: str, content: bytes) -> RawDocument:
        """Extract layout-aware text and tables from one document."""
        ...
