"""Application service for one-document parsing."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re

from app.errors import ParserError
from app.extractors.router import ExtractionRouter
from app.models import OrderSuccess, ParseRequest, SourceMetadata
from app.normalizer import OrderNormalizer
from app.validation import ArithmeticValidator, deduplicate_lines

DATA_URI_PATTERN = re.compile(r"^data:[^;]+;base64,", re.IGNORECASE)


class DocumentParserService:
    def __init__(
        self,
        router: ExtractionRouter,
        normalizer: OrderNormalizer,
        validator: ArithmeticValidator,
        *,
        max_file_size_bytes: int,
    ) -> None:
        self._router = router
        self._normalizer = normalizer
        self._validator = validator
        self._max_file_size_bytes = max_file_size_bytes

    async def parse(self, request: ParseRequest) -> OrderSuccess:
        content = self._decode_base64(request.content_base64)
        document = await self._router.extract(request.file_name, request.mime_type, content)
        candidate = await self._normalizer.normalize(document)
        candidate.lines, duplicates = deduplicate_lines(candidate.lines)
        validation = self._validator.validate(candidate, duplicates)
        source = SourceMetadata(
            file_name=request.file_name,
            mime_type=request.mime_type.lower().split(";", 1)[0],
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            page_count=document.page_count,
            sheet_count=document.sheet_count,
            contains_handwriting=document.contains_handwriting,
            extracted_with=document.extracted_with,
        )
        return OrderSuccess(
            **candidate.model_dump(),
            source=source,
            validation=validation,
        )

    def _decode_base64(self, encoded: str) -> bytes:
        payload = DATA_URI_PATTERN.sub("", encoded.strip())
        try:
            content = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ParserError(
                "INVALID_BASE64",
                "content_base64 is not valid base64.",
                status_code=400,
            ) from exc
        if not content:
            raise ParserError("EMPTY_DOCUMENT", "The uploaded document is empty.", status_code=400)
        if len(content) > self._max_file_size_bytes:
            raise ParserError(
                "FILE_TOO_LARGE",
                f"The uploaded document exceeds {self._max_file_size_bytes} bytes.",
                status_code=413,
            )
        return content
