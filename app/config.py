"""Environment-based service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    foundry_project_endpoint: str | None
    model_deployment_name: str | None
    document_intelligence_endpoint: str | None
    max_file_size_bytes: int = 25 * 1024 * 1024
    arithmetic_absolute_tolerance: float = 0.02
    arithmetic_relative_tolerance: float = 0.005
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            foundry_project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
            model_deployment_name=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            document_intelligence_endpoint=os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT"),
            max_file_size_bytes=int(os.getenv("MAX_FILE_SIZE_BYTES", str(25 * 1024 * 1024))),
            arithmetic_absolute_tolerance=float(os.getenv("ARITHMETIC_ABSOLUTE_TOLERANCE", "0.02")),
            arithmetic_relative_tolerance=float(
                os.getenv("ARITHMETIC_RELATIVE_TOLERANCE", "0.005")
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
