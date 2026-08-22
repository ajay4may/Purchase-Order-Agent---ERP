"""MIME and extension routing for extraction."""

from __future__ import annotations

from pathlib import Path

from app.errors import UnsupportedFormatError
from app.extractors.base import DocumentExtractor
from app.models import RawDocument

OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heif"}
NATIVE_EXTENSIONS = {".docx", ".xlsx", ".xls", ".csv", ".msg", ".eml", ".txt"}
OCR_MIME_PREFIXES = ("image/",)
OCR_MIME_TYPES = {"application/pdf"}


class ExtractionRouter:
    def __init__(
        self,
        ocr_extractor: DocumentExtractor,
        native_extractor: DocumentExtractor,
    ) -> None:
        self._ocr = ocr_extractor
        self._native = native_extractor

    async def extract(self, file_name: str, mime_type: str, content: bytes) -> RawDocument:
        extension = Path(file_name).suffix.lower()
        normalized_mime = mime_type.lower().split(";", 1)[0].strip()
        if extension in OCR_EXTENSIONS or normalized_mime in OCR_MIME_TYPES:
            return await self._ocr.extract(file_name, normalized_mime, content)
        if normalized_mime.startswith(OCR_MIME_PREFIXES):
            return await self._ocr.extract(file_name, normalized_mime, content)
        if extension in NATIVE_EXTENSIONS or self._is_native_mime(normalized_mime):
            return await self._native.extract(file_name, normalized_mime, content)
        raise UnsupportedFormatError(
            f"Unsupported file type for {file_name}: {normalized_mime or 'unknown'}"
        )

    @staticmethod
    def _is_native_mime(mime_type: str) -> bool:
        return mime_type.startswith("text/") or mime_type in {
            "application/csv",
            "application/vnd.ms-excel",
            "application/vnd.ms-outlook",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "message/rfc822",
        }
