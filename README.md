# Microsoft Foundry order document parser

A single, stateless Microsoft Foundry Hosted Agent that accepts one uploaded document at
`POST /responses` and returns only strict order-processing JSON. It intentionally excludes
Dataverse access, persistence, workflow orchestration, and business-side order creation.

## Processing design

1. Validate the file name, MIME type, strict base64 payload, and size.
2. Route PDF/images to Azure AI Document Intelligence Layout OCR.
3. Route DOCX, XLS/XLSX/CSV, MSG/EML, and text through native parsers.
4. Normalize the extracted source using a Foundry model through Microsoft Agent Framework
   structured output.
5. Revalidate with Pydantic, remove exact duplicate lines, and run line/header arithmetic checks.
6. Return one success or typed error JSON object. Missing source values remain `null`.

Printed and handwritten OCR evidence remain distinguishable. Telemetry records request IDs,
latency, status, and error codes only; it does not log document content or extracted values.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
pytest
ruff check .
mypy app
python -m app.main
```

The host listens on port `8088` and exposes:

- `GET /readiness`
- `POST /responses`

Callers send an OpenAI Responses request whose `input` text is the serialized `ParseRequest`;
the returned Responses envelope contains one schema-valid JSON object in its `output_text`.

See [DEPLOYMENT.md](DEPLOYMENT.md) for local invocation, Foundry/`azd` deployment, managed
identity roles, Copilot Studio connector mapping, and release packaging.

## Data handling

Customer documents and evaluation samples are never committed. Local integration/evaluation
tests read sample folders only from environment variables and assert schema/aggregate metadata,
not confidential golden values.
