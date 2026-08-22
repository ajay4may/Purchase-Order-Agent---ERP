from __future__ import annotations

from app.models import OrderExtractionCandidate, OrderLine
from app.validation import ArithmeticValidator, deduplicate_lines


def test_multi_page_confirmation_duplicates_are_removed() -> None:
    lines = [
        OrderLine(
            line_number=1,
            item_number="SYN-1",
            description="Synthetic plate",
            quantity=2,
            uom="EA",
            unit_price=5,
            line_total=10,
        ),
        OrderLine(
            line_number=1,
            item_number="SYN-1",
            description="  Synthetic   plate ",
            quantity=2,
            uom="ea",
            unit_price=5,
            line_total=10,
        ),
    ]
    unique, removed = deduplicate_lines(lines)
    assert len(unique) == 1
    assert removed == 1


def test_line_arithmetic_mismatch_requires_review() -> None:
    candidate = OrderExtractionCandidate(
        document_type="Purchase Order",
        lines=[
            OrderLine(
                description="Synthetic item",
                quantity=3,
                unit_price=10,
                line_total=29,
            )
        ],
    )
    result = ArithmeticValidator(0.02, 0.005).validate(candidate)
    assert result.is_valid is True
    assert result.needs_review is True
    assert any("quantity * unit_price" in warning for warning in result.warnings)


def test_header_total_tolerance_accepts_rounding() -> None:
    candidate = OrderExtractionCandidate(
        document_type="Invoice",
        lines=[OrderLine(description="Synthetic item", line_total=9.999)],
        subtotal=10,
        tax=0.5,
        freight=1,
        total=11.5,
    )
    result = ArithmeticValidator(0.02, 0.005).validate(candidate)
    assert result.warnings == []
    assert result.needs_review is False
