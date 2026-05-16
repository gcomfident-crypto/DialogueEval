from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import coverage_judge_prompt, schema_text
from dialogue_simulator.schemas import (
    CaseCard,
    CoverageJudgeOutput,
    CoveragePlan,
    SceneAsset,
    TurnRecord,
)


def judge_coverage(
    llm: LLMClient,
    *,
    coverage_plan: CoveragePlan,
    scene_asset: SceneAsset,
    case_card: CaseCard,
    history: list[TurnRecord],
    current_triggered_targets: list[str],
    retry_count: int = 1,
) -> CoverageJudgeOutput:
    raw_output = complete_model(
        llm,
        task_name="coverage_judge",
        prompt=coverage_judge_prompt(
            coverage_plan=coverage_plan,
            scene_asset=scene_asset,
            case_card=case_card,
            history=[turn.model_dump(mode="json") for turn in history],
            current_triggered_targets=current_triggered_targets,
            output_schema=schema_text(CoverageJudgeOutput),
        ),
        model_type=CoverageJudgeOutput,
        retry_count=retry_count,
    )
    planned = set(case_card.coverage_targets)
    triggered = [
        item for item in raw_output.triggered_targets if item.label in planned
    ]
    triggered_labels = {item.label for item in triggered}
    missing = [
        target for target in case_card.coverage_targets if target not in triggered_labels
    ]
    return CoverageJudgeOutput(
        triggered_targets=triggered,
        missing_targets=missing,
        risk_flags=raw_output.risk_flags,
    )
