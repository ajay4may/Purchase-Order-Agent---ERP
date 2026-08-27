from __future__ import annotations

import base64

import pytest
from conftest import FakeExtractor, FakeNormalizer

from app.errors import ParserError
from app.extractors.router import ExtractionRouter
from app.models import ParseRequest
from app.service import DocumentParserService
from app.validation import ArithmeticValidator


def service(extractor: FakeExtractor, normalizer: FakeNormalizer) -> DocumentParserService:
    return DocumentParserService(
        ExtractionRouter(extractor, extractor),
        normalizer,
        ArithmeticValidator(absolute_tolerance=0.02, relative_tolerance=0.005),
        max_file_size_bytes=1024,
    )


@pytest.mark.asyncio
async def test_valid_base64_returns_source_metadata() -> None:
    content = b"synthetic order"
    result = await service(FakeExtractor(), FakeNormalizer()).parse(
        ParseRequest(
            file_name="order.txt",
            mime_type="text/plain",
            content_base64=base64.b64encode(content).decode(),
        )
    )
    assert result.status == "success"
    assert result.source.size_bytes == len(content)
    assert len(result.source.sha256) == 64


@pytest.mark.asyncio
async def test_data_uri_base64_is_accepted() -> None:
    result = await service(FakeExtractor(), FakeNormalizer()).parse(
        ParseRequest(
            file_name="order.txt",
            mime_type="text/plain",
            content_base64="data:text/plain;base64,c3ludGhldGlj",
        )
    )
    assert result.source.size_bytes == 9


@pytest.mark.asyncio
async def test_invalid_base64_has_stable_code() -> None:
    with pytest.raises(ParserError) as error:
        await service(FakeExtractor(), FakeNormalizer()).parse(
            ParseRequest(
                file_name="order.txt",
                mime_type="text/plain",
                content_base64="not-base64!",
            )
        )
    assert error.value.code == "INVALID_BASE64"
    assert error.value.retryable is False


@pytest.mark.asyncio
async def test_file_size_limit_is_enforced() -> None:
    parser = service(FakeExtractor(), FakeNormalizer())
    parser._max_file_size_bytes = 2
    with pytest.raises(ParserError) as error:
        await parser.parse(
            ParseRequest(
                file_name="order.txt",
                mime_type="text/plain",
                content_base64=base64.b64encode(b"too large").decode(),
            )
        )
    assert error.value.code == "FILE_TOO_LARGE"
