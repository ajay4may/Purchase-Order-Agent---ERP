"""Create and verify a deterministic deployment-only ZIP package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "tests",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def collect_files() -> list[Path]:
    entries = [
        line.strip()
        for line in (ROOT / "packaging" / "package-files.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    files: list[Path] = []
    for entry in entries:
        path = ROOT / entry
        if not path.exists():
            raise FileNotFoundError(f"Required package path does not exist: {entry}")
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in candidates:
            relative = candidate.relative_to(ROOT)
            if (
                candidate.is_file()
                and not any(part in EXCLUDED_PARTS for part in relative.parts)
                and candidate.suffix not in EXCLUDED_SUFFIXES
            ):
                files.append(candidate)
    return sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix())


def build_package(output_dir: Path) -> Path:
    version = package_version()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"foundry-document-parser-{version}.zip"
    files = collect_files()
    content_manifest = []
    for path in files:
        content_manifest.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest = {
        "name": "foundry-document-parser",
        "version": version,
        "files": content_manifest,
    }
    checksums = "\n".join(f"{item['sha256']}  {item['path']}" for item in content_manifest) + "\n"

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix())
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        for name, data in {
            "package-manifest.json": json.dumps(manifest, indent=2) + "\n",
            "SHA256SUMS": checksums,
        }.items():
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o644 << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    (archive.with_suffix(".zip.sha256")).write_text(f"{sha256(archive)}  {archive.name}\n")
    verify_package(archive)
    return archive


def verify_package(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="foundry-parser-package-") as temp_dir:
        target = Path(temp_dir)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        manifest = json.loads((target / "package-manifest.json").read_text())
        expected = {item["path"]: item["sha256"] for item in manifest["files"]}
        for relative, expected_hash in expected.items():
            path = target / relative
            if not path.is_file() or sha256(path) != expected_hash:
                raise RuntimeError(f"Package checksum validation failed: {relative}")
        required = {
            "app/main.py",
            "Dockerfile",
            "azure.yaml",
            "connector/foundry-document-parser.openapi.yaml",
            "schemas/order-processing.schema.json",
            "DEPLOYMENT.md",
        }
        if missing := required - set(expected):
            raise RuntimeError(f"Package is missing required files: {sorted(missing)}")
        if any(part in EXCLUDED_PARTS for path in expected for part in Path(path).parts):
            raise RuntimeError("Package contains an excluded path.")
        spec = importlib.util.spec_from_file_location(
            "package_config", target / "app" / "config.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load packaged configuration module.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.Settings.from_env()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    archive = build_package(args.output_dir.resolve())
    print(archive)


if __name__ == "__main__":
    main()
