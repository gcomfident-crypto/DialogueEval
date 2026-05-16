from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from dialogue_simulator.cli import (
    evaluate_results,
    get_call_records,
    load_conversation_results,
    make_run_id,
)
from dialogue_simulator.eval_standard_loader import (
    extract_markdown_from_excel,
    is_excel_path,
)
from dialogue_simulator.graph import (
    build_asset_generation_graph,
    build_conversation_graph,
    load_generated_assets,
)
from dialogue_simulator.llm_client import FakeLLMClient, OpenAICompatibleClient
from dialogue_simulator.report_exporter import (
    export_evaluation_reports,
    export_llm_call_records,
    export_run_reports,
)
from dialogue_simulator.schemas import BusinessConfig, ConversationResult, ModelConfig
from dialogue_simulator.storage import read_structured_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_CONFIG = "configs/model_config.yaml"
DEFAULT_GENERATION_POLICY = "configs/generation_policy.yaml"
DEFAULT_ASSETS_ROOT = "outputs/assets"
DEFAULT_RUNS_ROOT = "outputs/runs"
DEFAULT_EXTRACTED_ROOT = "outputs/extracted_eval_standards"
DEFAULT_UPLOAD_ROOT = "outputs/uploads"

ASSET_FILES = {
    "scene_asset.yaml",
    "coverage_plan.yaml",
    "user_profiles.yaml",
    "case_cards.yaml",
    "scoring_rubric.yaml",
    "materialized_eval_standard.md",
    "variable_assignments.yaml",
    "asset_generation_report.md",
    "llm_calls.jsonl",
}
RUN_REPORT_FILES = {
    "summary_report.md",
    "coverage_report.csv",
    "conversation_log.jsonl",
    "evaluation_report.md",
    "evaluation_report.csv",
    "case_evaluation.jsonl",
    "llm_calls.jsonl",
}


class GenerateAssetsRequest(BaseModel):
    eval_standard_file_path: Optional[str] = None
    eval_standard_path: Optional[str] = None
    eval_standard_excel_path: Optional[str] = None
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


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "assets_root": str(_resolve_path(DEFAULT_ASSETS_ROOT)),
        "runs_root": str(_resolve_path(DEFAULT_RUNS_ROOT)),
    }


def extract_eval_standards(request: ExtractEvalStandardsRequest) -> dict[str, Any]:
    items = extract_markdown_from_excel(
        _resolve_path(request.excel_path),
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
            }
            for item in items
        ],
    }


def generate_assets(request: GenerateAssetsRequest) -> dict[str, Any]:
    eval_standard_paths, extracted_items = _resolve_eval_standard_paths(request)
    asset_summaries: list[dict[str, Any]] = []
    output_root = _resolve_path(request.output_root)

    for eval_standard_path in eval_standard_paths:
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
            }
        )
        asset_dir = Path(result["asset_dir"])
        export_llm_call_records(get_call_records([llm]), asset_dir)
        asset_summaries.append(summarize_asset_dir(asset_dir))

    return {
        "count": len(asset_summaries),
        "assets": asset_summaries,
        "extracted_eval_standards": extracted_items,
    }


def run_evaluation(request: RunEvaluationRequest) -> dict[str, Any]:
    asset_dir = _resolve_asset_dir(scene_id=request.scene_id, assets_path=request.assets_path)
    assets = load_generated_assets(asset_dir)
    business_config = _load_business_config(request.business_config_path)

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
    )

    results: list[ConversationResult] = []
    for case_card in case_cards:
        result = graph.invoke(
            {
                "run_id": run_id,
                "scene_asset": assets.scene_asset,
                "coverage_plan": assets.coverage_plan,
                "user_profiles": assets.user_profiles,
                "case_card": case_card,
                "business_config": business_config,
            },
            {"recursion_limit": case_card.stop_policy.max_turns * 6 + 10},
        )
        results.append(result["conversation_result"])
        export_run_reports(results, output_dir)

    export_run_reports(results, output_dir)
    evaluation_count = 0
    if evaluator_llm is not None:
        evaluations = evaluate_results(
            evaluator_llm=evaluator_llm,
            assets=assets,
            results=results,
            business_config=business_config,
        )
        evaluation_count = len(evaluations)
        export_evaluation_reports(evaluations, output_dir, conversations=results)

    export_llm_call_records(
        get_call_records([agent_llm, user_llm, judge_llm, evaluator_llm]),
        output_dir,
    )
    summary = summarize_run_dir(output_dir)
    summary.update(
        {
            "asset_dir": str(asset_dir),
            "cases_run": len(results),
            "cases_evaluated": evaluation_count,
        }
    )
    return summary


def evaluate_existing_run(request: EvaluateRunRequest) -> dict[str, Any]:
    if not request.run_dir:
        raise ValueError("run_dir is required.")

    asset_dir = _resolve_asset_dir(scene_id=request.scene_id, assets_path=request.assets_path)
    run_dir = _resolve_path(request.run_dir)
    assets = load_generated_assets(asset_dir)
    results = load_conversation_results(run_dir / "conversation_log.jsonl")
    business_config = _load_business_config(request.business_config_path)
    evaluator_llm = _build_llm(
        fake_llm=request.fake_llm,
        role="evaluator",
        model_config_path=request.model_config_path,
    )
    evaluations = evaluate_results(
        evaluator_llm=evaluator_llm,
        assets=assets,
        results=results,
        business_config=business_config,
    )
    export_evaluation_reports(evaluations, run_dir, conversations=results)
    export_llm_call_records(get_call_records([evaluator_llm]), run_dir)
    summary = summarize_run_dir(run_dir)
    summary.update({"asset_dir": str(asset_dir), "cases_evaluated": len(evaluations)})
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
    successful_cases = sum(1 for item in conversations if item.get("coverage_success"))
    passed_cases = sum(1 for item in evaluations if item.get("passed"))
    risk_count = sum(len(item.get("risk_deductions") or []) for item in evaluations)
    veto_count = sum(1 for item in evaluations if item.get("veto_triggered"))
    scores = [
        float(item["total_score"])
        for item in evaluations
        if isinstance(item.get("total_score"), (int, float))
    ]
    return {
        "run_id": path.name,
        "run_dir": str(path),
        "display_path": _display_path(path),
        "case_count": len(conversations),
        "coverage_success_count": successful_cases,
        "evaluation_count": len(evaluations),
        "passed_count": passed_cases,
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "veto_count": veto_count,
        "risk_count": risk_count,
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


def read_case_report(run_id: str, case_id: str) -> str:
    safe_case_id = Path(case_id).name
    path = _resolve_path(DEFAULT_RUNS_ROOT) / run_id / "case_reports" / f"{safe_case_id}.md"
    return _read_existing_text(path)


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
        if is_excel_path(path):
            return _extract_eval_standards_from_excel(path, request)
        return [path], []

    if request.eval_standard_path:
        path = _resolve_path(request.eval_standard_path)
        _ensure_file(path)
        return [path], []

    return _extract_eval_standards_from_excel(
        _resolve_path(request.eval_standard_excel_path or ""),
        request,
    )


def _extract_eval_standards_from_excel(
    excel_path: Path,
    request: GenerateAssetsRequest,
) -> tuple[list[Path], list[dict[str, Any]]]:
    extracted = extract_markdown_from_excel(
        excel_path,
        _resolve_path(request.extracted_output_dir),
        column=request.excel_column,
        start_row=request.excel_start_row,
        sheet_name=request.excel_sheet,
    )
    items = [
        {
            "source_excel_path": item.source_excel_path,
            "source_sheet": item.source_sheet,
            "source_row": item.source_row,
            "source_column": item.source_column,
            "output_path": item.output_path,
            "title": item.title,
        }
        for item in extracted
    ]
    return [Path(item.output_path) for item in extracted], items


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
