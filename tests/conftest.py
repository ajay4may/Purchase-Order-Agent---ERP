from __future__ import annotations

import pytest

from app.models import OrderExtractionCandidate, OrderLine, RawDocument


class FakeExtractor:
    def __init__(self, document: RawDocument | None = None) -> None:
        self.document = document or RawDocument(text="synthetic", extracted_with="fake")
        self.calls: list[tuple[str, str, bytes]] = []

    async def extract(self, file_name: str, mime_type: str, content: bytes) -> RawDocument:
        self.calls.append((file_name, mime_type, content))
        return self.document


class FakeNormalizer:
    def __init__(self, candidate: OrderExtractionCandidate | None = None) -> None:
        self.candidate = candidate or OrderExtractionCandidate(
            document_type="Purchase Order",
            lines=[
                OrderLine(
                    line_number=1,
                    item_number="SYN-100",
                    description="Synthetic item",
                    quantity=2,
                    uom="EA",
                    unit_price=5,
                    line_total=10,
                    confidence=0.99,
                )
            ],
            subtotal=10,
            total=10,
        )

    async def normalize(self, _document: RawDocument) -> OrderExtractionCandidate:
        return self.candidate.model_copy(deep=True)


@pytest.fixture
def fake_extractor() -> FakeExtractor:
    return FakeExtractor()


@pytest.fixture
def fake_normalizer() -> FakeNormalizer:
    return FakeNormalizer()
