from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import case_evaluation_prompt, schema_text
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseEvaluationDraft,
    CaseEvaluationResult,
    ConversationResult,
    CoveragePlan,
    ScoringRubric,
    SceneAsset,
)


def evaluate_case(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    scoring_rubric: ScoringRubric,
    conversation_result: ConversationResult,
    business_config: BusinessConfig,
    retry_count: int = 1,
) -> CaseEvaluationDraft:
    return complete_model(
        llm,
        task_name="case_evaluation",
        prompt=case_evaluation_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            scoring_rubric=scoring_rubric,
            conversation_result=conversation_result,
            business_config=business_config,
            output_schema=schema_text(CaseEvaluationDraft),
        ),
        model_type=CaseEvaluationDraft,
        retry_count=retry_count,
    )


def aggregate_case_evaluation(
    *,
    scoring_rubric: ScoringRubric,
    conversation_result: ConversationResult,
    draft: CaseEvaluationDraft,
) -> CaseEvaluationResult:
    dimension_weights = {
        dimension.dimension_id: dimension.weight
        for dimension in scoring_rubric.dimensions
    }
    normalized_scores = []
    for item in draft.dimension_scores:
        weight = dimension_weights.get(item.dimension_id, item.weight)
        score = max(0.0, min(float(item.score), float(weight)))
        normalized_scores.append(item.model_copy(update={"weight": weight, "score": score}))

    raw_score = sum(item.score for item in normalized_scores)
    risk_deduction_total = sum(item.deduction for item in draft.risk_deductions)
    total_score = max(0.0, min(scoring_rubric.total_score, raw_score - risk_deduction_total))
    veto_triggered = bool(draft.veto_items)
    passed = total_score >= scoring_rubric.pass_threshold and not veto_triggered

    return CaseEvaluationResult(
        run_id=conversation_result.run_id,
        case_id=conversation_result.case_id,
        scene_id=conversation_result.scene_id,
        priority=conversation_result.priority,
        raw_score=round(raw_score, 2),
        risk_deduction_total=round(risk_deduction_total, 2),
        total_score=round(total_score, 2),
        pass_threshold=scoring_rubric.pass_threshold,
        passed=passed,
        veto_triggered=veto_triggered,
        veto_items=draft.veto_items,
        dimension_scores=normalized_scores,
        risk_deductions=draft.risk_deductions,
        coverage_success=conversation_result.coverage_success,
        missing_targets=conversation_result.missing_targets,
        final_comment=draft.final_comment,
    )
