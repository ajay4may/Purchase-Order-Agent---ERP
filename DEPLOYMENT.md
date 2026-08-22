# Deployment guide

This package deploys one stateless Microsoft Foundry Hosted Agent. It parses one file and
returns order-processing JSON. It does not access Dataverse, persist documents, orchestrate
workflows, or create orders.

## Prerequisites

- Azure subscription and an existing or approved Microsoft Foundry project.
- A structured-output-capable model deployment in the project.
- Azure AI Document Intelligence resource.
- Azure CLI, Azure Developer CLI, and the hosted-agent extension:

```powershell
az login
azd auth login
azd ext install azure.ai.agents
```

Grant the hosted agent managed identity:

- **Azure AI User** (or the least-privilege equivalent required to invoke the project model)
  on the Foundry project.
- **Cognitive Services User** on the Document Intelligence resource.

No credentials or API keys are required by the application.

## Configure

Copy `.env.example` to a local `.env` only for development; never add `.env` to source control.
Set:

```text
FOUNDRY_PROJECT_ENDPOINT
AZURE_AI_MODEL_DEPLOYMENT_NAME
DOCUMENT_INTELLIGENCE_ENDPOINT
```

For `azd`, set the deployment values without putting secrets in files:

```powershell
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<deployment-name>"
azd env set AZURE_AI_MODEL_NAME "<catalog-model-name>"
azd env set AZURE_AI_MODEL_VERSION "<catalog-model-version>"
azd env set AZURE_AI_MODEL_SKU "GlobalStandard"
azd env set DOCUMENT_INTELLIGENCE_ENDPOINT "https://<resource>.cognitiveservices.azure.com/"
azd env set MAX_FILE_SIZE_BYTES "26214400"
```

## Local run

Agent Framework packages are prerelease, so retain the prerelease versions in
`requirements.lock`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m app.main
```

Readiness:

```powershell
Invoke-RestMethod http://localhost:8088/readiness
```

Invoke with a non-sensitive local file:

```powershell
$bytes = [System.IO.File]::ReadAllBytes("synthetic-order.xlsx")
$document = @{
  file_name = "synthetic-order.xlsx"
  mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  content_base64 = [Convert]::ToBase64String($bytes)
} | ConvertTo-Json
$body = @{ input = $document; stream = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8088/responses `
  -ContentType "application/json" -Body $body
```

The response envelope's `output_text` is the exact schema-valid order JSON. Streaming is
disabled because the product contract returns one atomic JSON object.

## Deploy

Review `azure.yaml` and use your approved subscription/environment:

```powershell
azd init
azd provision
azd deploy
```

Do not run provisioning until subscription, region, resource naming, model, capacity, and
Document Intelligence resource details are approved. After deployment, verify `/readiness`,
then invoke `/responses` through the Foundry agent endpoint.

## Copilot Studio custom connector

1. Replace the server URL and OAuth placeholders in
   `connector/foundry-document-parser.openapi.yaml`.
2. Import the OpenAPI definition as a custom connector and configure Microsoft Entra ID OAuth.
3. In the topic, require one uploaded file and call **ParseOrderDocument**.
4. Map `input` to compact JSON containing the attachment name, MIME type, and base64 content:

```powerfx
JSON(
  {
    file_name: First(System.Activity.Attachments).Name,
    mime_type: "application/octet-stream",
    content_base64: First(System.Activity.Attachments).Content
  },
  JSONFormat.Compact
)
```

Set `stream` to `false`. The parser also routes by file extension, so
`application/octet-stream` is safe when the attachment lacks a MIME property. Depending on the
channel, `First(System.Activity.Attachments).Content` can be a content URL rather than inline
bytes. In that case, use a thin Power Automate/custom-connector step to download the attachment
and place its base64 bytes in `content_base64`.

Read `output[0].content[0].text`, parse it as JSON, then branch on `status`. The checked-in
OpenAPI definition includes both `OrderSuccess` and `ErrorResponse` component schemas. Do not
attempt business-side order creation inside this connector action.

## Package

Create and validate a deterministic deployment bundle:

```powershell
python scripts\package_release.py
```

The command writes `dist\foundry-document-parser-<version>.zip` and a sibling
`.zip.sha256`. The archive contains only runtime/deployment files plus
`package-manifest.json` and `SHA256SUMS`.
