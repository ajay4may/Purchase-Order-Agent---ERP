"""Deterministic de-duplication and arithmetic validation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.models import OrderExtractionCandidate, OrderLine, ValidationSummary


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}".rstrip("0").rstrip(".")


def deduplicate_lines(lines: list[OrderLine]) -> tuple[list[OrderLine], int]:
    """Remove exact business-key duplicates while preserving the first evidence occurrence."""
    seen: set[tuple[str, ...]] = set()
    unique: list[OrderLine] = []
    removed = 0
    for line in lines:
        key = (
            _normalized(line.item_number),
            _normalized(line.customer_item_number),
            _normalized(line.description),
            _number(line.quantity),
            _normalized(line.uom),
            _number(line.unit_price),
            _number(line.line_total),
        )
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique.append(line)
    for index, line in enumerate(unique, start=1):
        if line.line_number is None:
            line.line_number = index
    return unique, removed


@dataclass(frozen=True, slots=True)
class ArithmeticValidator:
    absolute_tolerance: float
    relative_tolerance: float

    def validate(
        self, candidate: OrderExtractionCandidate, duplicate_count: int = 0
    ) -> ValidationSummary:
        warnings: list[str] = []
        if duplicate_count:
            warnings.append(f"Removed {duplicate_count} duplicate line(s).")

        for index, line in enumerate(candidate.lines, start=1):
            if (
                line.quantity is not None
                and line.unit_price is not None
                and line.line_total is not None
            ):
                expected = line.quantity * line.unit_price
                if not self._close(expected, line.line_total):
                    warnings.append(
                        f"Line {line.line_number or index}: quantity * unit_price "
                        "does not match line_total."
                    )

        lines_with_totals = [
            line.line_total for line in candidate.lines if line.line_total is not None
        ]
        calculated_subtotal = sum(lines_with_totals)
        if candidate.subtotal is not None and lines_with_totals:
            if not self._close(calculated_subtotal, candidate.subtotal):
                warnings.append("Sum of line totals does not match subtotal.")

        if candidate.total is not None and candidate.subtotal is not None:
            expected_total = (
                candidate.subtotal + (candidate.tax or 0.0) + (candidate.freight or 0.0)
            )
            if not self._close(expected_total, candidate.total):
                warnings.append("Subtotal + tax + freight does not match total.")

        if not candidate.document_type:
            warnings.append("document_type is missing.")
        if not candidate.lines:
            warnings.append("No order lines were extracted.")
        low_confidence = any(value < 0.7 for value in candidate.field_confidence.values())
        line_low_confidence = any(
            line.confidence is not None and line.confidence < 0.7 for line in candidate.lines
        )
        is_valid = bool(candidate.document_type or candidate.lines) and all(
            line.description or line.item_number or line.customer_item_number
            for line in candidate.lines
        )
        return ValidationSummary(
            is_valid=is_valid,
            needs_review=bool(warnings) or low_confidence or line_low_confidence,
            warnings=warnings,
        )

    def _close(self, expected: float, actual: float) -> bool:
        return math.isclose(
            expected,
            actual,
            abs_tol=self.absolute_tolerance,
            rel_tol=self.relative_tolerance,
        )
