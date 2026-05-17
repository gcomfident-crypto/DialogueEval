from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dialogue_simulator.schemas import (
    CaseEvaluationResult,
    ConversationResult,
    GeneratedAssets,
    LLMCallRecord,
    utc_now_iso,
)
from dialogue_simulator.storage import file_sha256, read_text


DEFAULT_REGISTRY_PATH = "outputs/dialogue_eval_registry.sqlite3"
ASSET_HASH_FILES = (
    "scene_asset.yaml",
    "coverage_plan.yaml",
    "coverage_taxonomy.yaml",
    "coverage_matrix.yaml",
    "case_generation_plan.yaml",
    "user_profiles.yaml",
    "case_cards.yaml",
    "scoring_rubric.yaml",
    "materialized_eval_standard.md",
    "variable_assignments.yaml",
)


def registry_status(db_path: str | Path | None = None) -> dict[str, Any]:
    path = _registry_path(db_path)
    ensure_registry(path)
    with _connect(path) as conn:
        return {
            "enabled": True,
            "path": str(path),
            "datasets": _count(conn, "datasets"),
            "task_instructions": _count(conn, "task_instructions"),
            "asset_versions": _count(conn, "asset_versions"),
            "experiments": _count(conn, "experiments"),
            "case_runs": _count(conn, "case_runs"),
            "llm_calls": _count(conn, "llm_calls"),
        }


def list_datasets(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    return _list_rows(
        "datasets",
        "created_at DESC",
        db_path=db_path,
    )


def list_experiments(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    return _list_rows(
        "experiments",
        "started_at DESC",
        db_path=db_path,
    )


def record_dataset(
    *,
    source_path: str | Path,
    source_type: str,
    metadata: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> str:
    path = Path(source_path)
    source_hash = file_sha256(path) if path.is_file() else _hash_text(str(path))
    dataset_id = f"ds_{source_hash[:16]}"
    now = utc_now_iso()
    with _write_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO datasets (
                dataset_id, source_type, source_path, source_hash, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                source_type=excluded.source_type,
                source_path=excluded.source_path,
                source_hash=excluded.source_hash,
                metadata_json=excluded.metadata_json
            """,
            (
                dataset_id,
                source_type,
                str(path),
                source_hash,
                now,
                _json_dumps(metadata or {}),
            ),
        )
    return dataset_id


def record_task_instruction(
    *,
    dataset_id: str,
    markdown_path: str | Path,
    source_row: int | None = None,
    source_column: int | None = None,
    source_sheet: str = "",
    title: str = "",
    metadata: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> str:
    path = Path(markdown_path)
    text = read_text(path)
    raw_hash = _hash_text(text)
    task_instruction_id = f"ti_{raw_hash[:16]}"
    with _write_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO task_instructions (
                task_instruction_id, dataset_id, source_path, source_row, source_column,
                source_sheet, raw_hash, title, markdown_path, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_instruction_id) DO UPDATE SET
                dataset_id=excluded.dataset_id,
                source_path=excluded.source_path,
                source_row=excluded.source_row,
                source_column=excluded.source_column,
                source_sheet=excluded.source_sheet,
                title=excluded.title,
                markdown_path=excluded.markdown_path,
                metadata_json=excluded.metadata_json
            """,
            (
                task_instruction_id,
                dataset_id,
                str(path),
                source_row,
                source_column,
                source_sheet,
                raw_hash,
                title or _markdown_title(text),
                str(path),
                utc_now_iso(),
                _json_dumps(metadata or {}),
            ),
        )
    return task_instruction_id


def find_task_instruction_by_hash(
    raw_hash: str,
    *,
    db_path: str | Path | None = None,
) -> str:
    if not raw_hash:
        return ""
    ensure_registry(db_path)
    with _connect(_registry_path(db_path)) as conn:
        row = conn.execute(
            "SELECT task_instruction_id FROM task_instructions WHERE raw_hash = ?",
            (raw_hash,),
        ).fetchone()
    return str(row["task_instruction_id"]) if row else ""


def record_asset_version(
    *,
    asset_dir: str | Path,
    assets: GeneratedAssets,
    task_instruction_id: str = "",
    db_path: str | Path | None = None,
) -> str:
    path = Path(asset_dir)
    asset_hash = _asset_bundle_hash(path)
    asset_version_id = f"av_{asset_hash[:16]}"
    with _write_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO asset_versions (
                asset_version_id, task_instruction_id, scene_id, scene_name, asset_dir,
                asset_hash, input_hash, case_count, coverage_label_count, profile_count,
                scoring_dimension_count, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_version_id) DO UPDATE SET
                task_instruction_id=COALESCE(NULLIF(excluded.task_instruction_id, ''), task_instruction_id),
                scene_id=excluded.scene_id,
                scene_name=excluded.scene_name,
                asset_dir=excluded.asset_dir,
                input_hash=excluded.input_hash,
                case_count=excluded.case_count,
                coverage_label_count=excluded.coverage_label_count,
                profile_count=excluded.profile_count,
                scoring_dimension_count=excluded.scoring_dimension_count,
                metadata_json=excluded.metadata_json
            """,
            (
                asset_version_id,
                task_instruction_id,
                assets.scene_asset.scene_id,
                assets.scene_asset.scene_name,
                str(path),
                asset_hash,
                assets.scene_asset.generation_metadata.input_hash,
                len(assets.case_cards.cases),
                len(assets.coverage_plan.coverage_labels),
                len(assets.user_profiles.profiles),
                len(assets.scoring_rubric.dimensions),
                utc_now_iso(),
                _json_dumps(
                    {
                        "source_eval_standard_path": assets.scene_asset.source_eval_standard_path,
                        "asset_version": assets.scene_asset.generation_metadata.asset_version,
                    }
                ),
            ),
        )
    return asset_version_id


def asset_version_for_dir(
    asset_dir: str | Path,
    *,
    db_path: str | Path | None = None,
) -> str:
    ensure_registry(db_path)
    path = str(Path(asset_dir))
    with _connect(_registry_path(db_path)) as conn:
        row = conn.execute(
            "SELECT asset_version_id FROM asset_versions WHERE asset_dir = ?",
            (path,),
        ).fetchone()
    return str(row["asset_version_id"]) if row else ""


def experiment_exists(
    experiment_id: str,
    *,
    db_path: str | Path | None = None,
) -> bool:
    ensure_registry(db_path)
    with _connect(_registry_path(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    return row is not None


def create_experiment(
    *,
    experiment_id: str,
    run_id: str,
    asset_version_id: str,
    scene_id: str,
    run_dir: str | Path,
    model_config_path: str = "",
    business_config_path: str = "",
    limit_count: int | None = None,
    skip_evaluation: bool = False,
    fake_llm: bool = False,
    metadata: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> str:
    with _write_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, asset_version_id, run_id, scene_id, run_dir,
                model_config_path, business_config_path, limit_count, skip_evaluation,
                fake_llm, status, started_at, completed_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                asset_version_id=excluded.asset_version_id,
                scene_id=excluded.scene_id,
                run_dir=excluded.run_dir,
                model_config_path=excluded.model_config_path,
                business_config_path=excluded.business_config_path,
                limit_count=excluded.limit_count,
                skip_evaluation=excluded.skip_evaluation,
                fake_llm=excluded.fake_llm,
                status=excluded.status,
                metadata_json=excluded.metadata_json
            """,
            (
                experiment_id,
                asset_version_id,
                run_id,
                scene_id,
                str(run_dir),
                model_config_path,
                business_config_path,
                limit_count,
                int(skip_evaluation),
                int(fake_llm),
                "running",
                utc_now_iso(),
                "",
                _json_dumps(metadata or {}),
            ),
        )
    return experiment_id


def complete_experiment(
    *,
    experiment_id: str,
    status: str = "completed",
    metadata: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> None:
    with _write_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE experiments
            SET status = ?, completed_at = ?, metadata_json = ?
            WHERE experiment_id = ?
            """,
            (status, utc_now_iso(), _json_dumps(metadata or {}), experiment_id),
        )


def record_case_run(
    *,
    experiment_id: str,
    asset_version_id: str,
    conversation: ConversationResult,
    evaluation: CaseEvaluationResult | None = None,
    run_dir: str | Path,
    db_path: str | Path | None = None,
) -> str:
    case_run_id = f"{experiment_id}:{conversation.case_id}"
    risk_count = len(evaluation.risk_deductions) if evaluation else len(conversation.risk_flags)
    with _write_connection(db_path) as conn:
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
            ON CONFLICT(case_run_id) DO UPDATE SET
                status=excluded.status,
                coverage_success=excluded.coverage_success,
                total_score=excluded.total_score,
                passed=excluded.passed,
                missing_targets_json=excluded.missing_targets_json,
                risk_count=excluded.risk_count,
                veto_triggered=excluded.veto_triggered,
                turn_count=excluded.turn_count,
                conversation_log_path=excluded.conversation_log_path,
                case_report_path=excluded.case_report_path,
                metadata_json=excluded.metadata_json
            """,
            (
                case_run_id,
                experiment_id,
                asset_version_id,
                conversation.run_id,
                conversation.case_id,
                conversation.scene_id,
                conversation.priority,
                "evaluated" if evaluation else "conversation_completed",
                int(conversation.coverage_success),
                evaluation.total_score if evaluation else None,
                int(evaluation.passed) if evaluation else None,
                _json_dumps(conversation.missing_targets),
                risk_count,
                int(evaluation.veto_triggered) if evaluation else 0,
                len(conversation.turns),
                str(Path(run_dir) / "conversation_log.jsonl"),
                str(Path(run_dir) / "case_reports" / f"{conversation.case_id}.md"),
                conversation.run_id,
                utc_now_iso(),
                _json_dumps(
                    {
                        "triggered_targets": conversation.triggered_targets,
                        "end_reason": conversation.end_reason,
                    }
                ),
            ),
        )
    return case_run_id


def record_llm_calls(
    *,
    records: list[LLMCallRecord],
    experiment_id: str,
    run_id: str,
    db_path: str | Path | None = None,
) -> None:
    with _write_connection(db_path) as conn:
        for record in records:
            conn.execute(
                """
                INSERT INTO llm_calls (
                    call_id, experiment_id, run_id, task_name, role, model,
                    latency_ms, prompt_tokens, completion_tokens, total_tokens,
                    prompt_chars, completion_chars, prompt_hash, completion_hash,
                    success, error, started_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(call_id) DO UPDATE SET
                    latency_ms=excluded.latency_ms,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    total_tokens=excluded.total_tokens,
                    prompt_chars=excluded.prompt_chars,
                    completion_chars=excluded.completion_chars,
                    prompt_hash=excluded.prompt_hash,
                    completion_hash=excluded.completion_hash,
                    success=excluded.success,
                    error=excluded.error,
                    metadata_json=excluded.metadata_json
                """,
                (
                    record.call_id,
                    experiment_id,
                    run_id,
                    record.task_name,
                    record.role,
                    record.model,
                    record.latency_ms,
                    record.prompt_tokens,
                    record.completion_tokens,
                    record.total_tokens,
                    record.prompt_chars,
                    record.completion_chars,
                    record.prompt_hash,
                    record.completion_hash,
                    int(record.success),
                    record.error,
                    record.started_at,
                    _json_dumps(
                        {
                            "temperature": record.temperature,
                            "message_count": record.message_count,
                            "estimated_cost": record.estimated_cost,
                        }
                    ),
                ),
            )


def ensure_registry(db_path: str | Path | None = None) -> None:
    path = _registry_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS task_instructions (
                task_instruction_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_row INTEGER,
                source_column INTEGER,
                source_sheet TEXT NOT NULL DEFAULT '',
                raw_hash TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                markdown_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_task_instructions_dataset
                ON task_instructions(dataset_id);
            CREATE INDEX IF NOT EXISTS idx_task_instructions_raw_hash
                ON task_instructions(raw_hash);

            CREATE TABLE IF NOT EXISTS asset_versions (
                asset_version_id TEXT PRIMARY KEY,
                task_instruction_id TEXT NOT NULL DEFAULT '',
                scene_id TEXT NOT NULL,
                scene_name TEXT NOT NULL DEFAULT '',
                asset_dir TEXT NOT NULL,
                asset_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL DEFAULT '',
                case_count INTEGER NOT NULL DEFAULT 0,
                coverage_label_count INTEGER NOT NULL DEFAULT 0,
                profile_count INTEGER NOT NULL DEFAULT 0,
                scoring_dimension_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_asset_versions_scene_id
                ON asset_versions(scene_id);
            CREATE INDEX IF NOT EXISTS idx_asset_versions_task
                ON asset_versions(task_instruction_id);

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                asset_version_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                run_dir TEXT NOT NULL,
                model_config_path TEXT NOT NULL DEFAULT '',
                business_config_path TEXT NOT NULL DEFAULT '',
                limit_count INTEGER,
                skip_evaluation INTEGER NOT NULL DEFAULT 0,
                fake_llm INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_experiments_run_id
                ON experiments(run_id);
            CREATE INDEX IF NOT EXISTS idx_experiments_asset
                ON experiments(asset_version_id);

            CREATE TABLE IF NOT EXISTS case_runs (
                case_run_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                asset_version_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                coverage_success INTEGER NOT NULL DEFAULT 0,
                total_score REAL,
                passed INTEGER,
                missing_targets_json TEXT NOT NULL DEFAULT '[]',
                risk_count INTEGER NOT NULL DEFAULT 0,
                veto_triggered INTEGER NOT NULL DEFAULT 0,
                turn_count INTEGER NOT NULL DEFAULT 0,
                conversation_log_path TEXT NOT NULL DEFAULT '',
                case_report_path TEXT NOT NULL DEFAULT '',
                phoenix_session_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_case_runs_experiment
                ON case_runs(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_case_runs_case
                ON case_runs(case_id);

            CREATE TABLE IF NOT EXISTS llm_calls (
                call_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                role TEXT NOT NULL,
                model TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                prompt_chars INTEGER,
                completion_chars INTEGER,
                prompt_hash TEXT NOT NULL DEFAULT '',
                completion_hash TEXT NOT NULL DEFAULT '',
                success INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_llm_calls_experiment
                ON llm_calls(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_task
                ON llm_calls(task_name);
            """
        )


def _list_rows(
    table: str,
    order_by: str,
    *,
    db_path: str | Path | None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_registry(db_path)
    with _connect(_registry_path(db_path)) as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by} LIMIT ?", (limit,)).fetchall()
    return [_decode_row(dict(row)) for row in rows]


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def _write_connection(db_path: str | Path | None = None):
    path = _registry_path(db_path)
    ensure_registry(path)
    return _connect(path)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _registry_path(db_path: str | Path | None = None) -> Path:
    configured = db_path or os.getenv("DIALOGUE_EVAL_REGISTRY_PATH") or DEFAULT_REGISTRY_PATH
    path = Path(configured).expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _asset_bundle_hash(asset_dir: Path) -> str:
    digest = hashlib.sha256()
    for filename in ASSET_HASH_FILES:
        path = asset_dir / filename
        if not path.is_file():
            continue
        digest.update(filename.encode("utf-8"))
        digest.update(file_sha256(path).encode("utf-8"))
    return digest.hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _markdown_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in list(row.keys()):
        if key.endswith("_json") and isinstance(row[key], str):
            try:
                row[key] = json.loads(row[key])
            except json.JSONDecodeError:
                pass
    return row
