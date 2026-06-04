from __future__ import annotations

from shared.database.connection import DatabaseConnection
from shared.logging.logger import AgentRunLogger, get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test.module")
    assert logger.name == "test.module"
    assert len(logger.handlers) > 0


def test_agent_run_logger_completed(tmp_db: DatabaseConnection):
    run_logger = AgentRunLogger(agent_name="unit_test_agent", db_connection=tmp_db)
    run_logger.started(metadata={"env": "test"})

    assert run_logger._run_id is not None
    assert run_logger._started_at is not None

    run_logger.completed(records_processed=99)

    row = tmp_db.conn.execute(
        "SELECT * FROM agent_runs WHERE id=?", (run_logger._run_id,)
    ).fetchone()
    assert row["status"] == "COMPLETED"
    assert row["records_processed"] == 99


def test_agent_run_logger_failed(tmp_db: DatabaseConnection):
    run_logger = AgentRunLogger(agent_name="failing_agent", db_connection=tmp_db)
    run_logger.started()
    run_logger.failed(error=ValueError("something went wrong"))

    row = tmp_db.conn.execute(
        "SELECT * FROM agent_runs WHERE id=?", (run_logger._run_id,)
    ).fetchone()
    assert row["status"] == "FAILED"
    assert "something went wrong" in row["error_message"]


def test_agent_run_context_manager_success(tmp_db: DatabaseConnection):
    run_logger = AgentRunLogger(agent_name="ctx_agent", db_connection=tmp_db)
    with run_logger.run_context(metadata={"test": True}) as rl:
        rl.completed(records_processed=5)

    row = tmp_db.conn.execute(
        "SELECT * FROM agent_runs WHERE id=?", (run_logger._run_id,)
    ).fetchone()
    assert row["status"] == "COMPLETED"


def test_agent_run_context_manager_failure(tmp_db: DatabaseConnection):
    run_logger = AgentRunLogger(agent_name="ctx_fail_agent", db_connection=tmp_db)
    try:
        with run_logger.run_context():
            raise RuntimeError("test failure")
    except RuntimeError:
        pass

    row = tmp_db.conn.execute(
        "SELECT * FROM agent_runs WHERE id=?", (run_logger._run_id,)
    ).fetchone()
    assert row["status"] == "FAILED"
