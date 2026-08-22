from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import OrderExtractionCandidate, OrderLine, ParseRequest


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ParseRequest(
            file_name="order.pdf",
            mime_type="application/pdf",
            content_base64="YQ==",
            unexpected=True,
        )


def test_line_requires_description_or_identifier() -> None:
    with pytest.raises(ValidationError):
        OrderLine(quantity=1, unit_price=2, line_total=2)


def test_missing_order_fields_remain_null() -> None:
    candidate = OrderExtractionCandidate(document_type="Purchase Order")
    payload = candidate.model_dump(mode="json")
    assert payload["customer_name"] is None
    assert payload["requested_delivery_date"] is None
    assert payload["lines"] == []
