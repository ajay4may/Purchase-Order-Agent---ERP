# Installation and deployment guide

This guide installs one stateless Microsoft Foundry Hosted Agent that parses one uploaded
document and returns schema-valid order-processing JSON. It does not access Dataverse, persist
documents, orchestrate workflows, or create business orders.

## Contents

1. [Choose an installation source](#1-choose-an-installation-source)
2. [Install prerequisites](#2-install-prerequisites)
3. [Prepare Azure resources and access](#3-prepare-azure-resources-and-access)
4. [Install and test locally](#4-install-and-test-locally)
5. [Configure an azd environment](#5-configure-an-azd-environment)
6. [Deploy the hosted agent](#6-deploy-the-hosted-agent)
7. [Grant runtime access to Document Intelligence](#7-grant-runtime-access-to-document-intelligence)
8. [Verify and invoke the deployment](#8-verify-and-invoke-the-deployment)
9. [Configure Copilot Studio](#9-configure-copilot-studio)
10. [Run privacy-safe evaluation](#10-run-privacy-safe-evaluation)
11. [Operate and update the agent](#11-operate-and-update-the-agent)
12. [Troubleshoot](#12-troubleshoot)

## 1. Choose an installation source

Use either a repository checkout or the release ZIP. Run all remaining commands from the
directory containing `azure.yaml`.

### Repository checkout

```powershell
git clone <repository-url>
Set-Location Purchase-Order-Agent---ERP
```

### Release ZIP

Place the ZIP and its `.zip.sha256` file in the same directory, then verify before extracting:

```powershell
$zip = "foundry-document-parser-1.0.0.zip"
$expected = (Get-Content "$zip.sha256").Split()[0].ToLowerInvariant()
$actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "Release archive checksum mismatch." }

New-Item -ItemType Directory -Path .\foundry-document-parser -Force | Out-Null
Expand-Archive -LiteralPath $zip -DestinationPath .\foundry-document-parser -Force
Set-Location .\foundry-document-parser
```

The archive also contains `package-manifest.json` and `SHA256SUMS` for per-file verification.
It intentionally excludes tests, caches, customer documents, credentials, `.env`, and git data.

## 2. Install prerequisites

Required:

- An Azure subscription with permission to use Microsoft Foundry.
- A Microsoft Foundry project and a structured-output-capable chat model deployment, or approval
  for `azd` to provision them.
- An existing Azure AI Document Intelligence resource.
- [Python 3.12](https://www.python.org/downloads/) for local development.
- [Azure CLI 2.80 or later](https://learn.microsoft.com/cli/azure/install-azure-cli).
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- The Azure Developer CLI AI agent extension.

Docker Desktop is optional. Hosted deployment uses a remote Azure Container Registry build by
default. Docker is needed only for an explicit local container build.

Verify the tools:

```powershell
python --version
az version
azd version
azd ext install azure.ai.agents
```

Sign in to the tenant that owns the Foundry project:

```powershell
az login --tenant "<tenant-id>"
azd auth login
az account set --subscription "<subscription-id-or-name>"
az account show --output table
```

No API keys are required. Local execution and the hosted agent both use Microsoft Entra ID through
`DefaultAzureCredential`.

## 3. Prepare Azure resources and access

Collect these values before installation:

| Value | Example |
| --- | --- |
| Subscription ID | `00000000-0000-0000-0000-000000000000` |
| Azure region | `eastus2` |
| Foundry project endpoint | `https://<account>.services.ai.azure.com/api/projects/<project>` |
| Model deployment name | `order-parser-model` |
| Catalog model name/version/SKU | Values approved for the target project |
| Document Intelligence endpoint | `https://<resource>.cognitiveservices.azure.com/` |

### Deployer access

The identity running `azd up` needs **Foundry Project Manager** at the Foundry project scope.
This role was previously named **Azure AI Project Manager**. It permits creation and update of
hosted-agent versions and the associated identity/RBAC operations.

### Local developer access

The identity used by `az login` needs:

- Access to invoke the deployed model in the Foundry project.
- **Cognitive Services User** on the Document Intelligence resource.

### Hosted runtime access

Foundry creates a dedicated Microsoft Entra agent identity during deployment. Model inferencing
through its Foundry project is available by default. Because Document Intelligence is an external
resource, assign **Cognitive Services User** to that agent identity after its first deployment.
Do not put keys, client secrets, or connection strings in source files or `azure.yaml`.

## 4. Install and test locally

Create an isolated Python environment and install the reproducible dependency lock:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
```

Set local process variables. A `.env` file is not loaded automatically; the explicit assignments
below avoid accidentally relying on an uncommitted local file.

```powershell
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "<model-deployment-name>"
$env:DOCUMENT_INTELLIGENCE_ENDPOINT = "https://<resource>.cognitiveservices.azure.com/"
$env:MAX_FILE_SIZE_BYTES = "26214400"
$env:ARITHMETIC_ABSOLUTE_TOLERANCE = "0.02"
$env:ARITHMETIC_RELATIVE_TOLERANCE = "0.005"
$env:LOG_LEVEL = "INFO"
```

Run validation:

```powershell
python -m ruff format --check app tests evaluation scripts
python -m ruff check app tests evaluation scripts
python -m mypy app
python -m pytest
```

Start the host:

```powershell
python -m app.main
```

The protocol adapter listens on port `8088` and supplies both endpoints:

- `GET http://localhost:8088/readiness`
- `POST http://localhost:8088/responses`

Check readiness from another terminal:

```powershell
Invoke-RestMethod http://localhost:8088/readiness
```

Invoke with a non-sensitive local fixture:

```powershell
$file = Resolve-Path ".\synthetic-order.xlsx"
$document = @{
  file_name = $file.Path | Split-Path -Leaf
  mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  content_base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file.Path))
} | ConvertTo-Json -Compress

$body = @{ input = $document; stream = $false } | ConvertTo-Json -Compress
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8088/responses" `
  -ContentType "application/json" -Body $body

$order = $response.output[0].content[0].text | ConvertFrom-Json
$order
```

`output[0].content[0].text` contains exactly one `OrderSuccess` or `ErrorResponse` JSON object.
Streaming must remain `false` so the caller receives one atomic result.

## 5. Configure an azd environment

The checked-in `azure.yaml` defines the Foundry project/model dependency and the Python 3.12
hosted agent. Create an environment and set deployment-specific values:

```powershell
azd env new "<environment-name>"
azd env set AZURE_SUBSCRIPTION_ID "<subscription-id>"
azd env set AZURE_LOCATION "<approved-region>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<model-deployment-name>"
azd env set AZURE_AI_MODEL_NAME "<catalog-model-name>"
azd env set AZURE_AI_MODEL_VERSION "<catalog-model-version>"
azd env set AZURE_AI_MODEL_SKU "GlobalStandard"
azd env set DOCUMENT_INTELLIGENCE_ENDPOINT "https://<resource>.cognitiveservices.azure.com/"
azd env set MAX_FILE_SIZE_BYTES "26214400"
```

Review the values before provisioning:

```powershell
azd env get-values
```

The Hosted Agent platform injects `FOUNDRY_PROJECT_ENDPOINT`,
`APPLICATIONINSIGHTS_CONNECTION_STRING`, and other `FOUNDRY_*` variables. Do not add or redeclare
those variables in `azure.yaml`.

## 6. Deploy the hosted agent

Do not provision until the subscription, region, resource names, model, SKU, capacity, and
Document Intelligence resource are approved.

For the first deployment, provision and deploy in one operation:

```powershell
azd up
```

`azd up` provisions the manifest resources and then deploys the agent. The default hosted-agent
flow builds the `linux/amd64` container remotely in Azure Container Registry, creates an agent
version, and creates its dedicated Microsoft Entra identity.

If the infrastructure already exists and only source or configuration changed:

```powershell
azd deploy
```

Each deployment creates a new hosted-agent version. Previous versions remain available for
rollback; the latest version is active by default.

### Optional local container smoke test

The Hosted Agent platform requires a `linux/amd64` image:

```powershell
docker build --platform linux/amd64 -t foundry-document-parser:local .
docker run --rm -p 8088:8088 --env-file .env foundry-document-parser:local
```

Use this only when the container has a supported Entra credential source. A host `az login`
session is not automatically available inside a plain Docker container. Never bake credentials
into the image.

## 7. Grant runtime access to Document Intelligence

After the first deployment:

1. Open the deployed agent in the Microsoft Foundry portal.
2. Locate its dedicated Microsoft Entra identity/object ID.
3. Open the Azure AI Document Intelligence resource in the Azure portal.
4. Select **Access control (IAM)** > **Add role assignment**.
5. Assign **Cognitive Services User** to the hosted agent identity.
6. Wait several minutes for RBAC propagation.

The app uses the endpoint in `DOCUMENT_INTELLIGENCE_ENDPOINT` and authenticates with that identity.
Do not configure a Document Intelligence key.

## 8. Verify and invoke the deployment

Inspect the deployed name, version, protocol, state, and environment:

```powershell
azd ai agent show --output table
```

The version must reach `active`. For production requests, use the gateway endpoint shown by the
deployment. Its format is:

```text
https://<account>.services.ai.azure.com/api/projects/<project>/agents/foundry-document-parser/endpoint/protocols/responses?api-version=v1
```

Acquire a Foundry data-plane token and invoke the endpoint:

```powershell
$token = az account get-access-token `
  --scope "https://ai.azure.com/.default" `
  --query accessToken --output tsv

$endpoint = "https://<account>.services.ai.azure.com/api/projects/<project>/agents/" +
  "foundry-document-parser/endpoint/protocols/responses?api-version=v1"

$file = Resolve-Path ".\synthetic-order.xlsx"
$document = @{
  file_name = $file.Path | Split-Path -Leaf
  mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  content_base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file.Path))
} | ConvertTo-Json -Compress
$body = @{ input = $document; stream = $false } | ConvertTo-Json -Compress

$response = Invoke-RestMethod -Method Post -Uri $endpoint `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" -Body $body
$response.output[0].content[0].text | ConvertFrom-Json
```

The caller needs a Foundry role that permits agent invocation. A `401` indicates token/tenant or
audience problems; a `403` indicates missing project access.

## 9. Configure Copilot Studio

The connector definition is
`connector/foundry-document-parser.openapi.yaml`.

### Prepare the OpenAPI file

1. Replace `REPLACE_WITH_HOSTED_AGENT_ENDPOINT` with the URL prefix ending in
   `/agents/foundry-document-parser/endpoint/protocols`. The checked-in `/responses` path is then
   appended to form the production endpoint.
2. Replace `REPLACE_TENANT_ID` with the tenant ID that owns the Foundry project.
3. Keep the OAuth scope `https://ai.azure.com/.default`.
4. Confirm the operation includes the `api-version=v1` query parameter.

### Import and secure the connector

1. In Power Apps or Copilot Studio, create a custom connector from the OpenAPI file.
2. Configure Microsoft Entra ID OAuth using an approved app registration/connection identity.
3. Grant the connection identity permission to invoke the Foundry project/agent.
4. Create and test the connector connection.
5. Add the **ParseOrderDocument** action to the Copilot Studio topic.

Do not store a client secret in the OpenAPI file or repository. Enter connector credentials only
through the platform's protected connection configuration.

### Map the uploaded attachment

Require exactly one attachment. Set the connector's `input` string to:

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

Set `stream` to `false` and `api-version` to `v1`.

The parser can route `application/octet-stream` by file extension. Some channels expose
`First(System.Activity.Attachments).Content` as a URL rather than inline base64. In that case, use
a thin Power Automate or custom-connector step to download the attachment and pass the downloaded
bytes as base64. Do not pass the URL itself as `content_base64`.

Read `output[0].content[0].text`, parse it as JSON, and branch on:

- `status = "success"`: consume the typed order fields and inspect `validation`.
- `status = "error"`: display or log `code`, `message`, and `retryable`.

Keep order creation, Dataverse writes, approval workflows, and persistence outside this connector
action.

## 10. Run privacy-safe evaluation

Evaluation inputs remain outside the repository. Point the scaffold at one or more local folders:

```powershell
$env:ORDER_PARSER_SAMPLE_DIRS = @(
  "C:\external\samples\set-one",
  "C:\external\samples\set-two"
) -join [IO.Path]::PathSeparator
$env:ORDER_PARSER_ENDPOINT = "http://localhost:8088"
python evaluation\run_evaluation.py
```

The runner reports aggregate document/status/review/extension counts only. It does not write
document content, PII, or extracted field values. Never add source documents or generated
evaluation output to git.

## 11. Operate and update the agent

View deployment details:

```powershell
azd ai agent show --output table
```

Stream runtime logs:

```powershell
azd ai agent monitor
```

Deploy a code-only update:

```powershell
azd deploy
```

Rebuild the distributable package:

```powershell
python scripts\package_release.py
Get-Content .\dist\foundry-document-parser-1.0.0.zip.sha256
```

Application Insights is injected by the Hosted Agent platform. Review telemetry access and
retention because platform traces can contain request context. Application logging in this
project avoids document bytes and extracted order values.

## 12. Troubleshoot

| Symptom | Likely cause | Resolution |
| --- | --- | --- |
| `/readiness` fails locally | Host did not start or port 8088 is occupied | Check console logs and stop the conflicting process or set the platform-supported port configuration. |
| `INVALID_RESPONSES_INPUT` | `input` is not compact serialized document-request JSON | Send `file_name`, `mime_type`, and `content_base64` inside the Responses `input` string. |
| `INVALID_BASE64` | Attachment content is a URL, data URI, or malformed base64 | Download the bytes first and base64-encode only the file bytes. |
| `UNSUPPORTED_FORMAT` | File extension/MIME type is unsupported | Use PDF, supported image, DOCX, XLS, XLSX, CSV, MSG, EML, or text. |
| `ENCRYPTED_DOCUMENT` | The Office/PDF input is password protected | Obtain an approved unencrypted copy; do not bypass document protection. |
| `CORRUPT_DOCUMENT` | Archive/OLE structure is invalid or unsafe | Re-export the source document and retry. |
| OCR request returns `403` | Agent/developer lacks Document Intelligence access | Assign **Cognitive Services User** at the resource scope and allow RBAC propagation. |
| Model request returns `401`/`403` | Wrong tenant, expired local login, or missing Foundry access | Run `az login` again, confirm the subscription/project, and verify project RBAC. |
| Hosted invocation returns `401` | Connector/token has the wrong audience | Request `https://ai.azure.com/.default`. |
| Hosted invocation returns `404` | Gateway endpoint omitted the agent/protocol path or API version | Use the endpoint from `azd ai agent show` and `api-version=v1`. |
| Result has `needs_review=true` | Missing fields, low confidence, duplicates, or arithmetic mismatch | Route the result to human review; do not guess or auto-correct source values. |

Official references:

- [Deploy a hosted agent](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent)
- [Foundry Hosted Agents with Agent Framework](https://learn.microsoft.com/agent-framework/hosting/foundry-hosted-agent)
- [Install Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Configure Entra ID authentication for Foundry](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/configure-entra-id)
