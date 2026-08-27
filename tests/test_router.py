from __future__ import annotations

import pytest
from conftest import FakeExtractor

from app.errors import UnsupportedFormatError
from app.extractors.router import ExtractionRouter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "mime_type"),
    [
        ("scan.pdf", "application/pdf"),
        ("photo.jpg", "image/jpeg"),
        ("rotated.tiff", "image/tiff"),
    ],
)
async def test_ocr_formats_route_to_document_intelligence(file_name: str, mime_type: str) -> None:
    ocr = FakeExtractor()
    native = FakeExtractor()
    await ExtractionRouter(ocr, native).extract(file_name, mime_type, b"content")
    assert len(ocr.calls) == 1
    assert native.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "mime_type"),
    [
        (
            "order.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("legacy.xls", "application/vnd.ms-excel"),
        ("message.msg", "application/vnd.ms-outlook"),
        (
            "order.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("lines.csv", "text/csv"),
    ],
)
async def test_native_formats_route_to_native_parser(file_name: str, mime_type: str) -> None:
    ocr = FakeExtractor()
    native = FakeExtractor()
    await ExtractionRouter(ocr, native).extract(file_name, mime_type, b"content")
    assert len(native.calls) == 1
    assert ocr.calls == []


@pytest.mark.asyncio
async def test_unsupported_format_is_explicit() -> None:
    with pytest.raises(UnsupportedFormatError):
        await ExtractionRouter(FakeExtractor(), FakeExtractor()).extract(
            "archive.zip", "application/zip", b"content"
        )
