"""Foundry model normalization behind a testable interface."""

from __future__ import annotations

import json
from typing import Protocol

from azure.core.exceptions import AzureError
from httpx import HTTPError
from openai import OpenAIError

from app.errors import ConfigurationError, UpstreamServiceError
from app.models import OrderExtractionCandidate, RawDocument

SYSTEM_INSTRUCTIONS = """
You extract order-processing data from OCR, email, document, and spreadsheet content.
Return only the requested structured object. Never infer missing values: use null.
Preserve printed versus handwritten evidence using source_type.
Treat purchase orders, invoices, and order confirmations as distinct document types.
Avoid duplicate lines caused by repeated table headers, repeated pages, or PO/confirmation copies.
Use ISO 8601 dates and ISO 4217 currency codes only when supported by the source.
Do not perform customer lookup, order creation, workflow orchestration, or business decisions.
""".strip()


class OrderNormalizer(Protocol):
    async def normalize(self, document: RawDocument) -> OrderExtractionCandidate:
        """Normalize extracted source data into the strict order schema."""
        ...


class FoundryAgentNormalizer:
    """Microsoft Agent Framework client using Foundry managed identity authentication."""

    def __init__(self, project_endpoint: str | None, model_deployment: str | None) -> None:
        self._project_endpoint = project_endpoint
        self._model_deployment = model_deployment
        self._agent: object | None = None

    def _get_agent(self) -> object:
        if not self._project_endpoint or not self._model_deployment:
            raise ConfigurationError(
                "FOUNDRY_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME are required."
            )
        if self._agent is None:
            from agent_framework import Agent
            from agent_framework.foundry import FoundryChatClient
            from azure.identity import DefaultAzureCredential

            client = FoundryChatClient(
                project_endpoint=self._project_endpoint,
                model=self._model_deployment,
                credential=DefaultAzureCredential(),
            )
            self._agent = Agent(
                client=client,
                name="order-document-normalizer",
                instructions=SYSTEM_INSTRUCTIONS,
                default_options={"store": False},
            )
        return self._agent

    async def normalize(self, document: RawDocument) -> OrderExtractionCandidate:
        payload = {
            "text": document.text,
            "tables": document.tables,
            "source_evidence": [evidence.model_dump(mode="json") for evidence in document.evidence],
        }
        prompt = (
            "Extract and normalize this single source document. Values absent from the "
            "source must be null. Input:\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
        try:
            agent = self._get_agent()
            result = await agent.run(  # type: ignore[attr-defined]
                prompt,
                options={"response_format": OrderExtractionCandidate},
            )
        except ConfigurationError:
            raise
        except (AzureError, HTTPError, OpenAIError, RuntimeError, TypeError, ValueError) as exc:
            raise UpstreamServiceError(
                "MODEL_NORMALIZATION_ERROR",
                "The Foundry model could not normalize the extracted document.",
            ) from exc

        try:
            if result.value is not None:
                return OrderExtractionCandidate.model_validate(result.value)
            return OrderExtractionCandidate.model_validate_json(result.text)
        except (TypeError, ValueError) as exc:
            raise UpstreamServiceError(
                "INVALID_MODEL_OUTPUT",
                "The Foundry model returned output that did not match the required schema.",
                retryable=False,
            ) from exc
