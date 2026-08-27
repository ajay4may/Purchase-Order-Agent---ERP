from __future__ import annotations

import io
from types import SimpleNamespace

import openpyxl
import pytest

from app.errors import CorruptDocumentError
from app.extractors.native import NativeDocumentExtractor


@pytest.mark.asyncio
async def test_xlsx_rows_and_cells_are_extracted() -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Order"
    sheet.append(["Item", "Description", "Qty", "Price"])
    sheet.append(["SYN-1", "Synthetic widget", 2, 4.5])
    stream = io.BytesIO()
    workbook.save(stream)

    result = await NativeDocumentExtractor().extract(
        "synthetic.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        stream.getvalue(),
    )

    assert result.sheet_count == 1
    assert "SYN-1" in result.text
    assert any(item.cell == "A2" for item in result.evidence)
    assert all(item.source_type == "spreadsheet" for item in result.evidence)


@pytest.mark.asyncio
async def test_legacy_xls_rows_are_extracted(monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = SimpleNamespace(
        name="Order",
        nrows=2,
        row_values=lambda index: ["Item", "Qty"] if index == 0 else ["SYN-2", 3.0],
    )
    workbook = SimpleNamespace(nsheets=1, sheets=lambda: [sheet])
    monkeypatch.setattr("app.extractors.native.xlrd.open_workbook", lambda **_: workbook)

    result = await NativeDocumentExtractor().extract(
        "synthetic.xls", "application/vnd.ms-excel", b"synthetic-biff"
    )

    assert result.sheet_count == 1
    assert "SYN-2" in result.text
    assert result.extracted_with == "xlrd"


@pytest.mark.asyncio
async def test_email_prose_is_preserved() -> None:
    eml = (
        b"Subject: Synthetic order\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Please ship 4 synthetic brackets at 3.25 each."
    )
    result = await NativeDocumentExtractor().extract("order.eml", "message/rfc822", eml)
    assert "4 synthetic brackets" in result.text
    assert result.evidence[0].source_type == "email"


@pytest.mark.asyncio
async def test_msg_body_and_attachment_names_are_extracted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_message = SimpleNamespace(
        body="Send two synthetic fasteners.",
        html_body=None,
        subject="Synthetic PO",
        attachments=[SimpleNamespace(longFilename="terms.txt", shortFilename=None, data=b"net 30")],
        close=lambda: None,
    )
    monkeypatch.setattr("app.extractors.native.extract_msg.Message", lambda _: fake_message)
    result = await NativeDocumentExtractor().extract(
        "order.msg", "application/vnd.ms-outlook", b"synthetic-msg"
    )
    assert "Send two synthetic fasteners" in result.text
    assert "terms.txt" in result.text
    assert "net 30" in result.text


@pytest.mark.asyncio
async def test_corrupt_msg_returns_typed_document_error() -> None:
    with pytest.raises(CorruptDocumentError):
        await NativeDocumentExtractor().extract(
            "broken.msg", "application/vnd.ms-outlook", b"not-an-msg"
        )


@pytest.mark.asyncio
async def test_xlsx_expansion_limit_is_enforced() -> None:
    workbook = openpyxl.Workbook()
    workbook.active.append(["Synthetic value"])
    stream = io.BytesIO()
    workbook.save(stream)
    with pytest.raises(CorruptDocumentError):
        await NativeDocumentExtractor(max_uncompressed_bytes=1).extract(
            "synthetic.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            stream.getvalue(),
        )
