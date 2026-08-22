from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from app.models import ErrorResponse

ROOT = Path(__file__).resolve().parents[1]


def test_json_schema_is_valid() -> None:
    schema = json.loads((ROOT / "schemas" / "order-processing.schema.json").read_text())
    Draft202012Validator.check_schema(schema)


def test_error_response_matches_checked_in_schema() -> None:
    schema = json.loads((ROOT / "schemas" / "order-processing.schema.json").read_text())
    validator = Draft202012Validator(schema)
    payload = ErrorResponse(
        code="UNSUPPORTED_FORMAT", message="Unsupported.", retryable=False
    ).model_dump(mode="json")
    assert list(validator.iter_errors(payload)) == []


def test_connector_has_typed_binary_contract() -> None:
    connector = yaml.safe_load(
        (ROOT / "connector" / "foundry-document-parser.openapi.yaml").read_text()
    )
    operation = connector["paths"]["/responses"]["post"]
    request = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request["$ref"].endswith("/ResponsesRequest")
    content = connector["components"]["schemas"]["ParseRequest"]["properties"]["content_base64"]
    assert content["format"] == "byte"
    assert (
        operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ResponsesEnvelope"
    )
