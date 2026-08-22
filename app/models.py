"""Strict request, extraction, and response models."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParseRequest(StrictModel):
    file_name: NonEmptyString = Field(max_length=512)
    mime_type: NonEmptyString = Field(max_length=255)
    content_base64: NonEmptyString


EvidenceSource = Literal["printed", "handwritten", "email", "spreadsheet", "document"]


class Evidence(StrictModel):
    source_type: EvidenceSource
    text: str | None = None
    page: int | None = Field(default=None, ge=1)
    sheet: str | None = None
    cell: str | None = None


class OrderLine(StrictModel):
    line_number: int | None = Field(default=None, ge=1)
    item_number: str | None = None
    customer_item_number: str | None = None
    description: str | None = None
    quantity: float | None = None
    uom: str | None = None
    unit_price: float | None = None
    line_total: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_identity(self) -> OrderLine:
        if not self.description and not self.item_number and not self.customer_item_number:
            raise ValueError("Each line requires a description or item identifier.")
        return self


class OrderExtractionCandidate(StrictModel):
    document_type: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_address: str | None = None
    vendor_name: str | None = None
    vendor_address: str | None = None
    bill_to_name: str | None = None
    bill_to_address: str | None = None
    ship_to_name: str | None = None
    ship_to_address: str | None = None
    order_date: date | None = None
    requested_delivery_date: date | None = None
    po_number: str | None = None
    currency: str | None = None
    payment_terms: str | None = None
    freight_terms: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    freight: float | None = None
    total: float | None = None
    lines: list[OrderLine] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_evidence: dict[str, list[Evidence]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_confidence(self) -> OrderExtractionCandidate:
        invalid = [key for key, value in self.field_confidence.items() if not 0 <= value <= 1]
        if invalid:
            raise ValueError(f"Confidence must be between 0 and 1: {', '.join(invalid)}")
        return self


class SourceMetadata(StrictModel):
    file_name: str
    mime_type: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=1)
    sheet_count: int | None = Field(default=None, ge=1)
    contains_handwriting: bool = False
    extracted_with: str


class ValidationSummary(StrictModel):
    is_valid: bool
    needs_review: bool
    warnings: list[str] = Field(default_factory=list)


class OrderSuccess(OrderExtractionCandidate):
    status: Literal["success"] = "success"
    source: SourceMetadata
    validation: ValidationSummary


class ErrorResponse(StrictModel):
    status: Literal["error"] = "error"
    code: str
    message: str
    retryable: bool


class RawDocument(StrictModel):
    text: str
    tables: list[list[list[str | None]]] = Field(default_factory=list)
    page_count: int | None = None
    sheet_count: int | None = None
    contains_handwriting: bool = False
    extracted_with: str
    evidence: list[Evidence] = Field(default_factory=list)
