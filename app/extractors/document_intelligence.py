"""Azure AI Document Intelligence Layout OCR adapter."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.identity import DefaultAzureCredential

from app.errors import ConfigurationError, CorruptDocumentError, UpstreamServiceError
from app.models import Evidence, EvidenceSource, RawDocument

logger = logging.getLogger(__name__)


class AzureDocumentIntelligenceExtractor:
    def __init__(self, endpoint: str | None) -> None:
        self._endpoint = endpoint
        self._client: DocumentIntelligenceClient | None = None

    def _get_client(self) -> DocumentIntelligenceClient:
        if not self._endpoint:
            raise ConfigurationError("DOCUMENT_INTELLIGENCE_ENDPOINT is not configured.")
        if self._client is None:
            self._client = DocumentIntelligenceClient(
                endpoint=self._endpoint,
                credential=DefaultAzureCredential(),
            )
        return self._client

    async def extract(self, file_name: str, mime_type: str, content: bytes) -> RawDocument:
        del file_name
        try:
            result = await asyncio.to_thread(self._analyze, mime_type, content)
        except ServiceRequestError as exc:
            raise UpstreamServiceError(
                "DOCUMENT_INTELLIGENCE_UNAVAILABLE",
                "Azure AI Document Intelligence could not be reached.",
            ) from exc
        except HttpResponseError as exc:
            if exc.status_code in {400, 415, 422}:
                raise CorruptDocumentError(
                    "Document Intelligence could not analyze the supplied document."
                ) from exc
            raise UpstreamServiceError(
                "DOCUMENT_INTELLIGENCE_ERROR",
                "Azure AI Document Intelligence returned an error.",
                retryable=exc.status_code in {408, 429, 500, 502, 503, 504},
            ) from exc

        pages: list[str] = []
        evidence: list[Evidence] = []
        contains_handwriting = False
        handwritten_spans = [
            (span.offset, span.offset + span.length)
            for style in result.styles or []
            if getattr(style, "is_handwritten", False)
            for span in style.spans or []
        ]
        for page in result.pages or []:
            page_lines: list[str] = []
            page_number = page.page_number
            for line in page.lines or []:
                page_lines.append(line.content)
                source_type: EvidenceSource = "printed"
                if self._is_handwritten(line, handwritten_spans):
                    source_type = "handwritten"
                    contains_handwriting = True
                evidence.append(
                    Evidence(source_type=source_type, text=line.content, page=page_number)
                )
            pages.append(f"[page {page_number}]\n" + "\n".join(page_lines))

        tables: list[list[list[str | None]]] = []
        for table in result.tables or []:
            matrix: list[list[str | None]] = [
                [None for _ in range(table.column_count)] for _ in range(table.row_count)
            ]
            for cell in table.cells:
                matrix[cell.row_index][cell.column_index] = cell.content
            tables.append(matrix)

        return RawDocument(
            text="\n\n".join(pages) or (result.content or ""),
            tables=tables,
            page_count=len(result.pages or []) or None,
            contains_handwriting=contains_handwriting,
            extracted_with="azure-ai-document-intelligence:prebuilt-layout",
            evidence=evidence,
        )

    def _analyze(self, mime_type: str, content: bytes) -> Any:
        poller = self._get_client().begin_analyze_document(
            "prebuilt-layout",
            body=io.BytesIO(content),
            content_type=mime_type,
        )
        return poller.result()

    @staticmethod
    def _is_handwritten(line: Any, handwritten_spans: list[tuple[int, int]]) -> bool:
        for span in getattr(line, "spans", []) or []:
            start = span.offset
            end = span.offset + span.length
            if any(
                start < handwritten_end and handwritten_start < end
                for handwritten_start, handwritten_end in handwritten_spans
            ):
                return True
        return False
