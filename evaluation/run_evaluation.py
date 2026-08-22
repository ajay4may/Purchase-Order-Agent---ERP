"""Metadata-safe evaluation runner for local, non-committed sample folders."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from collections import Counter
from pathlib import Path
from urllib import request

SUPPORTED = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".docx",
    ".xlsx",
    ".xls",
    ".csv",
    ".msg",
    ".eml",
}


def sample_files() -> list[Path]:
    roots = [
        Path(value)
        for value in os.getenv("ORDER_PARSER_SAMPLE_DIRS", "").split(os.pathsep)
        if value
    ]
    return sorted(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )


def invoke(endpoint: str, path: Path) -> tuple[str, bool]:
    mime_type = mimetypes.guess_type(path.name)[0] or {
        ".msg": "application/vnd.ms-outlook",
        ".xls": "application/vnd.ms-excel",
    }.get(path.suffix.lower(), "application/octet-stream")
    document = {
        "file_name": path.name,
        "mime_type": mime_type,
        "content_base64": base64.b64encode(path.read_bytes()).decode(),
    }
    payload = json.dumps({"input": json.dumps(document), "stream": False}).encode()
    call = request.Request(
        endpoint.rstrip("/") + "/responses",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(call, timeout=180) as response:
        envelope = json.loads(response.read())
    result = json.loads(envelope["output"][0]["content"][0]["text"])
    return str(result.get("status", "unknown")), bool(
        result.get("validation", {}).get("needs_review", False)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=os.getenv("ORDER_PARSER_ENDPOINT"))
    args = parser.parse_args()
    if not args.endpoint:
        raise SystemExit("Set ORDER_PARSER_ENDPOINT or pass --endpoint.")
    files = sample_files()
    if not files:
        raise SystemExit("Set ORDER_PARSER_SAMPLE_DIRS to one or more local sample folders.")
    statuses: Counter[str] = Counter()
    review_count = 0
    for path in files:
        status, needs_review = invoke(args.endpoint, path)
        statuses[status] += 1
        review_count += int(needs_review)
    print(
        json.dumps(
            {
                "documents_evaluated": len(files),
                "status_counts": dict(statuses),
                "needs_review_count": review_count,
                "extensions": dict(Counter(path.suffix.lower() for path in files)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
