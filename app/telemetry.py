"""Privacy-safe application logging.

The official AgentServer Responses adapter configures platform OpenTelemetry.
"""

from __future__ import annotations

import logging


def configure_telemetry(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
