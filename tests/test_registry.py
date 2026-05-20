import sqlite3
from pathlib import Path

from dialogue_simulator.registry import delete_run_records, ensure_registry


def test_delete_run_records_removes_registry_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    ensure_registry(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, asset_version_id, run_id, scene_id, run_dir,
                model_config_path, business_config_path, limit_count, skip_evaluation,
                fake_llm, status, started_at, completed_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_run_delete",
                "asset_v1",
                "run_delete",
                "scene_a",
                "outputs/runs/run_delete",
                "",
                "",
                None,
                0,
                0,
                "completed",
                "2026-05-17T10:00:00+00:00",
                "2026-05-17T10:01:00+00:00",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO case_runs (
                case_run_id, experiment_id, asset_version_id, run_id, case_id, scene_id,
                priority, status, coverage_success, total_score, passed,
                missing_targets_json, risk_count, veto_triggered, turn_count,
                conversation_log_path, case_report_path, phoenix_session_id,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_run_delete:case_001",
                "exp_run_delete",
                "asset_v1",
                "run_delete",
                "case_001",
                "scene_a",
                "P0",
                "evaluated",
                1,
                90.0,
                1,
                "[]",
                0,
                0,
                4,
                "",
                "",
                "",
                "2026-05-17T10:00:00+00:00",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO llm_calls (
                call_id, experiment_id, run_id, task_name, role, model,
                latency_ms, prompt_tokens, completion_tokens, total_tokens,
                prompt_chars, completion_chars, prompt_hash, completion_hash,
                success, error, started_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "call_001",
                "exp_run_delete",
                "run_delete",
                "agent_turn",
                "agent",
                "fake",
                1,
                None,
                None,
                None,
                10,
                5,
                "ph",
                "ch",
                1,
                "",
                "2026-05-17T10:00:00+00:00",
                "{}",
            ),
        )

    result = delete_run_records("run_delete", db_path=db_path)

    assert result == {"experiments": 1, "case_runs": 1, "llm_calls": 1}
