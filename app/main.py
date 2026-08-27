"""Microsoft Foundry Hosted Agent Responses protocol entry point."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
    TextResponse,
)

from app.config import Settings
from app.errors import ParserError
from app.extractors.document_intelligence import AzureDocumentIntelligenceExtractor
from app.extractors.native import NativeDocumentExtractor
from app.extractors.router import ExtractionRouter
from app.models import ErrorResponse, OrderSuccess, ParseRequest
from app.normalizer import FoundryAgentNormalizer
from app.service import DocumentParserService
from app.telemetry import configure_telemetry
from app.validation import ArithmeticValidator

settings = Settings.from_env()
configure_telemetry(settings.log_level)
logger = logging.getLogger(__name__)

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(default_fetch_history_count=1),
)


@lru_cache(maxsize=1)
def get_service() -> DocumentParserService:
    router = ExtractionRouter(
        AzureDocumentIntelligenceExtractor(settings.document_intelligence_endpoint),
        NativeDocumentExtractor(
            max_uncompressed_bytes=settings.max_file_size_bytes * 8,
        ),
    )
    return DocumentParserService(
        router,
        FoundryAgentNormalizer(
            settings.foundry_project_endpoint,
            settings.model_deployment_name,
        ),
        ArithmeticValidator(
            absolute_tolerance=settings.arithmetic_absolute_tolerance,
            relative_tolerance=settings.arithmetic_relative_tolerance,
        ),
        max_file_size_bytes=settings.max_file_size_bytes,
    )


def parse_responses_input(user_input: str | None) -> ParseRequest:
    if not user_input:
        raise ParserError(
            "INVALID_RESPONSES_INPUT",
            "Responses input must contain a JSON document request.",
            status_code=400,
        )
    try:
        return ParseRequest.model_validate_json(user_input)
    except (TypeError, ValueError) as exc:
        raise ParserError(
            "INVALID_RESPONSES_INPUT",
            "Responses input must be JSON with file_name, mime_type, and content_base64.",
            status_code=400,
        ) from exc


async def process_document_input(user_input: str | None) -> OrderSuccess | ErrorResponse:
    """Return one typed JSON object without leaking exceptions into protocol output."""
    try:
        parse_request = parse_responses_input(user_input)
        return await get_service().parse(parse_request)
    except ParserError as exc:
        logger.warning("document_parse_failed code=%s retryable=%s", exc.code, exc.retryable)
        return ErrorResponse(code=exc.code, message=exc.message, retryable=exc.retryable)
    except Exception:
        logger.exception("unhandled_document_parse_error")
        return ErrorResponse(
            code="INTERNAL_ERROR",
            message="The document parser encountered an unexpected error.",
            retryable=False,
        )


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    _cancellation_signal: asyncio.Event,
) -> TextResponse:
    """Handle one non-streaming document request through the official Responses adapter."""
    result = await process_document_input(await context.get_input_text())
    return TextResponse(
        context,
        request,
        text=result.model_dump_json(exclude_none=False),
    )


def run() -> None:
    app.run()


if __name__ == "__main__":
    run()
