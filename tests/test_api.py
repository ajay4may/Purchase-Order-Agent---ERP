from __future__ import annotations

import base64
import json

from conftest import FakeExtractor, FakeNormalizer
from starlette.testclient import TestClient

import app.main as main
from app.extractors.router import ExtractionRouter
from app.service import DocumentParserService
from app.validation import ArithmeticValidator


def make_client(monkeypatch) -> TestClient:
    service = DocumentParserService(
        ExtractionRouter(FakeExtractor(), FakeExtractor()),
        FakeNormalizer(),
        ArithmeticValidator(0.02, 0.005),
        max_file_size_bytes=1024,
    )
    monkeypatch.setattr(main, "get_service", lambda: service)
    return TestClient(main.app, raise_server_exceptions=False)


def test_responses_is_json_only(monkeypatch) -> None:
    document_request = {
        "file_name": "synthetic.txt",
        "mime_type": "text/plain",
        "content_base64": base64.b64encode(b"synthetic").decode(),
    }
    response = make_client(monkeypatch).post(
        "/responses",
        json={
            "input": json.dumps(document_request),
            "stream": False,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.text.lstrip().startswith("{")
    assert "```" not in response.text
    envelope = response.json()
    parsed_output = json.loads(envelope["output"][0]["content"][0]["text"])
    assert parsed_output["status"] == "success"


def test_request_validation_returns_typed_error(monkeypatch) -> None:
    response = make_client(monkeypatch).post(
        "/responses",
        json={"input": json.dumps({"file_name": "missing.txt"}), "stream": False},
    )
    assert response.status_code == 200
    payload = json.loads(response.json()["output"][0]["content"][0]["text"])
    assert payload == {
        "status": "error",
        "code": "INVALID_RESPONSES_INPUT",
        "message": "Responses input must be JSON with file_name, mime_type, and content_base64.",
        "retryable": False,
    }


def test_openai_responses_request_returns_protocol_envelope(monkeypatch) -> None:
    document_request = {
        "file_name": "synthetic.txt",
        "mime_type": "text/plain",
        "content_base64": base64.b64encode(b"synthetic").decode(),
    }
    response = make_client(monkeypatch).post(
        "/responses",
        json={
            "model": "deployment",
            "input": json.dumps(document_request),
            "stream": False,
        },
    )
    assert response.status_code == 200
    envelope = response.json()
    assert envelope["object"] == "response"
    assert envelope["status"] == "completed"
    parsed_output = json.loads(envelope["output"][0]["content"][0]["text"])
    assert parsed_output["status"] == "success"
    assert "```" not in envelope["output"][0]["content"][0]["text"]


def test_readiness(monkeypatch) -> None:
    response = make_client(monkeypatch).get("/readiness")
    assert response.status_code == 200
