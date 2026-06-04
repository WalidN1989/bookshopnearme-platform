from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


class AgentRunLogger:
    """Structured logger for agent runs. Records start/complete/failed + duration."""

    def __init__(self, agent_name: str, db_connection=None) -> None:
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")
        self._db = db_connection
        self._run_id: int | None = None
        self._started_at: float | None = None

    def started(self, metadata: dict | None = None) -> int | None:
        self._started_at = time.monotonic()
        started_wall = datetime.now(timezone.utc).isoformat()
        self.logger.info(f"[STARTED] agent={self.agent_name} at={started_wall} meta={metadata}")

        if self._db:
            self._run_id = self._db.insert_agent_run(
                agent_name=self.agent_name,
                status="STARTED",
                started_at=started_wall,
                metadata=metadata,
            )
        return self._run_id

    def completed(self, records_processed: int = 0, metadata: dict | None = None) -> None:
        duration = round(time.monotonic() - self._started_at, 3) if self._started_at else 0
        self.logger.info(
            f"[COMPLETED] agent={self.agent_name} duration={duration}s records={records_processed}"
        )
        if self._db and self._run_id:
            self._db.update_agent_run(
                run_id=self._run_id,
                status="COMPLETED",
                duration_seconds=duration,
                records_processed=records_processed,
                metadata=metadata,
            )

    def failed(self, error: Exception | str, metadata: dict | None = None) -> None:
        duration = round(time.monotonic() - self._started_at, 3) if self._started_at else 0
        error_str = str(error)
        self.logger.error(
            f"[FAILED] agent={self.agent_name} duration={duration}s error={error_str}"
        )
        if self._db and self._run_id:
            self._db.update_agent_run(
                run_id=self._run_id,
                status="FAILED",
                duration_seconds=duration,
                error_message=error_str,
                metadata=metadata,
            )

    @contextmanager
    def run_context(
        self, metadata: dict | None = None
    ) -> Generator["AgentRunLogger", None, None]:
        self.started(metadata=metadata)
        try:
            yield self
            self.completed()
        except Exception as exc:
            self.failed(error=exc)
            raise
