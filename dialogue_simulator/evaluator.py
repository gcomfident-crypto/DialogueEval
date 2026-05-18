from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import case_evaluation_prompt, schema_text
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseEvaluationDraft,
    CaseEvaluationResult,
    CheckItemEvaluation,
    ConversationResult,
    CoveragePlan,
    DimensionScore,
    EvidenceQuote,
    RiskDeduction,
    ScoringRubric,
    SceneAsset,
    VetoFinding,
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
    check_item_evaluations = _normalize_check_item_evaluations(
        scoring_rubric=scoring_rubric,
        conversation_result=conversation_result,
        draft_items=draft.check_item_evaluations,
    )
    if check_item_evaluations:
        normalized_scores = _dimension_scores_from_checks(
            scoring_rubric=scoring_rubric,
            check_item_evaluations=check_item_evaluations,
            legacy_dimension_scores=draft.dimension_scores,
            conversation_result=conversation_result,
        )
    else:
        normalized_scores = _normalize_legacy_dimension_scores(
            scoring_rubric=scoring_rubric,
            conversation_result=conversation_result,
            dimension_scores=draft.dimension_scores,
        )

    raw_score = sum(item.score for item in normalized_scores)
    risk_deductions = _normalize_risk_deductions(
        scoring_rubric=scoring_rubric,
        conversation_result=conversation_result,
        risk_deductions=draft.risk_deductions,
    )
    veto_items = _normalize_veto_items(
        conversation_result=conversation_result,
        veto_items=draft.veto_items,
    )
    risk_deduction_total = sum(item.deduction for item in risk_deductions)
    total_score = max(0.0, min(scoring_rubric.total_score, raw_score - risk_deduction_total))
    veto_triggered = bool(veto_items)
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
        veto_items=veto_items,
        check_item_evaluations=check_item_evaluations,
        dimension_scores=normalized_scores,
        risk_deductions=risk_deductions,
        coverage_success=conversation_result.coverage_success,
        missing_targets=conversation_result.missing_targets,
        final_comment=draft.final_comment,
    )


def _normalize_check_item_evaluations(
    *,
    scoring_rubric: ScoringRubric,
    conversation_result: ConversationResult,
    draft_items: list[CheckItemEvaluation],
) -> list[CheckItemEvaluation]:
    submitted = {}
    for item in draft_items:
        submitted.setdefault(item.check_id, item)

    normalized: list[CheckItemEvaluation] = []
    for dimension in scoring_rubric.dimensions:
        for check_item in dimension.check_items:
            draft_item = submitted.get(check_item.check_id)
            if draft_item is None:
                normalized.append(
                    CheckItemEvaluation(
                        check_id=check_item.check_id,
                        dimension_id=dimension.dimension_id,
                        name=check_item.name,
                        status="failed",
                        reason="评测模型未输出该原子评分项判定。",
                        missing_points=[check_item.pass_condition],
                    )
                )
                continue

            evidence = _validated_evidence(draft_item.evidence, conversation_result)
            status = draft_item.status
            missing_points = list(draft_item.missing_points)
            reason = draft_item.reason
            if status == "passed" and not evidence:
                status = "failed"
                reason = f"{reason}；证据引用未通过原文校验。"
                missing_points.append("缺少可回溯到原始对话的有效证据")
            normalized.append(
                draft_item.model_copy(
                    update={
                        "dimension_id": dimension.dimension_id,
                        "name": draft_item.name or check_item.name,
                        "status": status,
                        "evidence": evidence,
                        "missing_points": missing_points,
                    }
                )
            )
    return normalized


def _dimension_scores_from_checks(
    *,
    scoring_rubric: ScoringRubric,
    check_item_evaluations: list[CheckItemEvaluation],
    legacy_dimension_scores: list[DimensionScore],
    conversation_result: ConversationResult,
) -> list[DimensionScore]:
    checks_by_id = {item.check_id: item for item in check_item_evaluations}
    legacy_by_dimension = {
        item.dimension_id: item
        for item in _normalize_legacy_dimension_scores(
            scoring_rubric=scoring_rubric,
            conversation_result=conversation_result,
            dimension_scores=legacy_dimension_scores,
        )
    }

    dimension_scores: list[DimensionScore] = []
    for dimension in scoring_rubric.dimensions:
        if not dimension.check_items:
            legacy_score = legacy_by_dimension.get(dimension.dimension_id)
            if legacy_score is not None:
                dimension_scores.append(legacy_score)
            else:
                dimension_scores.append(
                    DimensionScore(
                        dimension_id=dimension.dimension_id,
                        name=dimension.name,
                        weight=dimension.weight,
                        score=0.0,
                        reason="评分量表未提供原子评分项，评测模型也未提供该维度分。",
                        missing_points=["缺少维度评分依据"],
                    )
                )
            continue

        applicable_points = 0.0
        passed_points = 0.0
        passed_count = 0
        failed_points: list[str] = []
        evidence: list[EvidenceQuote] = []
        not_applicable_count = 0
        for check_item in dimension.check_items:
            check = checks_by_id.get(check_item.check_id)
            if check is None:
                failed_points.append(check_item.name)
                applicable_points += check_item.points
                continue
            if check.status == "not_applicable":
                not_applicable_count += 1
                continue
            applicable_points += check_item.points
            evidence.extend(check.evidence)
            if check.status == "passed":
                passed_count += 1
                passed_points += check_item.points
            else:
                failed_points.append(check.name or check_item.name)

        if applicable_points <= 0:
            score = float(dimension.weight)
            reason = f"该维度 {not_applicable_count} 个原子评分项均不适用。"
        else:
            score = float(dimension.weight) * passed_points / applicable_points
            total_applicable = len(dimension.check_items) - not_applicable_count
            reason = (
                f"原子评分项通过 {passed_count}/{total_applicable}，"
                f"不适用 {not_applicable_count}。"
            )
            if failed_points:
                reason += " 未通过：" + "；".join(failed_points)

        dimension_scores.append(
            DimensionScore(
                dimension_id=dimension.dimension_id,
                name=dimension.name,
                weight=dimension.weight,
                score=round(max(0.0, min(float(dimension.weight), score)), 2),
                reason=reason,
                evidence=evidence,
                missing_points=failed_points,
            )
        )
    return dimension_scores


def _normalize_legacy_dimension_scores(
    *,
    scoring_rubric: ScoringRubric,
    conversation_result: ConversationResult,
    dimension_scores: list[DimensionScore],
) -> list[DimensionScore]:
    dimension_weights = {
        dimension.dimension_id: dimension.weight
        for dimension in scoring_rubric.dimensions
    }
    normalized_scores = []
    for item in dimension_scores:
        weight = dimension_weights.get(item.dimension_id, item.weight)
        score = max(0.0, min(float(item.score), float(weight)))
        normalized_scores.append(
            item.model_copy(
                update={
                    "weight": weight,
                    "score": score,
                    "evidence": _validated_evidence(item.evidence, conversation_result),
                }
            )
        )
    return normalized_scores


def _normalize_risk_deductions(
    *,
    scoring_rubric: ScoringRubric,
    conversation_result: ConversationResult,
    risk_deductions: list[RiskDeduction],
) -> list[RiskDeduction]:
    default_deductions = {
        item.rule_id: item.default_deduction
        for item in scoring_rubric.risk_rules
    }
    normalized: list[RiskDeduction] = []
    seen: set[str] = set()
    for item in risk_deductions:
        if not item.rule_id or item.rule_id in seen:
            continue
        evidence = _validated_evidence(item.evidence, conversation_result)
        deduction = float(item.deduction)
        default_deduction = float(default_deductions.get(item.rule_id, 0.0))
        if default_deduction > 0:
            deduction = default_deduction if deduction <= 0 else min(deduction, default_deduction)
        if deduction > 0 and not evidence:
            continue
        normalized.append(
            item.model_copy(
                update={
                    "deduction": round(max(0.0, deduction), 2),
                    "evidence": evidence,
                }
            )
        )
        seen.add(item.rule_id)
    return normalized


def _normalize_veto_items(
    *,
    conversation_result: ConversationResult,
    veto_items: list[VetoFinding],
) -> list[VetoFinding]:
    normalized: list[VetoFinding] = []
    seen: set[str] = set()
    for item in veto_items:
        if not item.rule_id or item.rule_id in seen:
            continue
        evidence = _validated_evidence(item.evidence, conversation_result)
        if not evidence:
            continue
        normalized.append(item.model_copy(update={"evidence": evidence}))
        seen.add(item.rule_id)
    return normalized


def _validated_evidence(
    evidence_items: list[EvidenceQuote],
    conversation_result: ConversationResult,
) -> list[EvidenceQuote]:
    valid_items: list[EvidenceQuote] = []
    for item in evidence_items:
        if item.turn_index >= len(conversation_result.turns):
            continue
        turn = conversation_result.turns[item.turn_index]
        quote = item.quote.strip()
        if not quote:
            continue
        if item.speaker != "both" and item.speaker != turn.role:
            continue
        if quote not in turn.text:
            continue
        valid_items.append(item.model_copy(update={"quote": quote}))
    return valid_items
