from __future__ import annotations

from contextvars import ContextVar
import json
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from dialogue_simulator.cli import (
    evaluate_results,
    get_call_records,
    load_conversation_results,
    make_run_id,
)
from dialogue_simulator.eval_standard_loader import (
    extract_markdown_from_csv,
    extract_markdown_from_excel,
    is_csv_path,
    is_excel_path,
    is_tabular_path,
)
from dialogue_simulator.graph import (
    build_asset_generation_graph,
    build_conversation_graph,
    load_generated_assets,
)
from dialogue_simulator.llm_client import FakeLLMClient, OpenAICompatibleClient
from dialogue_simulator.prompt_store import prompt_status, sync_default_prompts
from dialogue_simulator.registry import (
    asset_version_for_dir,
    complete_experiment,
    create_experiment,
    find_task_instruction_by_hash,
    experiment_exists,
    list_datasets as registry_list_datasets,
    list_experiments as registry_list_experiments,
    record_asset_version,
    record_case_run,
    record_dataset,
    record_llm_calls,
    record_task_instruction,
    registry_status,
)
from dialogue_simulator.report_exporter import (
    export_case_artifact_bundles,
    export_evaluation_reports,
    export_llm_call_records,
    export_run_reports,
)
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseEvaluationResult,
    ConversationResult,
    LLMCallRecord,
    ModelConfig,
    utc_now_iso,
)
from dialogue_simulator.storage import read_structured_file
from dialogue_simulator.tracing import trace_span, tracing_status


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_CONFIG = "configs/model_config.yaml"
DEFAULT_GENERATION_POLICY = "configs/generation_policy.yaml"
DEFAULT_ASSETS_ROOT = "outputs/assets"
DEFAULT_RUNS_ROOT = "outputs/runs"
DEFAULT_EXTRACTED_ROOT = "outputs/extracted_eval_standards"
DEFAULT_UPLOAD_ROOT = "outputs/uploads"
DEFAULT_ANNOTATIONS_ROOT = "outputs/annotations"

ASSET_FILES = {
    "scene_asset.yaml",
    "coverage_plan.yaml",
    "user_profiles.yaml",
    "coverage_taxonomy.yaml",
    "coverage_matrix.yaml",
    "case_generation_plan.yaml",
    "case_cards.yaml",
    "scoring_rubric.yaml",
    "materialized_eval_standard.md",
    "variable_assignments.yaml",
    "asset_generation_report.md",
    "coverage_gap_report.md",
    "llm_calls.jsonl",
}
RUN_REPORT_FILES = {
    "summary_report.md",
    "coverage_report.csv",
    "conversation_log.jsonl",
    "simulation_state_trace.jsonl",
    "evaluation_report.md",
    "evaluation_report.csv",
    "case_evaluation.jsonl",
    "llm_calls.jsonl",
}

_evaluation_jobs: dict[str, dict[str, Any]] = {}
_evaluation_jobs_lock = Lock()
_progress_job_id: ContextVar[str | None] = ContextVar("progress_job_id", default=None)


class GenerateAssetsRequest(BaseModel):
    eval_standard_file_path: Optional[str] = None
    eval_standard_path: Optional[str] = None
    eval_standard_excel_path: Optional[str] = None
    selected_eval_standard_paths: Optional[list[str]] = None
    excel_column: int = 2
    excel_start_row: int = 2
    excel_sheet: Optional[str] = None
    extracted_output_dir: str = DEFAULT_EXTRACTED_ROOT
    business_config_path: Optional[str] = None
    generation_policy_path: str = DEFAULT_GENERATION_POLICY
    model_config_path: str = DEFAULT_MODEL_CONFIG
    output_root: str = DEFAULT_ASSETS_ROOT
    fake_llm: bool = False


class RunEvaluationRequest(BaseModel):
    scene_id: Optional[str] = None
    assets_path: Optional[str] = None
    business_config_path: Optional[str] = None
    model_config_path: str = DEFAULT_MODEL_CONFIG
    output_root: str = DEFAULT_RUNS_ROOT
    limit: Optional[int] = Field(default=None, ge=1)
    skip_evaluation: bool = False
    fake_llm: bool = False


class StartEvaluationRequest(BaseModel):
    eval_standard_file_path: Optional[str] = None
    eval_standard_path: Optional[str] = None
    eval_standard_excel_path: Optional[str] = None
    selected_eval_standard_paths: Optional[list[str]] = None
    excel_column: int = 2
    excel_start_row: int = 2
    excel_sheet: Optional[str] = None
    extracted_output_dir: str = DEFAULT_EXTRACTED_ROOT
    business_config_path: Optional[str] = None
    generation_policy_path: str = DEFAULT_GENERATION_POLICY
    model_config_path: str = DEFAULT_MODEL_CONFIG
    asset_output_root: str = DEFAULT_ASSETS_ROOT
    run_output_root: str = DEFAULT_RUNS_ROOT
    limit: Optional[int] = Field(default=None, ge=1)
    skip_evaluation: bool = False
    fake_llm: bool = False


class EvaluateRunRequest(BaseModel):
    scene_id: Optional[str] = None
    assets_path: Optional[str] = None
    run_dir: Optional[str] = None
    business_config_path: Optional[str] = None
    model_config_path: str = DEFAULT_MODEL_CONFIG
    fake_llm: bool = False


class ExtractEvalStandardsRequest(BaseModel):
    excel_path: str
    output_dir: str = DEFAULT_EXTRACTED_ROOT
    excel_column: int = 2
    excel_start_row: int = 2
    excel_sheet: Optional[str] = None


class SyncPromptsRequest(BaseModel):
    phoenix_base_url: Optional[str] = None
    model_name: str = "deepseek-chat"
    dry_run: bool = False


class AnnotationDimensionScore(BaseModel):
    dimension_id: str
    name: str = ""
    weight: float = 0.0
    score: float = 0.0
    reason: str = ""


class AnnotationTargetCheck(BaseModel):
    target: str
    status: str = "unreviewed"
    turn_index: Optional[int] = None
    evidence: str = ""


class AnnotationDimensionCheck(BaseModel):
    check_id: str
    dimension_id: str
    description: str = ""
    deduction: float = 0.0
    status: str = "unreviewed"
    turn_index: Optional[int] = None
    evidence: str = ""


class AnnotationRiskFlag(BaseModel):
    rule_id: str
    description: str = ""
    severity: str = ""
    deduction: float = 0.0
    turn_index: Optional[int] = None
    evidence: str = ""


class AnnotationVetoItem(BaseModel):
    rule_id: str
    description: str = ""
    severity: str = "critical"
    turn_index: Optional[int] = None
    evidence: str = ""


class SaveAnnotationRequest(BaseModel):
    annotator_id: str = "human_01"
    covered_targets: list[str] = Field(default_factory=list)
    target_checks: list[AnnotationTargetCheck] = Field(default_factory=list)
    dimension_checks: list[AnnotationDimensionCheck] = Field(default_factory=list)
    dimension_scores: list[AnnotationDimensionScore] = Field(default_factory=list)
    risk_flags: list[AnnotationRiskFlag] = Field(default_factory=list)
    veto_items: list[AnnotationVetoItem] = Field(default_factory=list)
    notes: str = ""


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "assets_root": str(_resolve_path(DEFAULT_ASSETS_ROOT)),
        "runs_root": str(_resolve_path(DEFAULT_RUNS_ROOT)),
        "registry": registry_status(),
        "tracing": tracing_status(),
    }


def get_registry_status() -> dict[str, Any]:
    return registry_status()


def list_registry_datasets() -> list[dict[str, Any]]:
    return registry_list_datasets()


def list_registry_experiments() -> list[dict[str, Any]]:
    experiments = registry_list_experiments()
    for item in experiments:
        run_id = str(item.get("run_id") or "")
        run_dir = str(item.get("run_dir") or "").strip()
        scene_id = str(item.get("scene_id") or "")
        run_summary: dict[str, Any] = {}
        if run_dir:
            try:
                run_summary = summarize_run_dir(run_dir)
            except Exception:
                run_summary = {}
        item["run_display_name"] = run_summary.get("run_display_name") or _run_display_name(
            run_id=run_id,
            scene_name="",
            scene_id=scene_id or _scene_id_from_run_id(run_id),
        )
        item["run_display_time"] = run_summary.get("run_display_time") or _run_display_time(run_id)
    return experiments


def index_existing_outputs() -> dict[str, Any]:
    asset_root = _resolve_path(DEFAULT_ASSETS_ROOT)
    run_root = _resolve_path(DEFAULT_RUNS_ROOT)
    asset_versions: dict[str, str] = {}
    indexed_assets = 0
    indexed_runs = 0
    indexed_cases = 0
    indexed_llm_calls = 0

    if asset_root.exists():
        for asset_dir in sorted(path for path in asset_root.iterdir() if path.is_dir()):
            try:
                assets = load_generated_assets(asset_dir)
            except Exception:
                continue
            asset_version_id = _ensure_asset_version(asset_dir, assets)
            asset_versions[assets.scene_asset.scene_id] = asset_version_id
            indexed_assets += 1

    if run_root.exists():
        for run_dir in sorted(path for path in run_root.iterdir() if path.is_dir()):
            conversations = load_conversation_results_safe(run_dir / "conversation_log.jsonl")
            if not conversations:
                continue
            scene_id = conversations[0].scene_id
            asset_dir = asset_root / scene_id
            asset_version_id = asset_versions.get(scene_id, "")
            if not asset_version_id and asset_dir.is_dir():
                try:
                    asset_version_id = _ensure_asset_version(asset_dir, load_generated_assets(asset_dir))
                except Exception:
                    asset_version_id = ""
            experiment_id = f"exp_{run_dir.name}"
            existing_experiment = experiment_exists(experiment_id)
            if not existing_experiment:
                create_experiment(
                    experiment_id=experiment_id,
                    run_id=run_dir.name,
                    asset_version_id=asset_version_id,
                    scene_id=scene_id,
                    run_dir=run_dir,
                    metadata={"indexed_from_outputs": True},
                )
            evaluations = load_case_evaluations_safe(run_dir / "case_evaluation.jsonl")
            evaluation_map = {item.case_id: item for item in evaluations}
            for conversation in conversations:
                record_case_run(
                    experiment_id=experiment_id,
                    asset_version_id=asset_version_id,
                    conversation=conversation,
                    evaluation=evaluation_map.get(conversation.case_id),
                    run_dir=run_dir,
                )
                indexed_cases += 1
            records = load_llm_call_records_safe(run_dir / "llm_calls.jsonl")
            if records:
                record_llm_calls(records=records, experiment_id=experiment_id, run_id=run_dir.name)
                indexed_llm_calls += len(records)
            if not existing_experiment:
                complete_experiment(
                    experiment_id=experiment_id,
                    metadata={
                        "indexed_from_outputs": True,
                        "cases": len(conversations),
                        "llm_calls": len(records),
                    },
                )
            indexed_runs += 1

    return {
        "indexed_assets": indexed_assets,
        "indexed_runs": indexed_runs,
        "indexed_cases": indexed_cases,
        "indexed_llm_calls": indexed_llm_calls,
        "registry": registry_status(),
    }


def get_prompt_status() -> dict[str, Any]:
    return prompt_status()


def sync_prompts(request: SyncPromptsRequest) -> dict[str, Any]:
    with trace_span(
        "api.sync_prompts",
        attributes={
            "dialogue_eval.operation": "sync_prompts",
            "dialogue_eval.dry_run": request.dry_run,
        },
        input_data=request,
    ) as span:
        results = sync_default_prompts(
            base_url=request.phoenix_base_url,
            model_name=request.model_name,
            dry_run=request.dry_run,
        )
        output = {
            "count": len(results),
            "results": [
                {
                    "name": item.name,
                    "version_id": item.version_id,
                    "status": item.status,
                    "error": item.error,
                }
                for item in results
            ],
        }
        span.set_output(output)
        return output


def extract_eval_standards(request: ExtractEvalStandardsRequest) -> dict[str, Any]:
    source_path = _resolve_path(request.excel_path)
    if is_csv_path(source_path):
        items = extract_markdown_from_csv(
            source_path,
            _resolve_path(request.output_dir),
            column=request.excel_column,
            start_row=request.excel_start_row,
        )
    else:
        items = extract_markdown_from_excel(
            source_path,
            _resolve_path(request.output_dir),
            column=request.excel_column,
            start_row=request.excel_start_row,
            sheet_name=request.excel_sheet,
        )
    return {
        "count": len(items),
        "items": [
            {
                "source_excel_path": item.source_excel_path,
                "source_sheet": item.source_sheet,
                "source_row": item.source_row,
                "source_column": item.source_column,
                "output_path": item.output_path,
                "title": item.title,
                "task_summary": _task_instruction_summary(Path(item.output_path), item.title),
                "content": _read_text_or_empty(Path(item.output_path)),
                "preview": _preview_text(Path(item.output_path)),
            }
            for item in items
        ],
    }


def generate_assets(request: GenerateAssetsRequest) -> dict[str, Any]:
    eval_standard_paths, extracted_items = _resolve_eval_standard_paths(request)
    asset_summaries: list[dict[str, Any]] = []
    output_root = _resolve_path(request.output_root)
    dataset_id = _record_dataset_for_generation(request)
    extracted_by_path = {str(_resolve_path(item["output_path"])): item for item in extracted_items}
    _set_job_progress(
        step="assets",
        step_status="in_progress",
        stage="生成测试设计",
        message=f"准备为 {len(eval_standard_paths)} 条任务指令生成场景资产。",
        percent=10,
    )

    with trace_span(
        "api.generate_assets",
        attributes={
            "dialogue_eval.operation": "generate_assets",
            "dialogue_eval.eval_standard_count": len(eval_standard_paths),
            "dialogue_eval.dataset_id": dataset_id,
        },
        input_data=request,
        metadata={"dataset_id": dataset_id},
    ) as span:
        for index, eval_standard_path in enumerate(eval_standard_paths, start=1):
            _set_job_progress(
                step="assets",
                step_status="in_progress",
                stage="生成测试设计",
                message=f"正在生成第 {index}/{len(eval_standard_paths)} 条任务指令的用户画像、覆盖矩阵和 case card。",
                percent=10 + int(25 * (index - 1) / max(len(eval_standard_paths), 1)),
                details={"current_eval_standard_path": str(eval_standard_path)},
            )
            task_instruction_id = _record_task_instruction_for_path(
                dataset_id=dataset_id,
                eval_standard_path=eval_standard_path,
                extracted_item=extracted_by_path.get(str(eval_standard_path)),
            )
            llm = _build_llm(
                fake_llm=request.fake_llm,
                role="asset_generator",
                model_config_path=request.model_config_path,
            )
            graph = build_asset_generation_graph(llm, output_root=output_root)
            result = graph.invoke(
                {
                    "eval_standard_path": str(eval_standard_path),
                    "business_config_path": _optional_path_str(request.business_config_path),
                    "generation_policy_path": _optional_path_str(request.generation_policy_path),
                    "dataset_id": dataset_id,
                    "task_instruction_id": task_instruction_id,
                }
            )
            asset_dir = Path(result["asset_dir"])
            export_llm_call_records(get_call_records([llm]), asset_dir)
            assets = load_generated_assets(asset_dir)
            asset_version_id = record_asset_version(
                asset_dir=asset_dir,
                assets=assets,
                task_instruction_id=task_instruction_id,
            )
            summary = summarize_asset_dir(asset_dir)
            summary.update(
                {
                    "dataset_id": dataset_id,
                    "task_instruction_id": task_instruction_id,
                    "asset_version_id": asset_version_id,
                }
            )
            asset_summaries.append(summary)

        _set_job_progress(
            step="assets",
            step_status="completed",
            stage="生成测试设计",
            message=f"已生成 {len(asset_summaries)} 个场景资产。",
            percent=35,
        )
        output = {
            "dataset_id": dataset_id,
            "count": len(asset_summaries),
            "assets": asset_summaries,
            "extracted_eval_standards": extracted_items,
        }
        span.set_output(output)
        return output


def start_evaluation(request: StartEvaluationRequest) -> dict[str, Any]:
    _set_job_progress(
        step="prepare",
        step_status="in_progress",
        stage="准备任务",
        message="正在读取任务输入和高级配置。",
        percent=2,
    )
    with trace_span(
        "api.start_evaluation",
        attributes={
            "dialogue_eval.operation": "start_evaluation",
            "dialogue_eval.limit": request.limit or 0,
            "dialogue_eval.skip_evaluation": request.skip_evaluation,
        },
        input_data=request,
    ) as span:
        _set_job_progress(
            step="prepare",
            step_status="completed",
            stage="准备任务",
            message="任务输入已确认，开始生成测试设计。",
            percent=6,
        )
        asset_result = generate_assets(
            GenerateAssetsRequest(
                eval_standard_file_path=request.eval_standard_file_path,
                eval_standard_path=request.eval_standard_path,
                eval_standard_excel_path=request.eval_standard_excel_path,
                selected_eval_standard_paths=request.selected_eval_standard_paths,
                excel_column=request.excel_column,
                excel_start_row=request.excel_start_row,
                excel_sheet=request.excel_sheet,
                extracted_output_dir=request.extracted_output_dir,
                business_config_path=request.business_config_path,
                generation_policy_path=request.generation_policy_path,
                model_config_path=request.model_config_path,
                output_root=request.asset_output_root,
                fake_llm=request.fake_llm,
            )
        )
        run_summaries = []
        assets = asset_result.get("assets", [])
        for index, asset in enumerate(assets, start=1):
            asset_dir = str(asset.get("asset_dir") or asset.get("display_path") or "")
            if not asset_dir:
                raise ValueError("Generated asset is missing asset_dir.")
            _set_job_progress(
                step="conversation",
                step_status="in_progress",
                stage="运行模拟对话",
                message=f"正在运行第 {index}/{len(assets)} 个场景：{asset.get('scene_name') or asset.get('scene_id') or asset_dir}。",
                percent=35 + int(35 * (index - 1) / max(len(assets), 1)),
                details={"asset_dir": asset_dir},
            )
            run_summary = run_evaluation(
                RunEvaluationRequest(
                    assets_path=asset_dir,
                    business_config_path=request.business_config_path,
                    model_config_path=request.model_config_path,
                    output_root=request.run_output_root,
                    limit=request.limit,
                    skip_evaluation=request.skip_evaluation,
                    fake_llm=request.fake_llm,
                )
            )
            run_summary.update(
                {
                    "scene_id": asset.get("scene_id"),
                    "scene_name": asset.get("scene_name"),
                    "source_asset_dir": asset_dir,
                }
            )
            run_summaries.append(run_summary)

        _set_job_progress(
            step="reports",
            step_status="completed",
            stage="完成评测",
            message=f"已完成 {len(run_summaries)} 个评测运行。",
            percent=100,
        )
        output = {
            "dataset_id": asset_result.get("dataset_id", ""),
            "asset_count": len(asset_result.get("assets", [])),
            "run_count": len(run_summaries),
            "assets": asset_result.get("assets", []),
            "runs": run_summaries,
            "extracted_eval_standards": asset_result.get("extracted_eval_standards", []),
        }
        span.set_output(output)
        return output


def start_evaluation_job(request: StartEvaluationRequest) -> dict[str, Any]:
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "排队中",
        "message": "评测任务已创建，等待后台执行。",
        "percent": 0,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "started_at": "",
        "completed_at": "",
        "error": "",
        "result": None,
        "details": {},
        "steps": _default_evaluation_steps(),
    }
    with _evaluation_jobs_lock:
        _evaluation_jobs[job_id] = job
    thread = Thread(target=_run_evaluation_job, args=(job_id, request), daemon=True)
    thread.start()
    return get_evaluation_job(job_id)


def get_evaluation_job(job_id: str) -> dict[str, Any]:
    with _evaluation_jobs_lock:
        job = _evaluation_jobs.get(job_id)
        if not job:
            raise FileNotFoundError(f"Evaluation job not found: {job_id}")
        return json.loads(json.dumps(job, ensure_ascii=False, default=str))


def _run_evaluation_job(job_id: str, request: StartEvaluationRequest) -> None:
    token = _progress_job_id.set(job_id)
    try:
        _set_job_progress(
            status="running",
            step="prepare",
            step_status="in_progress",
            stage="准备任务",
            message="后台评测已启动。",
            percent=1,
            started=True,
        )
        result = start_evaluation(request)
        _set_job_progress(
            status="completed",
            stage="完成评测",
            message="评测完成，报告已生成。",
            percent=100,
            result=result,
            completed=True,
        )
    except Exception as exc:
        _set_job_progress(
            status="failed",
            stage="评测失败",
            message=str(exc),
            error=str(exc),
            completed=True,
        )
    finally:
        _progress_job_id.reset(token)


def _default_evaluation_steps() -> list[dict[str, str]]:
    return [
        {"key": "prepare", "label": "准备任务", "status": "pending"},
        {"key": "assets", "label": "生成测试设计", "status": "pending"},
        {"key": "conversation", "label": "运行模拟对话", "status": "pending"},
        {"key": "scoring", "label": "评分与证据生成", "status": "pending"},
        {"key": "reports", "label": "导出报告", "status": "pending"},
    ]


def _set_job_progress(
    *,
    status: str | None = None,
    step: str | None = None,
    step_status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    percent: int | None = None,
    details: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    job_id = _progress_job_id.get()
    if not job_id:
        return
    with _evaluation_jobs_lock:
        job = _evaluation_jobs.get(job_id)
        if not job:
            return
        if status:
            job["status"] = status
        if stage:
            job["stage"] = stage
        if message:
            job["message"] = message
        if percent is not None:
            job["percent"] = max(0, min(100, int(percent)))
        if details is not None:
            job["details"] = details
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
        if started and not job.get("started_at"):
            job["started_at"] = utc_now_iso()
        if completed:
            job["completed_at"] = utc_now_iso()
        if step:
            for item in job["steps"]:
                if item["key"] == step:
                    item["status"] = step_status or item["status"]
                elif step_status == "in_progress" and item["status"] == "in_progress":
                    item["status"] = "completed"
        job["updated_at"] = utc_now_iso()


def run_evaluation(request: RunEvaluationRequest) -> dict[str, Any]:
    asset_dir = _resolve_asset_dir(scene_id=request.scene_id, assets_path=request.assets_path)
    assets = load_generated_assets(asset_dir)
    business_config = _load_business_config(request.business_config_path)
    asset_version_id = _ensure_asset_version(asset_dir, assets)
    _set_job_progress(
        step="conversation",
        step_status="in_progress",
        stage="运行模拟对话",
        message=f"正在初始化客服模型、用户模型和 judge：{assets.scene_asset.scene_name}。",
        percent=38,
        details={"scene_id": assets.scene_asset.scene_id, "asset_dir": str(asset_dir)},
    )

    agent_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="agent",
        model_config_path=request.model_config_path,
    )
    user_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="user",
        model_config_path=request.model_config_path,
    )
    judge_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="judge",
        model_config_path=request.model_config_path,
    )
    state_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="state_updater",
        model_config_path=request.model_config_path,
    )
    evaluator_llm = (
        None
        if request.skip_evaluation
        else _build_llm(
            fake_llm=request.fake_llm,
            role="evaluator",
            model_config_path=request.model_config_path,
        )
    )

    output_root = _resolve_path(request.output_root)
    run_id = make_run_id(assets.scene_asset.scene_id, output_root)
    experiment_id = f"exp_{run_id}"
    output_dir = output_root / run_id
    case_cards = (
        assets.case_cards.cases[: request.limit]
        if request.limit
        else assets.case_cards.cases
    )
    graph = build_conversation_graph(
        agent_llm=agent_llm,
        user_llm=user_llm,
        judge_llm=judge_llm,
        state_llm=state_llm,
    )
    create_experiment(
        experiment_id=experiment_id,
        run_id=run_id,
        asset_version_id=asset_version_id,
        scene_id=assets.scene_asset.scene_id,
        run_dir=output_dir,
        model_config_path=request.model_config_path,
        business_config_path=request.business_config_path or "",
        limit_count=request.limit,
        skip_evaluation=request.skip_evaluation,
        fake_llm=request.fake_llm,
        metadata={"asset_dir": str(asset_dir)},
    )

    results: list[ConversationResult] = []
    records: list[Any] = []
    with trace_span(
        "api.run_evaluation",
        attributes={
            "dialogue_eval.operation": "run_evaluation",
            "dialogue_eval.experiment_id": experiment_id,
            "dialogue_eval.run_id": run_id,
            "dialogue_eval.scene_id": assets.scene_asset.scene_id,
            "dialogue_eval.asset_version_id": asset_version_id,
            "dialogue_eval.case_count": len(case_cards),
        },
        input_data=request,
        session_id=run_id,
        metadata={
            "experiment_id": experiment_id,
            "asset_version_id": asset_version_id,
            "run_id": run_id,
            "scene_id": assets.scene_asset.scene_id,
        },
    ) as run_span:
        for index, case_card in enumerate(case_cards, start=1):
            _set_job_progress(
                step="conversation",
                step_status="in_progress",
                stage="运行模拟对话",
                message=f"正在对话第 {index}/{len(case_cards)} 个 case：{case_card.case_id}。",
                percent=40 + int(35 * (index - 1) / max(len(case_cards), 1)),
                details={
                    "run_id": run_id,
                    "case_id": case_card.case_id,
                    "scene_id": assets.scene_asset.scene_id,
                    "case_index": index,
                    "case_count": len(case_cards),
                },
            )
            with trace_span(
                "case.run",
                attributes={
                    "dialogue_eval.experiment_id": experiment_id,
                    "dialogue_eval.run_id": run_id,
                    "dialogue_eval.asset_version_id": asset_version_id,
                    "dialogue_eval.case_id": case_card.case_id,
                    "dialogue_eval.scene_id": case_card.scene_id,
                    "dialogue_eval.case_index": index,
                },
                input_data=case_card,
                session_id=run_id,
                metadata={
                    "experiment_id": experiment_id,
                    "asset_version_id": asset_version_id,
                    "run_id": run_id,
                    "case_id": case_card.case_id,
                    "scene_id": case_card.scene_id,
                },
            ) as case_span:
                result = graph.invoke(
                    {
                        "run_id": run_id,
                        "experiment_id": experiment_id,
                        "asset_version_id": asset_version_id,
                        "scene_asset": assets.scene_asset,
                        "coverage_plan": assets.coverage_plan,
                        "user_profiles": assets.user_profiles,
                        "case_card": case_card,
                        "business_config": business_config,
                    },
                    {"recursion_limit": case_card.stop_policy.max_turns * 6 + 10},
                )
                conversation_result = result["conversation_result"]
                case_span.set_output(
                    {
                        "coverage_success": conversation_result.coverage_success,
                        "turn_count": len(conversation_result.turns),
                        "missing_targets": conversation_result.missing_targets,
                    }
                )
            results.append(result["conversation_result"])
            export_run_reports(results, output_dir)

        _set_job_progress(
            step="conversation",
            step_status="completed",
            stage="运行模拟对话",
            message=f"已完成 {len(results)} 个 case 的客服-用户模拟对话。",
            percent=75,
            details={"run_id": run_id, "run_dir": str(output_dir)},
        )
        export_run_reports(results, output_dir)
        evaluation_count = 0
        evaluations = []
        if evaluator_llm is not None:
            _set_job_progress(
                step="scoring",
                step_status="in_progress",
                stage="评分与证据生成",
                message=f"正在依据评分量表评估 {len(results)} 个 case。",
                percent=78,
                details={"run_id": run_id, "case_count": len(results)},
            )
            evaluations = evaluate_results(
                evaluator_llm=evaluator_llm,
                assets=assets,
                results=results,
                business_config=business_config,
                experiment_id=experiment_id,
                asset_version_id=asset_version_id,
            )
            evaluation_count = len(evaluations)
            export_evaluation_reports(evaluations, output_dir, conversations=results)
            _set_job_progress(
                step="scoring",
                step_status="completed",
                stage="评分与证据生成",
                message=f"已完成 {evaluation_count} 个 case 的量化评分。",
                percent=88,
                details={"run_id": run_id, "evaluation_count": evaluation_count},
            )
        else:
            _set_job_progress(
                step="scoring",
                step_status="completed",
                stage="评分与证据生成",
                message="已按配置跳过评分，只保留模拟对话结果。",
                percent=88,
                details={"run_id": run_id},
            )
        _set_job_progress(
            step="reports",
            step_status="in_progress",
            stage="导出报告",
            message="正在导出 Markdown、CSV、case 子报告和模型调用记录。",
            percent=92,
            details={"run_id": run_id, "run_dir": str(output_dir)},
        )
        export_case_artifact_bundles(
            conversations=results,
            evaluations=evaluations,
            case_cards=assets.case_cards.cases,
            output_dir=output_dir,
        )

        records = get_call_records([agent_llm, user_llm, judge_llm, state_llm, evaluator_llm])
        export_llm_call_records(records, output_dir)
        evaluation_map = {item.case_id: item for item in evaluations}
        for conversation in results:
            record_case_run(
                experiment_id=experiment_id,
                asset_version_id=asset_version_id,
                conversation=conversation,
                evaluation=evaluation_map.get(conversation.case_id),
                run_dir=output_dir,
            )
        record_llm_calls(records=records, experiment_id=experiment_id, run_id=run_id)
        _set_job_progress(
            step="reports",
            step_status="in_progress",
            stage="沉淀运行记录",
            message="正在写入实验库和运行摘要。",
            percent=96,
            details={"run_id": run_id, "run_dir": str(output_dir)},
        )
        summary = summarize_run_dir(output_dir)
        summary.update(
            {
                "experiment_id": experiment_id,
                "asset_version_id": asset_version_id,
                "asset_dir": str(asset_dir),
                "cases_run": len(results),
                "cases_evaluated": evaluation_count,
            }
        )
        complete_experiment(
            experiment_id=experiment_id,
            metadata={
                "cases_run": len(results),
                "cases_evaluated": evaluation_count,
                "llm_call_count": len(records),
            },
        )
        run_span.set_output(summary)
        return summary


def evaluate_existing_run(request: EvaluateRunRequest) -> dict[str, Any]:
    if not request.run_dir:
        raise ValueError("run_dir is required.")

    asset_dir = _resolve_asset_dir(scene_id=request.scene_id, assets_path=request.assets_path)
    run_dir = _resolve_path(request.run_dir)
    assets = load_generated_assets(asset_dir)
    asset_version_id = _ensure_asset_version(asset_dir, assets)
    results = load_conversation_results(run_dir / "conversation_log.jsonl")
    business_config = _load_business_config(request.business_config_path)
    experiment_id = f"eval_{run_dir.name}"
    evaluator_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="evaluator",
        model_config_path=request.model_config_path,
    )
    create_experiment(
        experiment_id=experiment_id,
        run_id=run_dir.name,
        asset_version_id=asset_version_id,
        scene_id=assets.scene_asset.scene_id,
        run_dir=run_dir,
        model_config_path=request.model_config_path,
        business_config_path=request.business_config_path or "",
        skip_evaluation=False,
        fake_llm=request.fake_llm,
        metadata={"mode": "evaluate_existing_run", "asset_dir": str(asset_dir)},
    )
    with trace_span(
        "api.evaluate_existing_run",
        attributes={
            "dialogue_eval.operation": "evaluate_existing_run",
            "dialogue_eval.experiment_id": experiment_id,
            "dialogue_eval.run_id": run_dir.name,
            "dialogue_eval.asset_version_id": asset_version_id,
            "dialogue_eval.case_count": len(results),
        },
        input_data=request,
        session_id=run_dir.name,
        metadata={
            "experiment_id": experiment_id,
            "asset_version_id": asset_version_id,
            "run_id": run_dir.name,
            "scene_id": assets.scene_asset.scene_id,
        },
    ) as span:
        evaluations = evaluate_results(
            evaluator_llm=evaluator_llm,
            assets=assets,
            results=results,
            business_config=business_config,
            experiment_id=experiment_id,
            asset_version_id=asset_version_id,
        )
        export_evaluation_reports(evaluations, run_dir, conversations=results)
        export_case_artifact_bundles(
            conversations=results,
            evaluations=evaluations,
            case_cards=assets.case_cards.cases,
            output_dir=run_dir,
        )
        records = get_call_records([evaluator_llm])
        export_llm_call_records(records, run_dir)
        evaluation_map = {item.case_id: item for item in evaluations}
        for conversation in results:
            record_case_run(
                experiment_id=experiment_id,
                asset_version_id=asset_version_id,
                conversation=conversation,
                evaluation=evaluation_map.get(conversation.case_id),
                run_dir=run_dir,
            )
        record_llm_calls(records=records, experiment_id=experiment_id, run_id=run_dir.name)
        summary = summarize_run_dir(run_dir)
        summary.update(
            {
                "experiment_id": experiment_id,
                "asset_version_id": asset_version_id,
                "asset_dir": str(asset_dir),
                "cases_evaluated": len(evaluations),
            }
        )
        complete_experiment(
            experiment_id=experiment_id,
            metadata={
                "cases_evaluated": len(evaluations),
                "llm_call_count": len(records),
            },
        )
        span.set_output(summary)
        return summary


def list_assets(*, include_legacy: bool = False) -> list[dict[str, Any]]:
    root = _resolve_path(DEFAULT_ASSETS_ROOT)
    if not root.exists():
        return []
    summaries = [
        summarize_asset_dir(path)
        for path in sorted(root.iterdir())
        if path.is_dir()
    ]
    if include_legacy:
        return summaries
    return [item for item in summaries if not item.get("legacy")]


def summarize_asset_dir(asset_dir: str | Path) -> dict[str, Any]:
    path = _resolve_path(asset_dir)
    base: dict[str, Any] = {
        "scene_id": path.name,
        "asset_dir": str(path),
        "display_path": _display_path(path),
        "valid": False,
    }
    try:
        assets = load_generated_assets(path)
    except Exception as exc:
        base["error"] = str(exc)
        return base

    current_schema = (
        (path / "materialized_eval_standard.md").is_file()
        and (path / "variable_assignments.yaml").is_file()
    )

    base.update(
        {
            "valid": True,
            "legacy": not current_schema,
            "asset_schema": "materialized" if current_schema else "legacy",
            "scene_id": assets.scene_asset.scene_id,
            "scene_name": assets.scene_asset.scene_name,
            "business_goal": assets.scene_asset.business_goal,
            "case_count": len(assets.case_cards.cases),
            "profile_count": len(assets.user_profiles.profiles),
            "coverage_label_count": len(assets.coverage_plan.coverage_labels),
            "coverage_matrix_row_count": len(assets.coverage_matrix.rows) if assets.coverage_matrix else 0,
            "planned_case_count": (
                sum(item.case_count for item in assets.case_generation_plan.allocations)
                if assets.case_generation_plan
                else len(assets.case_cards.cases)
            ),
            "scoring_dimension_count": len(assets.scoring_rubric.dimensions),
            "pass_threshold": assets.scoring_rubric.pass_threshold,
            "files": _existing_files(path, ASSET_FILES),
        }
    )
    return base


def list_runs() -> list[dict[str, Any]]:
    root = _resolve_path(DEFAULT_RUNS_ROOT)
    if not root.exists():
        return []
    return [
        summarize_run_dir(path)
        for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True)
        if path.is_dir()
    ]


def summarize_run_dir(run_dir: str | Path) -> dict[str, Any]:
    path = _resolve_path(run_dir)
    conversations = _read_jsonl_dicts(path / "conversation_log.jsonl")
    evaluations = _read_jsonl_dicts(path / "case_evaluation.jsonl")
    scene_id, scene_name = _run_scene_summary(path, conversations)
    run_display_time = _run_display_time(path.name)
    run_display_name = _run_display_name(
        run_id=path.name,
        scene_name=scene_name,
        scene_id=scene_id,
    )
    successful_cases = sum(1 for item in conversations if item.get("coverage_success"))
    passed_cases = sum(1 for item in evaluations if item.get("passed"))
    risk_count = sum(len(item.get("risk_deductions") or []) for item in evaluations)
    veto_count = sum(1 for item in evaluations if item.get("veto_triggered"))
    case_artifacts_dir = path / "cases"
    case_artifact_count = (
        len([item for item in case_artifacts_dir.glob("*") if item.is_dir()])
        if case_artifacts_dir.is_dir()
        else 0
    )
    scores = [
        float(item["total_score"])
        for item in evaluations
        if isinstance(item.get("total_score"), (int, float))
    ]
    return {
        "run_id": path.name,
        "run_display_name": run_display_name,
        "run_display_time": run_display_time,
        "scene_id": scene_id,
        "scene_name": scene_name,
        "run_dir": str(path),
        "display_path": _display_path(path),
        "case_count": len(conversations),
        "coverage_success_count": successful_cases,
        "evaluation_count": len(evaluations),
        "passed_count": passed_cases,
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "veto_count": veto_count,
        "risk_count": risk_count,
        "case_artifact_count": case_artifact_count,
        "files": _existing_files(path, RUN_REPORT_FILES),
        "case_reports": list_case_reports(path),
    }


def read_asset_file(scene_id: str, filename: str) -> str:
    if filename not in ASSET_FILES:
        raise ValueError(f"Unsupported asset file: {filename}")
    path = _resolve_path(DEFAULT_ASSETS_ROOT) / scene_id / filename
    return _read_existing_text(path)


def read_run_report(run_id: str, filename: str) -> str:
    if filename not in RUN_REPORT_FILES:
        raise ValueError(f"Unsupported report file: {filename}")
    path = _resolve_path(DEFAULT_RUNS_ROOT) / run_id / filename
    return _read_existing_text(path)


def list_case_reports(run_dir: str | Path) -> list[str]:
    path = _resolve_path(run_dir) / "case_reports"
    if not path.exists():
        return []
    return [item.stem for item in sorted(path.glob("*.md"))]


def _run_scene_summary(run_dir: Path, conversations: list[dict[str, Any]]) -> tuple[str, str]:
    scene_id = ""
    if conversations:
        scene_id = str(conversations[0].get("scene_id") or "")
    if not scene_id:
        scene_id = _scene_id_from_run_id(run_dir.name)

    scene_name = ""
    if scene_id:
        scene_name = _scene_title_from_assets(scene_id)
    return scene_id, scene_name


def _scene_title_from_assets(scene_id: str) -> str:
    for asset_file in _scene_asset_files(scene_id):
        try:
            payload = read_structured_file(asset_file)
        except Exception:
            continue
        if str(payload.get("scene_id") or "") != scene_id:
            continue
        scene_name = str(payload.get("scene_name") or "").strip()
        source_path = str(payload.get("source_eval_standard_path") or "").strip()
        business_goal = str(payload.get("business_goal") or "").strip()
        task_summary = _task_summary_from_eval_standard(source_path)
        if task_summary and _is_generic_scene_name(scene_name):
            return task_summary
        if scene_name and not _is_generic_scene_name(scene_name):
            return scene_name
        if task_summary:
            return task_summary
        if business_goal and not _is_generic_scene_name(business_goal):
            return business_goal
    return ""


def _scene_asset_files(scene_id: str) -> list[Path]:
    files: list[Path] = []
    current = _resolve_path(DEFAULT_ASSETS_ROOT) / scene_id / "scene_asset.yaml"
    if current.is_file():
        files.append(current)
    archived_root = _resolve_path("outputs/archived_assets")
    if archived_root.is_dir():
        for path in sorted(archived_root.glob("*/scene_asset.yaml")):
            if path not in files:
                files.append(path)
    return files


def _is_generic_scene_name(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    generic_values = {
        "模型生成场景",
        "生成场景",
        "根据评测标准完成一次外呼任务。",
        "根据评测标准完成一次外呼任务",
    }
    return text in generic_values


def _task_summary_from_eval_standard(source_path: str) -> str:
    if not source_path:
        return ""
    path = _resolve_path(source_path)
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    for index, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("# task:") or lower.startswith("## task:"):
            return _clean_task_summary(stripped.split(":", 1)[1])
        if lower in {"# task", "## task"}:
            for next_line in lines[index + 1 :]:
                candidate = next_line.strip()
                if candidate:
                    return _clean_task_summary(candidate)
    return ""


def _clean_task_summary(value: str) -> str:
    text = value.strip()
    while text.startswith("#"):
        text = text[1:].strip()
    return text


def _scene_id_from_run_id(run_id: str) -> str:
    parts = run_id.split("_")
    if len(parts) <= 3 or parts[0] != "run":
        return ""
    scene_parts = parts[3:]
    if scene_parts and len(scene_parts[-1]) == 2 and scene_parts[-1].isdigit():
        scene_parts = scene_parts[:-1]
    return "_".join(scene_parts)


def _run_display_time(run_id: str) -> str:
    parts = run_id.split("_")
    if len(parts) < 3 or parts[0] != "run":
        return ""
    date_part = parts[1]
    time_part = parts[2]
    if len(date_part) != 8 or len(time_part) != 6:
        return ""
    if not date_part.isdigit() or not time_part.isdigit():
        return ""
    try:
        value = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
    except ValueError:
        return ""
    return value.strftime("%Y年%m月%d日 %H:%M:%S")


def _run_display_name(
    *,
    run_id: str,
    scene_name: str,
    scene_id: str,
) -> str:
    return _compact_run_title(scene_name or scene_id or run_id, scene_id=scene_id)


def _compact_run_title(value: str, *, scene_id: str) -> str:
    from_scene_id = _title_from_scene_id(scene_id)
    text = _remove_title_punctuation(value)
    if text and len(text) <= 12 and _has_chinese(text) and not _is_generic_scene_name(text):
        return text
    if from_scene_id:
        return from_scene_id
    from_task = _title_from_task_text(text)
    if from_task:
        return from_task
    if text and _has_chinese(text):
        return text[:12]
    return "评测任务"


def _has_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _title_from_scene_id(scene_id: str) -> str:
    tokens = [item for item in scene_id.split("_") if item]
    if not tokens:
        return ""
    translated = []
    token_map = {
        "feimaotui": "飞毛腿",
        "meituan": "美团",
        "contract": "合同",
        "notify": "通知",
        "notification": "通知",
        "live": "直播",
        "stream": "直播",
        "course": "课程",
        "publish": "发布",
        "upgrade": "升级",
    }
    for token in tokens:
        label = token_map.get(token.lower())
        if label and label not in translated:
            translated.append(label)
    if not translated:
        return ""
    if "直播" in translated and "升级" in translated:
        if "课程" in translated:
            return "课程直播升级"
        return "直播升级通知"
    if "飞毛腿" in translated and "合同" in translated:
        return "飞毛腿合同通知"
    if "合同" in translated and "通知" not in translated:
        translated.append("通知")
    return "".join(translated)[:12]


def _title_from_task_text(text: str) -> str:
    if not text:
        return ""
    if "直播" in text and ("升级" in text or "新增" in text or "选项" in text):
        if "课程" in text:
            return "课程直播升级"
        return "直播选项升级"
    if "飞毛腿" in text and "合同" in text:
        return "飞毛腿合同通知"
    if "合同" in text and ("签署" in text or "生效" in text):
        return "合同生效通知"
    if "配送" in text and ("提醒" in text or "任务" in text):
        return "配送任务提醒"
    return ""


def _remove_title_punctuation(value: str) -> str:
    punctuation = set(' \t\r\n，。,.；;："“”"\'（）()【】[]、·!！?？')
    return "".join(char for char in value.strip() if char not in punctuation)


def read_case_report(run_id: str, case_id: str) -> str:
    safe_case_id = Path(case_id).name
    path = _resolve_path(DEFAULT_RUNS_ROOT) / run_id / "case_reports" / f"{safe_case_id}.md"
    return _read_existing_text(path)


def get_annotation_run(run_id: str) -> dict[str, Any]:
    safe_run_id = Path(run_id).name
    run_dir = _resolve_path(DEFAULT_RUNS_ROOT) / safe_run_id
    conversations = load_conversation_results_safe(run_dir / "conversation_log.jsonl")
    if not conversations:
        raise FileNotFoundError(f"Conversation log not found or empty for run: {safe_run_id}")

    scene_id = conversations[0].scene_id
    asset_dir = _resolve_path(DEFAULT_ASSETS_ROOT) / scene_id
    assets = load_generated_assets(asset_dir)
    annotations = _load_annotation_records(safe_run_id)
    coverage_by_label = {
        item.label: item.model_dump(mode="json")
        for item in assets.coverage_plan.coverage_labels
    }
    case_by_id = {
        item.case_id: item.model_dump(mode="json")
        for item in assets.case_cards.cases
    }
    cases = []
    for conversation in conversations:
        conversation_data = conversation.model_dump(mode="json")
        case_card = case_by_id.get(conversation.case_id, {})
        cases.append(
            {
                **conversation_data,
                "case_name": case_card.get("case_name", ""),
                "profile_id": case_card.get("profile_id", ""),
                "target_definitions": [
                    coverage_by_label.get(target, {"label": target})
                    for target in conversation.planned_targets
                ],
                "annotation": annotations.get(conversation.case_id),
            }
        )
    completed_annotations = [
        item.get("annotation")
        for item in cases
        if _annotation_is_complete(item.get("annotation"))
    ]

    return {
        "run_id": safe_run_id,
        "scene_id": scene_id,
        "asset_dir": str(asset_dir),
        "annotation_path": str(_annotation_file(safe_run_id)),
        "total_cases": len(cases),
        "annotated_count": len(completed_annotations),
        "scoring_rubric": assets.scoring_rubric.model_dump(mode="json"),
        "dimension_check_templates": _dimension_check_templates(assets.scoring_rubric),
        "coverage_labels": [
            item.model_dump(mode="json")
            for item in assets.coverage_plan.coverage_labels
        ],
        "cases": cases,
    }


def save_case_annotation(
    *,
    run_id: str,
    case_id: str,
    request: SaveAnnotationRequest,
) -> dict[str, Any]:
    safe_run_id = Path(run_id).name
    safe_case_id = Path(case_id).name
    run_dir = _resolve_path(DEFAULT_RUNS_ROOT) / safe_run_id
    conversations = load_conversation_results_safe(run_dir / "conversation_log.jsonl")
    conversation = next((item for item in conversations if item.case_id == safe_case_id), None)
    if conversation is None:
        raise FileNotFoundError(f"Case not found: {safe_case_id}")

    assets = load_generated_assets(_resolve_path(DEFAULT_ASSETS_ROOT) / conversation.scene_id)
    target_checks = _normalize_target_checks(
        planned_targets=conversation.planned_targets,
        target_checks=request.target_checks,
        covered_targets=request.covered_targets,
    )
    covered_targets = [
        item["target"]
        for item in target_checks
        if item["status"] in {"satisfied", "partial"}
    ]
    partial_targets = [
        item["target"]
        for item in target_checks
        if item["status"] == "partial"
    ]
    missing_targets = [
        item["target"]
        for item in target_checks
        if item["status"] in {"missing", "unreviewed"}
    ]

    dimension_checks = _normalize_dimension_checks(
        scoring_rubric=assets.scoring_rubric,
        dimension_checks=request.dimension_checks,
    )
    if dimension_checks:
        normalized_dimensions = _score_dimensions_from_checks(
            scoring_rubric=assets.scoring_rubric,
            dimension_checks=dimension_checks,
        )
    else:
        normalized_dimensions = _normalize_legacy_dimension_scores(
            scoring_rubric=assets.scoring_rubric,
            dimension_scores=request.dimension_scores,
        )

    risk_flags = [
        {
            **item.model_dump(mode="json"),
            "deduction": round(max(0.0, float(item.deduction)), 2),
        }
        for item in request.risk_flags
        if item.rule_id
    ]
    raw_score = sum(item["score"] for item in normalized_dimensions)
    risk_deduction_total = sum(item["deduction"] for item in risk_flags)
    computed_human_score = max(
        0.0,
        min(float(assets.scoring_rubric.total_score), raw_score - risk_deduction_total),
    )
    veto_items = [
        item.model_dump(mode="json")
        for item in request.veto_items
        if item.rule_id
    ]
    veto_triggered = bool(veto_items)
    review_complete = _annotation_review_complete(target_checks, dimension_checks)
    human_score = round(computed_human_score, 2) if review_complete else None
    raw_score_value = round(raw_score, 2) if review_complete else None
    human_passed = (
        computed_human_score >= assets.scoring_rubric.pass_threshold and not veto_triggered
        if review_complete
        else None
    )
    annotation = {
        "schema_version": "1.1",
        "run_id": safe_run_id,
        "case_id": safe_case_id,
        "scene_id": conversation.scene_id,
        "annotator_id": request.annotator_id.strip() or "human_01",
        "annotated_at": utc_now_iso(),
        "score_status": "complete" if review_complete else "draft",
        "human_passed": human_passed,
        "human_score": human_score,
        "raw_score": raw_score_value,
        "risk_deduction_total": round(risk_deduction_total, 2) if review_complete else None,
        "pass_threshold": assets.scoring_rubric.pass_threshold,
        "review_complete": review_complete,
        "target_checks": target_checks,
        "covered_targets": covered_targets,
        "partial_targets": partial_targets,
        "missing_targets": missing_targets,
        "dimension_checks": dimension_checks,
        "dimension_scores": normalized_dimensions,
        "risk_flags": risk_flags,
        "veto_triggered": veto_triggered,
        "veto_items": veto_items,
        "notes": request.notes,
    }

    annotations = _load_annotation_records(safe_run_id)
    annotations[safe_case_id] = annotation
    _write_annotation_records(safe_run_id, annotations)
    return annotation


def _dimension_check_templates(scoring_rubric: Any) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for dimension in scoring_rubric.dimensions:
        rules = list(dimension.deduction_rules)
        if not rules:
            fallback = dimension.full_score_standard or dimension.description or dimension.name
            rules = [fallback]
        default_deduction = float(dimension.weight) / max(len(rules), 1)
        for index, rule in enumerate(rules, start=1):
            explicit_deduction = _deduction_from_rule_text(rule)
            templates.append(
                {
                    "check_id": f"{dimension.dimension_id}__check_{index:02d}",
                    "dimension_id": dimension.dimension_id,
                    "dimension_name": dimension.name,
                    "dimension_weight": float(dimension.weight),
                    "description": rule,
                    "deduction": round(explicit_deduction if explicit_deduction is not None else default_deduction, 2),
                    "status": "unreviewed",
                    "evidence_required": dimension.evidence_required,
                    "deduction_basis": "explicit_rule_text" if explicit_deduction is not None else "dimension_weight_even_split",
                }
            )
    return templates


def _deduction_from_rule_text(text: str) -> Optional[float]:
    marker_index = text.find("扣")
    if marker_index < 0:
        return None
    number_chars: list[str] = []
    for char in text[marker_index + 1:]:
        if char.isdigit() or char == ".":
            number_chars.append(char)
            continue
        if number_chars:
            break
    if not number_chars:
        return None
    try:
        return float("".join(number_chars))
    except ValueError:
        return None


def _normalize_target_checks(
    *,
    planned_targets: list[str],
    target_checks: list[AnnotationTargetCheck],
    covered_targets: list[str],
) -> list[dict[str, Any]]:
    allowed_statuses = {"unreviewed", "satisfied", "partial", "missing", "not_applicable"}
    submitted_by_target = {
        item.target: item
        for item in target_checks
        if item.target
    }
    covered = set(covered_targets)
    normalized = []
    for target in planned_targets:
        item = submitted_by_target.get(target)
        if item:
            status = item.status if item.status in allowed_statuses else "unreviewed"
            normalized.append(
                {
                    "target": target,
                    "status": status,
                    "turn_index": item.turn_index,
                    "evidence": item.evidence,
                }
            )
        else:
            normalized.append(
                {
                    "target": target,
                    "status": "satisfied" if target in covered else "unreviewed",
                    "turn_index": None,
                    "evidence": "",
                }
            )
    return normalized


def _normalize_dimension_checks(
    *,
    scoring_rubric: Any,
    dimension_checks: list[AnnotationDimensionCheck],
) -> list[dict[str, Any]]:
    if not dimension_checks:
        return []
    allowed_statuses = {"unreviewed", "not_triggered", "partial", "triggered", "not_applicable"}
    template_by_id = {
        item["check_id"]: item
        for item in _dimension_check_templates(scoring_rubric)
    }
    normalized = []
    for item in dimension_checks:
        if not item.check_id or not item.dimension_id:
            continue
        template = template_by_id.get(item.check_id, {})
        status = item.status if item.status in allowed_statuses else "unreviewed"
        deduction = template.get("deduction", item.deduction)
        normalized.append(
            {
                "check_id": item.check_id,
                "dimension_id": item.dimension_id,
                "dimension_name": template.get("dimension_name", ""),
                "description": item.description or template.get("description", ""),
                "deduction": round(max(0.0, float(deduction)), 2),
                "status": status,
                "turn_index": item.turn_index,
                "evidence": item.evidence,
            }
        )
    return normalized


def _score_dimensions_from_checks(
    *,
    scoring_rubric: Any,
    dimension_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks_by_dimension: dict[str, list[dict[str, Any]]] = {}
    for check in dimension_checks:
        checks_by_dimension.setdefault(check["dimension_id"], []).append(check)

    normalized_dimensions = []
    for dimension in scoring_rubric.dimensions:
        checks = checks_by_dimension.get(dimension.dimension_id, [])
        deduction_total = 0.0
        triggered_descriptions = []
        unreviewed_count = 0
        for check in checks:
            status = check.get("status", "unreviewed")
            multiplier = {
                "not_triggered": 0.0,
                "not_applicable": 0.0,
                "partial": 0.5,
                "triggered": 1.0,
                "unreviewed": 1.0,
            }.get(status, 1.0)
            deduction_total += float(check.get("deduction", 0.0)) * multiplier
            if status in {"partial", "triggered"}:
                triggered_descriptions.append(str(check.get("description", "")))
            if status == "unreviewed":
                unreviewed_count += 1

        weight = float(dimension.weight)
        score = max(0.0, min(weight, weight - deduction_total))
        if triggered_descriptions:
            reason = "触发扣分事实：" + "；".join(item for item in triggered_descriptions if item)
        elif unreviewed_count:
            reason = f"仍有 {unreviewed_count} 个事实项未判断，暂按扣分处理。"
        else:
            reason = "未标记维度内扣分事实。"
        normalized_dimensions.append(
            {
                "dimension_id": dimension.dimension_id,
                "name": dimension.name,
                "weight": weight,
                "score": round(score, 2),
                "reason": reason,
            }
        )
    return normalized_dimensions


def _normalize_legacy_dimension_scores(
    *,
    scoring_rubric: Any,
    dimension_scores: list[AnnotationDimensionScore],
) -> list[dict[str, Any]]:
    dimension_by_id = {
        item.dimension_id: item
        for item in scoring_rubric.dimensions
    }
    normalized_dimensions = []
    for item in dimension_scores:
        rubric_dimension = dimension_by_id.get(item.dimension_id)
        weight = float(rubric_dimension.weight if rubric_dimension else item.weight)
        score = max(0.0, min(float(item.score), weight))
        normalized_dimensions.append(
            {
                "dimension_id": item.dimension_id,
                "name": item.name or (rubric_dimension.name if rubric_dimension else item.dimension_id),
                "weight": weight,
                "score": round(score, 2),
                "reason": item.reason,
            }
        )
    return normalized_dimensions


def _annotation_review_complete(
    target_checks: list[dict[str, Any]],
    dimension_checks: list[dict[str, Any]],
) -> bool:
    return all(item.get("status") != "unreviewed" for item in [*target_checks, *dimension_checks])


def _annotation_is_complete(annotation: Any) -> bool:
    if not isinstance(annotation, dict):
        return False
    return bool(annotation.get("review_complete", True))


def load_conversation_results_safe(path: Path) -> list[ConversationResult]:
    if not path.is_file():
        return []
    try:
        return load_conversation_results(path)
    except Exception:
        return []


def load_case_evaluations_safe(path: Path) -> list[CaseEvaluationResult]:
    if not path.is_file():
        return []
    items: list[CaseEvaluationResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(CaseEvaluationResult.model_validate_json(line))
        except Exception:
            continue
    return items


def load_llm_call_records_safe(path: Path) -> list[LLMCallRecord]:
    if not path.is_file():
        return []
    records: list[LLMCallRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(LLMCallRecord.model_validate_json(line))
        except Exception:
            continue
    return records


def _annotation_file(run_id: str) -> Path:
    safe_run_id = Path(run_id).name
    return _resolve_path(DEFAULT_ANNOTATIONS_ROOT) / safe_run_id / "gold_annotations.jsonl"


def _load_annotation_records(run_id: str) -> dict[str, dict[str, Any]]:
    path = _annotation_file(run_id)
    if not path.is_file():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = str(item.get("case_id") or "")
        if case_id:
            records[case_id] = item
    return records


def _write_annotation_records(run_id: str, records: dict[str, dict[str, Any]]) -> None:
    path = _annotation_file(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records.values(), key=lambda item: str(item.get("case_id") or ""))
    with path.open("w", encoding="utf-8") as file:
        for item in ordered:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_uploaded_file(filename: str, content: bytes) -> dict[str, str]:
    safe_name = _safe_filename(filename)
    upload_dir = _resolve_path(DEFAULT_UPLOAD_ROOT)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = _next_available_path(upload_dir / safe_name)
    destination.write_bytes(content)
    return {
        "filename": destination.name,
        "path": str(destination),
        "display_path": _display_path(destination),
    }


def _resolve_eval_standard_paths(
    request: GenerateAssetsRequest,
) -> tuple[list[Path], list[dict[str, Any]]]:
    provided_inputs = [
        bool(request.eval_standard_file_path),
        bool(request.eval_standard_path),
        bool(request.eval_standard_excel_path),
    ]
    if sum(provided_inputs) != 1:
        raise ValueError(
            "Provide exactly one of eval_standard_file_path, "
            "eval_standard_path, or eval_standard_excel_path."
        )

    if request.eval_standard_file_path:
        path = _resolve_path(request.eval_standard_file_path)
        _ensure_file(path)
        if is_tabular_path(path):
            return _extract_eval_standards_from_table(path, request)
        return _filter_single_eval_standard_path(path, request), []

    if request.eval_standard_path:
        path = _resolve_path(request.eval_standard_path)
        _ensure_file(path)
        return _filter_single_eval_standard_path(path, request), []

    return _extract_eval_standards_from_table(
        _resolve_path(request.eval_standard_excel_path or ""),
        request,
    )


def _extract_eval_standards_from_table(
    table_path: Path,
    request: GenerateAssetsRequest,
) -> tuple[list[Path], list[dict[str, Any]]]:
    if is_csv_path(table_path):
        extracted = extract_markdown_from_csv(
            table_path,
            _resolve_path(request.extracted_output_dir),
            column=request.excel_column,
            start_row=request.excel_start_row,
        )
        source_type = "csv"
    else:
        extracted = extract_markdown_from_excel(
            table_path,
            _resolve_path(request.extracted_output_dir),
            column=request.excel_column,
            start_row=request.excel_start_row,
            sheet_name=request.excel_sheet,
        )
        source_type = "excel"
    selected_paths = _selected_eval_standard_path_set(request)
    if selected_paths is not None:
        extracted = [
            item
            for item in extracted
            if str(_resolve_path(item.output_path)) in selected_paths
        ]
        if not extracted:
            raise ValueError("Selected eval standards were not found in the extracted table.")
    items = [
        {
            "source_excel_path": item.source_excel_path,
            "source_file_path": item.source_excel_path,
            "source_type": source_type,
            "source_sheet": item.source_sheet,
            "source_row": item.source_row,
            "source_column": item.source_column,
            "output_path": item.output_path,
            "title": item.title,
        }
        for item in extracted
    ]
    return [Path(item.output_path) for item in extracted], items


def _filter_single_eval_standard_path(
    path: Path,
    request: GenerateAssetsRequest,
) -> list[Path]:
    selected_paths = _selected_eval_standard_path_set(request)
    if selected_paths is None:
        return [path]
    if str(path) not in selected_paths:
        raise ValueError("Selected eval standards do not include the provided Markdown file.")
    return [path]


def _selected_eval_standard_path_set(request: GenerateAssetsRequest) -> set[str] | None:
    if request.selected_eval_standard_paths is None:
        return None
    selected_paths = {
        str(_resolve_path(item))
        for item in request.selected_eval_standard_paths
        if str(item or "").strip()
    }
    if not selected_paths:
        raise ValueError("Select at least one eval standard to run.")
    return selected_paths


def _record_dataset_for_generation(request: GenerateAssetsRequest) -> str:
    source_path = (
        request.eval_standard_file_path
        or request.eval_standard_path
        or request.eval_standard_excel_path
        or ""
    )
    resolved = _resolve_path(source_path)
    if is_csv_path(resolved):
        source_type = "csv"
    elif is_excel_path(resolved):
        source_type = "excel"
    else:
        source_type = "markdown"
    return record_dataset(
        source_path=resolved,
        source_type=source_type,
        metadata={
            "excel_column": request.excel_column,
            "excel_start_row": request.excel_start_row,
            "excel_sheet": request.excel_sheet or "",
        },
    )


def _record_task_instruction_for_path(
    *,
    dataset_id: str,
    eval_standard_path: Path,
    extracted_item: dict[str, Any] | None,
) -> str:
    extracted_item = extracted_item or {}
    return record_task_instruction(
        dataset_id=dataset_id,
        markdown_path=eval_standard_path,
        source_row=extracted_item.get("source_row"),
        source_column=extracted_item.get("source_column"),
        source_sheet=extracted_item.get("source_sheet") or "",
        title=extracted_item.get("title") or "",
        metadata=extracted_item,
    )


def _ensure_asset_version(asset_dir: Path, assets) -> str:
    existing = asset_version_for_dir(asset_dir)
    if existing:
        return existing
    input_hash = assets.scene_asset.generation_metadata.input_hash
    task_instruction_id = find_task_instruction_by_hash(input_hash)
    if not task_instruction_id and assets.scene_asset.source_eval_standard_path:
        source = Path(assets.scene_asset.source_eval_standard_path)
        if source.is_file():
            dataset_id = record_dataset(source_path=source, source_type="markdown")
            task_instruction_id = record_task_instruction(
                dataset_id=dataset_id,
                markdown_path=source,
            )
    return record_asset_version(
        asset_dir=asset_dir,
        assets=assets,
        task_instruction_id=task_instruction_id,
    )


def _resolve_asset_dir(*, scene_id: str | None, assets_path: str | None) -> Path:
    if bool(scene_id) == bool(assets_path):
        raise ValueError("Provide exactly one of scene_id or assets_path.")
    path = _resolve_path(assets_path) if assets_path else _resolve_path(DEFAULT_ASSETS_ROOT) / str(scene_id)
    if not path.is_dir():
        raise FileNotFoundError(f"Asset directory not found: {path}")
    return path


def _build_llm(*, fake_llm: bool, role: str, model_config_path: str):
    if fake_llm:
        client = FakeLLMClient()
        client.role = role
        client.call_records = []
        return client
    config = ModelConfig.model_validate(read_structured_file(_resolve_path(model_config_path)))
    return OpenAICompatibleClient.from_config(config, role)


def _load_business_config(path: str | None) -> BusinessConfig:
    if not path:
        return BusinessConfig()
    return BusinessConfig.model_validate(read_structured_file(_resolve_path(path)))


def _optional_path_str(path: str | None) -> str | None:
    return str(_resolve_path(path)) if path else None


def _resolve_path(path: str | Path) -> Path:
    item = Path(path).expanduser()
    if item.is_absolute():
        return item
    return PROJECT_ROOT / item


def _display_path(path: str | Path) -> str:
    item = _resolve_path(path)
    try:
        return str(item.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(item)


def _ensure_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")


def _read_existing_text(path: Path) -> str:
    _ensure_file(path)
    return path.read_text(encoding="utf-8")


def _read_text_or_empty(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _task_instruction_summary(path: Path, title: str = "") -> str:
    text = _read_text_or_empty(path)
    task_text = _task_text_from_markdown(text)
    source = task_text or title or _first_non_empty_line(text)
    semantic_title = _title_from_task_text(source)
    if semantic_title:
        return semantic_title[:10]
    return _compact_instruction_summary(source or title or text)


def _task_text_from_markdown(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        heading_lower = heading.lower()
        if not (heading_lower.startswith("task") or heading.startswith("任务")):
            continue
        inline_value = ""
        for delimiter in (":", "："):
            if delimiter in heading:
                inline_value = heading.split(delimiter, 1)[1].strip()
                break
        if inline_value:
            return inline_value
        collected: list[str] = []
        for next_line in lines[index + 1 :]:
            candidate = next_line.strip()
            if candidate.startswith("#") and collected:
                break
            if candidate:
                collected.append(candidate)
        if collected:
            return " ".join(collected)
    return ""


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate.lstrip("#").strip()
    return ""


def _compact_instruction_summary(value: str) -> str:
    text = _remove_markdown_marks(value)
    for phrase in (
        "角色",
        "任务",
        "你是",
        "请",
        "需要",
        "进行",
        "完成",
        "致电",
        "告知",
        "通知",
        "提醒",
        "他们",
        "客户",
        "用户",
        "商家",
        "老板",
        "骑手",
        "今天",
        "将",
    ):
        text = text.replace(phrase, "")
    chars = "".join(char for char in text if "\u4e00" <= char <= "\u9fff")
    return (chars or "任务指令")[:10]


def _remove_markdown_marks(value: str) -> str:
    remove_chars = set("#*_`[]()<>\"'“”‘’：:，。,.；;、!！?？-")
    return "".join(char for char in value.strip() if char not in remove_chars)


def _preview_text(path: Path, max_chars: int = 420) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _existing_files(path: Path, filenames: set[str]) -> list[str]:
    return sorted(filename for filename in filenames if (path / filename).is_file())


def _read_jsonl_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            items.append(value)
    return items


def _safe_filename(filename: str) -> str:
    source = Path(filename or "upload").name
    chars = []
    for char in source:
        if char.isalnum() or char in {".", "_", "-"}:
            chars.append(char)
        else:
            chars.append("_")
    safe = "".join(chars).strip("._")
    return safe or "upload"


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1
