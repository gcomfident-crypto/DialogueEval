from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import (
    case_card_batch_prompt,
    case_generation_plan_prompt,
    case_cards_prompt,
    coverage_matrix_prompt,
    coverage_plan_prompt,
    coverage_taxonomy_prompt,
    materialize_eval_standard_prompt,
    scene_asset_prompt,
    schema_text,
    scoring_rubric_prompt,
    system_json_only_prompt,
    user_profiles_prompt,
)
from dialogue_simulator.rubric_validator import assert_valid_scoring_rubric
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseCard,
    CaseCardCollection,
    CasePlanAllocation,
    CaseGenerationPlan,
    CoverageMatrix,
    CoveragePlan,
    CoverageTaxonomy,
    GenerationMetadata,
    GenerationPolicy,
    MaterializedEvalStandard,
    SceneAsset,
    RiskScoringRule,
    ScoringCheckItem,
    ScoringDimension,
    ScoringRubric,
    UserProfileCollection,
    VetoRule,
    utc_now_iso,
)
from dialogue_simulator.structured_output import StructuredOutputError, parse_model


CASE_CARD_BATCH_SIZE = 8


def complete_model(
    llm: LLMClient,
    *,
    task_name: str,
    prompt: str,
    model_type: type,
    retry_count: int = 1,
):
    messages = [
        {"role": "system", "content": system_json_only_prompt()},
        {"role": "user", "content": prompt},
    ]
    last_error = ""
    for attempt in range(retry_count + 1):
        prompt_messages = messages
        if attempt > 0:
            prompt_messages = messages + [
                {
                    "role": "user",
                    "content": f"上一次输出无法通过结构化校验：{last_error}。请只返回合法 JSON。",
                }
            ]
        raw = llm.complete(prompt_messages, task_name=task_name)
        try:
            return parse_model(raw, model_type)
        except StructuredOutputError as exc:
            last_error = str(exc)
    raise StructuredOutputError(f"{task_name}: {last_error}")


def generate_scene_asset(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    eval_standard_path: str,
    business_config: BusinessConfig,
    input_hash: str,
    retry_count: int,
) -> SceneAsset:
    scene_asset = complete_model(
        llm,
        task_name="scene_asset",
        prompt=scene_asset_prompt(
            eval_standard_text=eval_standard_text,
            business_config=business_config,
            input_hash=input_hash,
            output_schema=schema_text(SceneAsset),
        ),
        model_type=SceneAsset,
        retry_count=retry_count,
    )
    metadata = scene_asset.generation_metadata.model_copy(
        update={
            "model": llm.model_name,
            "created_at": utc_now_iso(),
            "input_hash": input_hash,
            "source_eval_standard_path": eval_standard_path,
        }
    )
    return scene_asset.model_copy(
        update={
            "source_eval_standard_path": eval_standard_path,
            "generation_metadata": metadata,
        }
    )


def materialize_eval_standard(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    business_config: BusinessConfig,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> MaterializedEvalStandard:
    materialized = complete_model(
        llm,
        task_name="eval_standard_materialization",
        prompt=materialize_eval_standard_prompt(
            eval_standard_text=eval_standard_text,
            business_config=business_config,
            generation_policy=generation_policy,
            output_schema=schema_text(MaterializedEvalStandard),
        ),
        model_type=MaterializedEvalStandard,
        retry_count=retry_count,
    )
    if not materialized.materialized_text.strip():
        raise ValueError("materialized eval standard cannot be empty")
    return materialized


def generate_coverage_plan(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> CoveragePlan:
    coverage_plan = complete_model(
        llm,
        task_name="coverage_plan",
        prompt=coverage_plan_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            generation_policy=generation_policy,
            output_schema=schema_text(CoveragePlan),
        ),
        model_type=CoveragePlan,
        retry_count=retry_count,
    )
    if len(coverage_plan.coverage_labels) < generation_policy.validation.min_coverage_label_count:
        raise ValueError(
            "coverage label count is lower than "
            f"{generation_policy.validation.min_coverage_label_count}"
        )
    return coverage_plan.model_copy(update={"scene_id": scene_asset.scene_id})


def generate_user_profiles(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> UserProfileCollection:
    profiles = complete_model(
        llm,
        task_name="user_profiles",
        prompt=user_profiles_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            generation_policy=generation_policy,
            output_schema=schema_text(UserProfileCollection),
        ),
        model_type=UserProfileCollection,
        retry_count=retry_count,
    )
    return profiles.model_copy(update={"scene_id": scene_asset.scene_id})


def generate_coverage_taxonomy(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    scoring_rubric: ScoringRubric,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> CoverageTaxonomy:
    taxonomy = complete_model(
        llm,
        task_name="coverage_taxonomy",
        prompt=coverage_taxonomy_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            scoring_rubric=scoring_rubric,
            generation_policy=generation_policy,
            output_schema=schema_text(CoverageTaxonomy),
        ),
        model_type=CoverageTaxonomy,
        retry_count=retry_count,
    )
    return taxonomy.model_copy(update={"scene_id": scene_asset.scene_id})


def generate_coverage_matrix(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy,
    scoring_rubric: ScoringRubric,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> CoverageMatrix:
    matrix = complete_model(
        llm,
        task_name="coverage_matrix",
        prompt=coverage_matrix_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            coverage_taxonomy=coverage_taxonomy,
            scoring_rubric=scoring_rubric,
            generation_policy=generation_policy,
            output_schema=schema_text(CoverageMatrix),
        ),
        model_type=CoverageMatrix,
        retry_count=retry_count,
    )
    matrix = _repair_matrix_task_targets(matrix, coverage_plan)
    matrix = _ensure_matrix_label_coverage(matrix, coverage_plan)
    _validate_matrix_references(matrix, coverage_plan, coverage_taxonomy)
    return matrix.model_copy(update={"scene_id": scene_asset.scene_id})


def generate_case_generation_plan(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy,
    coverage_matrix: CoverageMatrix,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> CaseGenerationPlan:
    plan = complete_model(
        llm,
        task_name="case_generation_plan",
        prompt=case_generation_plan_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            coverage_taxonomy=coverage_taxonomy,
            coverage_matrix=coverage_matrix,
            generation_policy=generation_policy,
            output_schema=schema_text(CaseGenerationPlan),
        ),
        model_type=CaseGenerationPlan,
        retry_count=retry_count,
    )
    matrix_ids = {row.matrix_id for row in coverage_matrix.rows}
    invalid = [item.matrix_id for item in plan.allocations if item.matrix_id not in matrix_ids]
    if invalid:
        raise ValueError(f"case generation plan references unknown matrix_id: {', '.join(invalid)}")
    target_total = generation_policy.case_generation.target_cases
    plan = _normalize_case_generation_plan(
        plan,
        coverage_matrix=coverage_matrix,
        target_total=target_total,
    )
    planned_total = sum(item.case_count for item in plan.allocations)
    if planned_total > generation_policy.case_generation.max_cases:
        raise ValueError(
            f"case generation plan count {planned_total} exceeds max_cases "
            f"{generation_policy.case_generation.max_cases}"
        )
    return plan.model_copy(update={"scene_id": scene_asset.scene_id})


def _normalize_case_generation_plan(
    plan: CaseGenerationPlan,
    *,
    coverage_matrix: CoverageMatrix,
    target_total: int,
) -> CaseGenerationPlan:
    rows = coverage_matrix.rows
    if target_total < 1:
        target_total = 1

    original_total = sum(item.case_count for item in plan.allocations)
    original_target = plan.target_case_count
    raw_counts: dict[str, int] = {}
    raw_rationales: dict[str, str] = {}
    for allocation in plan.allocations:
        raw_counts[allocation.matrix_id] = raw_counts.get(allocation.matrix_id, 0) + allocation.case_count
        if allocation.rationale:
            raw_rationales.setdefault(allocation.matrix_id, allocation.rationale)

    ordered_rows = sorted(
        rows,
        key=lambda row: (0 if row.priority == "P0" else 1, row.matrix_id),
    )
    active_rows = ordered_rows[:target_total] if len(ordered_rows) > target_total else ordered_rows
    counts = {
        row.matrix_id: max(1, raw_counts.get(row.matrix_id, row.case_count))
        for row in active_rows
    }

    total = sum(counts.values())
    while total > target_total:
        adjustable = [
            row for row in reversed(active_rows) if counts.get(row.matrix_id, 0) > 1
        ]
        if not adjustable:
            break
        for row in adjustable:
            if total <= target_total:
                break
            counts[row.matrix_id] -= 1
            total -= 1

    while total < target_total and active_rows:
        for row in active_rows:
            if total >= target_total:
                break
            counts[row.matrix_id] += 1
            total += 1

    allocations = [
        CasePlanAllocation(
            matrix_id=row.matrix_id,
            case_count=counts[row.matrix_id],
            rationale=raw_rationales.get(row.matrix_id, row.rationale),
        )
        for row in coverage_matrix.rows
        if row.matrix_id in counts
    ]
    notes = list(plan.validation_notes)
    if original_target != target_total or original_total != target_total:
        notes.append(
            f"程序已将模型生成的 case 分配从 target={original_target}, total={original_total} "
            f"归一化为 target={target_total}, total={sum(item.case_count for item in allocations)}。"
        )
    return plan.model_copy(
        update={
            "target_case_count": target_total,
            "allocations": allocations,
            "validation_notes": notes,
        }
    )


def generate_case_cards(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    user_profiles: UserProfileCollection,
    generation_policy: GenerationPolicy,
    retry_count: int,
    coverage_taxonomy: CoverageTaxonomy | None = None,
    coverage_matrix: CoverageMatrix | None = None,
    case_generation_plan: CaseGenerationPlan | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> CaseCardCollection:
    if coverage_taxonomy and coverage_matrix and case_generation_plan:
        case_cards = _generate_case_cards_from_matrix(
            llm,
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            coverage_taxonomy=coverage_taxonomy,
            coverage_matrix=coverage_matrix,
            case_generation_plan=case_generation_plan,
            user_profiles=user_profiles,
            generation_policy=generation_policy,
            retry_count=retry_count,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        return _repair_and_validate_case_cards(
            case_cards,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            user_profiles=user_profiles,
            generation_policy=generation_policy,
            coverage_taxonomy=coverage_taxonomy,
            coverage_matrix=coverage_matrix,
        )

    if cancel_check:
        cancel_check()
    if progress_callback:
        progress_callback(
            {
                "phase": "case_cards",
                "status": "batch_start",
                "generated_count": 0,
                "target_case_count": generation_policy.case_generation.target_cases,
                "case_range_start": 1,
                "case_range_end": generation_policy.case_generation.target_cases,
            }
        )
    case_cards = complete_model(
        llm,
        task_name="case_cards",
        prompt=case_cards_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            user_profiles=user_profiles,
            generation_policy=generation_policy,
            output_schema=schema_text(CaseCardCollection),
        ),
        model_type=CaseCardCollection,
        retry_count=retry_count,
    )
    if cancel_check:
        cancel_check()
    if progress_callback:
        progress_callback(
            {
                "phase": "case_cards",
                "status": "batch_complete",
                "generated_count": len(case_cards.cases),
                "target_case_count": generation_policy.case_generation.target_cases,
                "case_range_start": 1,
                "case_range_end": len(case_cards.cases),
            }
        )
    return _repair_and_validate_case_cards(
        case_cards,
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
        user_profiles=user_profiles,
        generation_policy=generation_policy,
        coverage_taxonomy=coverage_taxonomy,
        coverage_matrix=coverage_matrix,
    )


def _generate_case_cards_from_matrix(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy,
    coverage_matrix: CoverageMatrix,
    case_generation_plan: CaseGenerationPlan,
    user_profiles: UserProfileCollection,
    generation_policy: GenerationPolicy,
    retry_count: int,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> CaseCardCollection:
    rows = {row.matrix_id: row for row in coverage_matrix.rows}
    labels = {item.label for item in coverage_plan.coverage_labels}
    cases = []
    generated_count = 0
    target_case_count = sum(item.case_count for item in case_generation_plan.allocations)
    for allocation in case_generation_plan.allocations:
        row = rows[allocation.matrix_id]
        remaining = allocation.case_count
        while remaining > 0:
            if cancel_check:
                cancel_check()
            batch_size = min(CASE_CARD_BATCH_SIZE, remaining)
            case_range_start = generated_count + 1
            case_range_end = generated_count + batch_size
            if progress_callback:
                progress_callback(
                    {
                        "phase": "case_cards",
                        "status": "batch_start",
                        "matrix_id": row.matrix_id,
                        "generated_count": generated_count,
                        "target_case_count": target_case_count,
                        "case_range_start": case_range_start,
                        "case_range_end": case_range_end,
                        "batch_size": batch_size,
                    }
                )
            batch = complete_model(
                llm,
                task_name="case_card_batch",
                prompt=case_card_batch_prompt(
                    eval_standard_text=eval_standard_text,
                    scene_asset=scene_asset,
                    coverage_plan=coverage_plan,
                    coverage_taxonomy=coverage_taxonomy,
                    coverage_matrix_row=row,
                    case_count=batch_size,
                    user_profiles=user_profiles,
                    generation_policy=generation_policy,
                    output_schema=schema_text(CaseCardCollection),
                ),
                model_type=CaseCardCollection,
                retry_count=retry_count,
            )
            if cancel_check:
                cancel_check()
            if len(batch.cases) < batch_size:
                raise ValueError(
                    f"{row.matrix_id} generated {len(batch.cases)} cases; "
                    f"expected at least {batch_size}"
                )
            for case_card in batch.cases[:batch_size]:
                generated_count += 1
                coverage_targets = _ordered_unique(
                    [
                        target
                        for target in [*row.task_targets, *case_card.coverage_targets]
                        if target in labels
                    ]
                )
                cases.append(
                    case_card.model_copy(
                        update={
                            "case_id": f"case_{generated_count:03d}",
                            "scene_id": scene_asset.scene_id,
                            "coverage_targets": coverage_targets,
                            "matrix_id": row.matrix_id,
                            "flow_branch_tags": row.flow_branches,
                            "user_behavior_tags": row.user_behaviors,
                            "risk_probe_tags": row.risk_probes,
                            "dynamic_state_path_tags": row.dynamic_state_paths,
                        }
                    )
                )
            remaining -= batch_size
            if progress_callback:
                progress_callback(
                    {
                        "phase": "case_cards",
                        "status": "batch_complete",
                        "matrix_id": row.matrix_id,
                        "generated_count": generated_count,
                        "target_case_count": target_case_count,
                        "case_range_start": case_range_start,
                        "case_range_end": case_range_end,
                        "batch_size": batch_size,
                    }
                )
    return CaseCardCollection(scene_id=scene_asset.scene_id, cases=cases)


def _repair_and_validate_case_cards(
    case_cards: CaseCardCollection,
    *,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    user_profiles: UserProfileCollection,
    generation_policy: GenerationPolicy,
    coverage_taxonomy: CoverageTaxonomy | None = None,
    coverage_matrix: CoverageMatrix | None = None,
) -> CaseCardCollection:
    labels = {item.label for item in coverage_plan.coverage_labels}
    profile_ids = {item.profile_id for item in user_profiles.profiles}
    matrix_targets_by_id = {
        row.matrix_id: [target for target in row.task_targets if target in labels]
        for row in coverage_matrix.rows
    } if coverage_matrix else {}
    taxonomy_ids = _taxonomy_id_sets(coverage_taxonomy)
    fallback_targets = _fallback_coverage_targets(coverage_plan, generation_policy)
    if len(case_cards.cases) < generation_policy.case_generation.min_cases:
        raise ValueError(
            f"case card count is lower than {generation_policy.case_generation.min_cases}"
        )
    if len(case_cards.cases) > generation_policy.case_generation.max_cases:
        raise ValueError(
            f"case card count is greater than {generation_policy.case_generation.max_cases}"
        )
    repaired_cases = []
    for case_card in case_cards.cases:
        normalized = _normalize_case_card_references(
            case_card,
            labels=labels,
            taxonomy_ids=taxonomy_ids,
            matrix_targets=matrix_targets_by_id.get(case_card.matrix_id, []),
            fallback_targets=fallback_targets,
        )
        if case_card.profile_id not in profile_ids:
            raise ValueError(
                f"{case_card.case_id} references unknown profile_id {case_card.profile_id}"
            )
        repaired_cases.append(normalized.model_copy(update={"scene_id": scene_asset.scene_id}))
    return case_cards.model_copy(
        update={"scene_id": scene_asset.scene_id, "cases": repaired_cases}
    )


def _normalize_case_card_references(
    case_card: CaseCard,
    *,
    labels: set[str],
    taxonomy_ids: dict[str, set[str]],
    matrix_targets: list[str],
    fallback_targets: list[str],
) -> CaseCard:
    coverage_targets = _ordered_unique(
        target for target in case_card.coverage_targets if target in labels
    )
    if not coverage_targets:
        coverage_targets = _ordered_unique(matrix_targets or fallback_targets)

    misplaced_targets = [
        target for target in case_card.coverage_targets if target not in labels
    ]
    flow_branch_tags = _merge_known_references(
        case_card.flow_branch_tags,
        misplaced_targets,
        taxonomy_ids["flow_branch_tags"],
    )
    user_behavior_tags = _merge_known_references(
        case_card.user_behavior_tags,
        misplaced_targets,
        taxonomy_ids["user_behavior_tags"],
    )
    risk_probe_tags = _merge_known_references(
        case_card.risk_probe_tags,
        misplaced_targets,
        taxonomy_ids["risk_probe_tags"],
    )
    dynamic_state_path_tags = _merge_known_references(
        case_card.dynamic_state_path_tags,
        misplaced_targets,
        taxonomy_ids["dynamic_state_path_tags"],
    )
    return case_card.model_copy(
        update={
            "coverage_targets": coverage_targets,
            "flow_branch_tags": flow_branch_tags,
            "user_behavior_tags": user_behavior_tags,
            "risk_probe_tags": risk_probe_tags,
            "dynamic_state_path_tags": dynamic_state_path_tags,
        }
    )


def _fallback_coverage_targets(
    coverage_plan: CoveragePlan,
    generation_policy: GenerationPolicy,
) -> list[str]:
    max_targets = generation_policy.case_generation.coverage_per_case_max
    p0_labels = [item.label for item in coverage_plan.coverage_labels if item.priority == "P0"]
    candidates = p0_labels or [item.label for item in coverage_plan.coverage_labels]
    return candidates[:max_targets]


def _taxonomy_id_sets(coverage_taxonomy: CoverageTaxonomy | None) -> dict[str, set[str]]:
    if not coverage_taxonomy:
        return {
            "flow_branch_tags": set(),
            "user_behavior_tags": set(),
            "risk_probe_tags": set(),
            "dynamic_state_path_tags": set(),
        }
    return {
        "flow_branch_tags": {item.item_id for item in coverage_taxonomy.flow_branches},
        "user_behavior_tags": {item.item_id for item in coverage_taxonomy.user_behaviors},
        "risk_probe_tags": {item.item_id for item in coverage_taxonomy.risk_probes},
        "dynamic_state_path_tags": {item.item_id for item in coverage_taxonomy.dynamic_state_paths},
    }


def _merge_known_references(
    existing_values,
    misplaced_values,
    known_ids: set[str],
) -> list[str]:
    if not known_ids:
        return _ordered_unique(existing_values)
    return _ordered_unique(
        value for value in [*existing_values, *misplaced_values] if value in known_ids
    )


def _ordered_unique(values) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _validate_matrix_references(
    matrix: CoverageMatrix,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy,
) -> None:
    labels = {item.label for item in coverage_plan.coverage_labels}
    flow = {item.item_id for item in coverage_taxonomy.flow_branches}
    behaviors = {item.item_id for item in coverage_taxonomy.user_behaviors}
    risks = {item.item_id for item in coverage_taxonomy.risk_probes}
    paths = {item.item_id for item in coverage_taxonomy.dynamic_state_paths}
    for row in matrix.rows:
        invalid_targets = [item for item in row.task_targets if item not in labels]
        invalid_flow = [item for item in row.flow_branches if item not in flow]
        invalid_behaviors = [item for item in row.user_behaviors if item not in behaviors]
        invalid_risks = [item for item in row.risk_probes if item not in risks]
        invalid_paths = [item for item in row.dynamic_state_paths if item not in paths]
        invalid = invalid_targets + invalid_flow + invalid_behaviors + invalid_risks + invalid_paths
        if invalid:
            raise ValueError(
                f"{row.matrix_id} contains references outside coverage taxonomy/plan: "
                f"{', '.join(invalid)}"
            )


def _repair_matrix_task_targets(
    matrix: CoverageMatrix,
    coverage_plan: CoveragePlan,
) -> CoverageMatrix:
    labels = {item.label for item in coverage_plan.coverage_labels}
    p0_labels = [item.label for item in coverage_plan.coverage_labels if item.priority == "P0"]
    fallback = p0_labels[:4] or [item.label for item in coverage_plan.coverage_labels[:4]]
    repaired_rows = []
    for row in matrix.rows:
        valid_targets = [target for target in row.task_targets if target in labels]
        if not valid_targets:
            valid_targets = fallback
        repaired_rows.append(row.model_copy(update={"task_targets": valid_targets}))
    return matrix.model_copy(update={"rows": repaired_rows})


def _ensure_matrix_label_coverage(
    matrix: CoverageMatrix,
    coverage_plan: CoveragePlan,
) -> CoverageMatrix:
    """Close planning gaps without inventing scene-specific content.

    The model owns the coverage labels and matrix semantics. This guard only
    ensures every generated label is assigned to at least one existing matrix
    row, so downstream case cards can be audited against the complete plan.
    """
    rows = list(matrix.rows)
    if not rows:
        return matrix

    covered = {target for row in rows for target in row.task_targets}
    missing = [item for item in coverage_plan.coverage_labels if item.label not in covered]
    if not missing:
        return matrix

    repaired_rows = rows[:]
    for label in missing:
        candidate_indexes = [
            index for index, row in enumerate(repaired_rows) if row.priority == label.priority
        ]
        if not candidate_indexes:
            candidate_indexes = list(range(len(repaired_rows)))
        target_index = min(
            candidate_indexes,
            key=lambda index: (
                len(repaired_rows[index].task_targets),
                repaired_rows[index].case_count,
                index,
            ),
        )
        row = repaired_rows[target_index]
        expected_agent_capabilities = list(row.expected_agent_capabilities)
        expected_agent_capabilities.append(
            f"覆盖检查点 {label.label}：{label.definition}"
        )
        forbidden_failures = list(row.forbidden_failures)
        forbidden_failures.append(
            f"不得遗漏检查点 {label.label} 所需证据：{label.evidence_required}"
        )
        repaired_rows[target_index] = row.model_copy(
            update={
                "task_targets": list(dict.fromkeys([*row.task_targets, label.label])),
                "expected_agent_capabilities": expected_agent_capabilities,
                "forbidden_failures": forbidden_failures,
            }
        )
    return matrix.model_copy(update={"rows": repaired_rows})


def _normalize_scoring_rubric(
    rubric: ScoringRubric,
    *,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
) -> ScoringRubric:
    dimensions = [
        _normalize_dimension_check_items(dimension)
        for dimension in rubric.dimensions
    ]
    normalized = rubric.model_copy(update={"dimensions": dimensions})
    normalized = _map_missing_p0_labels(normalized, coverage_plan)
    return _map_compliance_rules(normalized, scene_asset)


def _normalize_dimension_check_items(dimension: ScoringDimension) -> ScoringDimension:
    if not dimension.check_items:
        return dimension.model_copy(
            update={
                "check_items": [
                    ScoringCheckItem(
                        check_id=f"{dimension.dimension_id}__full_score",
                        name=dimension.name,
                        points=dimension.weight,
                        pass_condition=(
                            dimension.full_score_standard
                            or dimension.description
                            or f"满足{dimension.name}要求"
                        ),
                        applicability="always",
                        evidence_required=dimension.evidence_required,
                    )
                ]
            }
        )

    target = float(dimension.weight)
    items = list(dimension.check_items)
    current = sum(float(item.points) for item in items)
    if abs(current - target) <= 0.01:
        return dimension

    if target <= 0:
        normalized_points = [0.0 for _ in items]
    elif current <= 0:
        base = target / len(items)
        normalized_points = [base for _ in items]
    else:
        normalized_points = [float(item.points) * target / current for item in items]

    if normalized_points:
        rounded_prefix = [round(value, 4) for value in normalized_points[:-1]]
        last = round(target - sum(rounded_prefix), 4)
        normalized_points = [*rounded_prefix, max(0.0, last)]

    normalized_items = [
        item.model_copy(update={"points": normalized_points[index]})
        for index, item in enumerate(items)
    ]
    return dimension.model_copy(update={"check_items": normalized_items})


def _map_missing_p0_labels(
    rubric: ScoringRubric,
    coverage_plan: CoveragePlan,
) -> ScoringRubric:
    mapped_labels = {
        label
        for dimension in rubric.dimensions
        for check_item in dimension.check_items
        for label in check_item.covered_labels
    }
    missing_labels = [
        item.label
        for item in coverage_plan.coverage_labels
        if item.priority == "P0" and item.label not in mapped_labels
    ]
    if not missing_labels:
        return rubric

    dimensions = list(rubric.dimensions)
    for label in missing_labels:
        dimension_index = _best_dimension_index_for_label(dimensions, label)
        dimension = dimensions[dimension_index]
        check_index = _best_check_item_index_for_label(dimension.check_items, label)
        check_item = dimension.check_items[check_index]
        covered_labels = list(dict.fromkeys([*check_item.covered_labels, label]))
        check_items = list(dimension.check_items)
        check_items[check_index] = check_item.model_copy(
            update={"covered_labels": covered_labels}
        )
        dimensions[dimension_index] = dimension.model_copy(update={"check_items": check_items})
    return rubric.model_copy(update={"dimensions": dimensions})


def _best_dimension_index_for_label(
    dimensions: list[ScoringDimension],
    label: str,
) -> int:
    label_tokens = _identifier_tokens(label)
    preferred_keywords = _dimension_keywords_for_label(label)

    def score(dimension: ScoringDimension) -> tuple[int, int]:
        text = " ".join(
            [
                dimension.dimension_id,
                dimension.name,
                dimension.description,
                dimension.full_score_standard,
            ]
        ).lower()
        keyword_score = sum(1 for keyword in preferred_keywords if keyword in text)
        token_score = sum(1 for token in label_tokens if token in text)
        return keyword_score, token_score

    return max(range(len(dimensions)), key=lambda index: (*score(dimensions[index]), -index))


def _dimension_keywords_for_label(label: str) -> list[str]:
    lower = label.lower()
    if lower.startswith(("flow_", "process_")):
        return ["flow", "process", "流程"]
    if lower.startswith("knowledge_"):
        return ["knowledge", "知识"]
    if lower.startswith("compliance_"):
        return ["compliance", "合规"]
    if lower.startswith(("quality_", "expression_")):
        return ["quality", "expression", "表达"]
    if lower.startswith(("task_", "goal_")) or "_goal_" in lower:
        return ["task", "completion", "任务"]
    return []


def _best_check_item_index_for_label(
    check_items: list[ScoringCheckItem],
    label: str,
) -> int:
    label_tokens = _identifier_tokens(label)

    def score(item: ScoringCheckItem) -> tuple[int, int]:
        text = " ".join(
            [
                item.check_id,
                item.name,
                item.pass_condition,
                item.applicability,
                item.evidence_required,
            ]
        ).lower()
        token_score = sum(1 for token in label_tokens if token in text)
        return token_score, -len(item.covered_labels)

    return max(range(len(check_items)), key=lambda index: (*score(check_items[index]), -index))


def _map_compliance_rules(
    rubric: ScoringRubric,
    scene_asset: SceneAsset,
) -> ScoringRubric:
    veto_rules = list(rubric.veto_rules)
    risk_rules = list(rubric.risk_rules)
    mapped_ids = {item.rule_id for item in veto_rules} | {item.rule_id for item in risk_rules}

    for compliance_rule in scene_asset.compliance_rules:
        if not compliance_rule.id or compliance_rule.id in mapped_ids:
            continue

        if compliance_rule.severity == "critical":
            match_index = _matching_rule_index(compliance_rule.id, veto_rules)
            if match_index is not None:
                veto_rules[match_index] = _veto_from_compliance_rule(
                    compliance_rule,
                    existing=veto_rules[match_index],
                )
            else:
                risk_match_index = _matching_rule_index(compliance_rule.id, risk_rules)
                if risk_match_index is not None:
                    risk_rules.pop(risk_match_index)
                veto_rules.append(_veto_from_compliance_rule(compliance_rule))
        else:
            match_index = _matching_rule_index(compliance_rule.id, risk_rules)
            if match_index is not None:
                risk_rules[match_index] = _risk_from_compliance_rule(
                    compliance_rule,
                    existing=risk_rules[match_index],
                )
            else:
                veto_match_index = _matching_rule_index(compliance_rule.id, veto_rules)
                if veto_match_index is not None:
                    veto_rules.pop(veto_match_index)
                risk_rules.append(_risk_from_compliance_rule(compliance_rule))
        mapped_ids.add(compliance_rule.id)

    return rubric.model_copy(update={"veto_rules": veto_rules, "risk_rules": risk_rules})


def _matching_rule_index(rule_id: str, rules: list[VetoRule] | list[RiskScoringRule]) -> int | None:
    target_tokens = _identifier_tokens(rule_id)
    if not target_tokens:
        return None
    best_index: int | None = None
    best_score = 0
    for index, rule in enumerate(rules):
        rule_tokens = _identifier_tokens(rule.rule_id)
        overlap = target_tokens & rule_tokens
        has_strong_token = any(len(token) >= 6 for token in overlap)
        score = len(overlap) * 10 + (1 if has_strong_token else 0)
        if score > best_score and (len(overlap) >= min(2, len(target_tokens)) or has_strong_token):
            best_score = score
            best_index = index
    return best_index


def _veto_from_compliance_rule(
    compliance_rule: Any,
    *,
    existing: VetoRule | None = None,
) -> VetoRule:
    return VetoRule(
        rule_id=compliance_rule.id,
        description=existing.description if existing and existing.description else compliance_rule.rule,
        severity="critical",
        evidence_required=(
            existing.evidence_required
            if existing and existing.evidence_required
            else compliance_rule.negative_examples_description
        ),
    )


def _risk_from_compliance_rule(
    compliance_rule: Any,
    *,
    existing: RiskScoringRule | None = None,
) -> RiskScoringRule:
    return RiskScoringRule(
        rule_id=compliance_rule.id,
        description=existing.description if existing and existing.description else compliance_rule.rule,
        severity=existing.severity if existing else "medium",
        default_deduction=existing.default_deduction if existing else 5.0,
        evidence_required=(
            existing.evidence_required
            if existing and existing.evidence_required
            else compliance_rule.negative_examples_description
        ),
    )


def _identifier_tokens(value: str) -> set[str]:
    raw_tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", value.lower())
        if token
    ]
    ignored = {"cr", "risk", "veto", "rule", "rules", "no", "not", "compliance"}
    return {
        _singularize_token(token)
        for token in raw_tokens
        if token not in ignored
    }


def _singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


def generate_scoring_rubric(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    input_hash: str,
    retry_count: int,
) -> ScoringRubric:
    rubric = complete_model(
        llm,
        task_name="scoring_rubric",
        prompt=scoring_rubric_prompt(
            eval_standard_text=eval_standard_text,
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            output_schema=schema_text(ScoringRubric),
        ),
        model_type=ScoringRubric,
        retry_count=retry_count,
    )
    metadata = rubric.generation_metadata.model_copy(
        update={
            "model": llm.model_name,
            "created_at": utc_now_iso(),
            "input_hash": input_hash,
            "source_eval_standard_path": scene_asset.source_eval_standard_path,
            "asset_version": scene_asset.generation_metadata.asset_version,
        }
    )
    normalized_rubric = rubric.model_copy(
        update={"scene_id": scene_asset.scene_id, "generation_metadata": metadata}
    )
    normalized_rubric = _normalize_scoring_rubric(
        normalized_rubric,
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
    )
    assert_valid_scoring_rubric(
        scoring_rubric=normalized_rubric,
        coverage_plan=coverage_plan,
        scene_asset=scene_asset,
    )
    return normalized_rubric


def write_asset_generation_report(asset_dir: Path, scene_asset: SceneAsset) -> None:
    lines = [
        "# 资产生成报告",
        "",
        f"- scene_id: {scene_asset.scene_id}",
        f"- scene_name: {scene_asset.scene_name}",
        f"- source: {scene_asset.source_eval_standard_path}",
        f"- model: {scene_asset.generation_metadata.model}",
        f"- input_hash: {scene_asset.generation_metadata.input_hash}",
        f"- created_at: {scene_asset.generation_metadata.created_at}",
    ]
    (asset_dir / "asset_generation_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_coverage_gap_report(
    asset_dir: Path,
    *,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy | None,
    coverage_matrix: CoverageMatrix | None,
    case_generation_plan: CaseGenerationPlan | None,
    user_profiles: UserProfileCollection | None = None,
    case_cards: CaseCardCollection,
) -> None:
    target_counts = {item.label: 0 for item in coverage_plan.coverage_labels}
    behavior_counts: dict[str, int] = {}
    branch_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    state_path_counts: dict[str, int] = {}
    matrix_counts: dict[str, int] = {}
    profile_counts: dict[str, int] = {}
    for case_card in case_cards.cases:
        for target in case_card.coverage_targets:
            target_counts[target] = target_counts.get(target, 0) + 1
        for item in case_card.user_behavior_tags:
            behavior_counts[item] = behavior_counts.get(item, 0) + 1
        for item in case_card.flow_branch_tags:
            branch_counts[item] = branch_counts.get(item, 0) + 1
        for item in case_card.risk_probe_tags:
            risk_counts[item] = risk_counts.get(item, 0) + 1
        for item in case_card.dynamic_state_path_tags:
            state_path_counts[item] = state_path_counts.get(item, 0) + 1
        if case_card.matrix_id:
            matrix_counts[case_card.matrix_id] = matrix_counts.get(case_card.matrix_id, 0) + 1
        if case_card.profile_id:
            profile_counts[case_card.profile_id] = profile_counts.get(case_card.profile_id, 0) + 1

    p0_labels = [item.label for item in coverage_plan.coverage_labels if item.priority == "P0"]
    covered_labels = [label for label, count in target_counts.items() if count > 0]
    covered_p0 = [label for label in p0_labels if target_counts.get(label, 0) > 0]
    quality_metrics = _simulator_quality_metrics(
        coverage_plan=coverage_plan,
        coverage_taxonomy=coverage_taxonomy,
        coverage_matrix=coverage_matrix,
        user_profiles=user_profiles,
        case_cards=case_cards,
        target_counts=target_counts,
        branch_counts=branch_counts,
        behavior_counts=behavior_counts,
        risk_counts=risk_counts,
        state_path_counts=state_path_counts,
        matrix_counts=matrix_counts,
        profile_counts=profile_counts,
    )
    lines = [
        "# 覆盖缺口报告",
        "",
        f"- case 总数：{len(case_cards.cases)}",
        f"- coverage label 覆盖率：{len(covered_labels)}/{len(target_counts)}",
        f"- P0 label 覆盖率：{len(covered_p0)}/{len(p0_labels)}",
        f"- 覆盖矩阵行数：{len(coverage_matrix.rows) if coverage_matrix else 0}",
        "",
        "## Coverage Label 覆盖",
        "",
        "| label | priority | case_count |",
        "|---|---|---:|",
    ]
    priority_by_label = {item.label: item.priority for item in coverage_plan.coverage_labels}
    for label in sorted(target_counts):
        lines.append(f"| {label} | {priority_by_label.get(label, '')} | {target_counts[label]} |")

    lines.extend(["", "## 覆盖矩阵计划与实际", ""])
    if coverage_matrix and case_generation_plan:
        planned = {item.matrix_id: item.case_count for item in case_generation_plan.allocations}
        lines.extend(["| matrix_id | priority | planned | generated |", "|---|---|---:|---:|"])
        for row in coverage_matrix.rows:
            lines.append(
                f"| {row.matrix_id} | {row.priority} | "
                f"{planned.get(row.matrix_id, row.case_count)} | {matrix_counts.get(row.matrix_id, 0)} |"
            )
    else:
        lines.append("- 当前资产未包含覆盖矩阵。")

    lines.extend(
        [
            "",
            "## 用户模拟器质量评估",
            "",
            "| 指标 | 公式 | 数值 | 说明 |",
            "|---|---|---:|---|",
        ]
    )
    for metric in quality_metrics:
        lines.append(
            f"| {metric['name']} | {metric['formula']} | {metric['value']} | {metric['note']} |"
        )

    lines.extend(["", "## 用户行为/流程/风险/动态状态覆盖", ""])
    _append_count_section(lines, "用户行为", behavior_counts, coverage_taxonomy.user_behaviors if coverage_taxonomy else [])
    _append_count_section(lines, "流程分支", branch_counts, coverage_taxonomy.flow_branches if coverage_taxonomy else [])
    _append_count_section(lines, "风险探针", risk_counts, coverage_taxonomy.risk_probes if coverage_taxonomy else [])
    _append_count_section(lines, "动态状态路径", state_path_counts, coverage_taxonomy.dynamic_state_paths if coverage_taxonomy else [])

    missing_labels = [label for label, count in target_counts.items() if count == 0]
    quality_gaps = _simulator_quality_gaps(
        coverage_plan=coverage_plan,
        coverage_taxonomy=coverage_taxonomy,
        target_counts=target_counts,
        branch_counts=branch_counts,
        behavior_counts=behavior_counts,
        risk_counts=risk_counts,
        state_path_counts=state_path_counts,
    )
    lines.extend(["", "## 需要补测", ""])
    if missing_labels:
        for label in missing_labels:
            lines.append(f"- coverage label 未覆盖：{label}")
    else:
        lines.append("- 暂无 coverage label 缺口。")
    if quality_gaps:
        lines.append("")
        for gap in quality_gaps:
            lines.append(f"- {gap}")

    (asset_dir / "coverage_gap_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _simulator_quality_metrics(
    *,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy | None,
    coverage_matrix: CoverageMatrix | None,
    user_profiles: UserProfileCollection | None,
    case_cards: CaseCardCollection,
    target_counts: dict[str, int],
    branch_counts: dict[str, int],
    behavior_counts: dict[str, int],
    risk_counts: dict[str, int],
    state_path_counts: dict[str, int],
    matrix_counts: dict[str, int],
    profile_counts: dict[str, int],
) -> list[dict[str, str]]:
    labels = coverage_plan.coverage_labels
    branches = coverage_taxonomy.flow_branches if coverage_taxonomy else []
    behaviors = coverage_taxonomy.user_behaviors if coverage_taxonomy else []
    risk_probes = coverage_taxonomy.risk_probes if coverage_taxonomy else []
    state_paths = coverage_taxonomy.dynamic_state_paths if coverage_taxonomy else []
    p0_labels = [item for item in labels if item.priority == "P0"]
    p0_branches = [item for item in branches if item.priority == "P0"]
    p0_risk_probes = [item for item in risk_probes if item.priority == "P0"]
    p0_state_paths = [item for item in state_paths if item.priority == "P0"]
    covered_failure_modes = _covered_failure_modes(coverage_matrix, matrix_counts)
    all_failure_modes = _all_failure_modes(coverage_matrix)
    return [
        _metric(
            "指令点覆盖率",
            "已覆盖 coverage label / 全部 coverage label",
            _covered_count(target_counts, [item.label for item in labels]),
            len(labels),
            "衡量 case 是否覆盖任务模板中的必做项、知识项和禁忌项。",
        ),
        _metric(
            "P0 指令充足率",
            "P0 label 样本数达标 / 全部 P0 label",
            _sufficient_count(target_counts, p0_labels),
            len(p0_labels),
            "P0 默认至少需要 2 个样本，避免只出现一次但无法稳定评估。",
        ),
        _metric(
            "分支覆盖率",
            "已覆盖流程分支 / 全部流程分支",
            _covered_count(branch_counts, [item.item_id for item in branches]),
            len(branches),
            "覆盖愿意、犹豫、拒绝、忙碌、质疑等业务流程路径。",
        ),
        _metric(
            "关键分支充足率",
            "P0 流程分支样本数达标 / 全部 P0 流程分支",
            _sufficient_count(branch_counts, p0_branches),
            len(p0_branches),
            "关键流程分支默认至少 2 个样本。",
        ),
        _metric(
            "用户行为覆盖率",
            "已覆盖用户行为 / 全部用户行为",
            _covered_count(behavior_counts, [item.item_id for item in behaviors]),
            len(behaviors),
            "衡量模拟用户是否覆盖配合、拒绝、怀疑、诱导违规等行为。",
        ),
        _metric(
            "风险探针覆盖率",
            "已覆盖风险探针 / 全部风险探针",
            _covered_count(risk_counts, [item.item_id for item in risk_probes]),
            len(risk_probes),
            "衡量是否有 case 主动测试虚假承诺、强迫配送、错误解释等风险。",
        ),
        _metric(
            "关键风险探针充足率",
            "P0 风险探针样本数达标 / 全部 P0 风险探针",
            _sufficient_count(risk_counts, p0_risk_probes),
            len(p0_risk_probes),
            "P0 风险探针默认至少 2 个样本。",
        ),
        _metric(
            "用户画像多样性",
            "画像使用率、画像属性差异、初始状态差异的均值",
            _profile_diversity_score(user_profiles, case_cards, profile_counts),
            100,
            "同时看 profile 是否被使用、画像字段是否有差异、case 初始心理状态是否有差异。",
            value_is_percent=True,
        ),
        _metric(
            "对话状态覆盖率",
            "已覆盖动态状态路径 / 全部动态状态路径",
            _covered_count(state_path_counts, [item.item_id for item in state_paths]),
            len(state_paths),
            "覆盖信任上升、耐心下降、拒绝转愿意、突然挂断等动态路径。",
        ),
        _metric(
            "关键状态路径充足率",
            "P0 动态状态路径样本数达标 / 全部 P0 动态状态路径",
            _sufficient_count(state_path_counts, p0_state_paths),
            len(p0_state_paths),
            "P0 动态状态路径默认至少 2 个样本。",
        ),
        _metric(
            "缺陷暴露设计率",
            "已生成 case 的 forbidden_failures / 矩阵设计的 forbidden_failures",
            len(covered_failure_modes),
            len(all_failure_modes),
            "说明测试用户是否覆盖了坏客服样例应暴露的失败模式；实际发现率由缺陷注入评测验证。",
        ),
    ]


def _simulator_quality_gaps(
    *,
    coverage_plan: CoveragePlan,
    coverage_taxonomy: CoverageTaxonomy | None,
    target_counts: dict[str, int],
    branch_counts: dict[str, int],
    behavior_counts: dict[str, int],
    risk_counts: dict[str, int],
    state_path_counts: dict[str, int],
) -> list[str]:
    gaps: list[str] = []
    p0_labels = [
        item for item in coverage_plan.coverage_labels
        if item.priority == "P0"
    ]
    gaps.extend(_insufficient_items("P0 coverage label 样本不足", p0_labels, target_counts))
    if coverage_taxonomy:
        gaps.extend(_insufficient_items("流程分支样本不足", coverage_taxonomy.flow_branches, branch_counts))
        gaps.extend(_insufficient_items("用户行为未覆盖", coverage_taxonomy.user_behaviors, behavior_counts, minimum=1))
        gaps.extend(_insufficient_items("风险探针样本不足", coverage_taxonomy.risk_probes, risk_counts))
        gaps.extend(_insufficient_items("动态状态路径样本不足", coverage_taxonomy.dynamic_state_paths, state_path_counts))
    return gaps


def _metric(
    name: str,
    formula: str,
    numerator: int,
    denominator: int,
    note: str,
    *,
    value_is_percent: bool = False,
) -> dict[str, str]:
    if value_is_percent:
        value = f"{numerator:.1f}%"
    else:
        value = f"{numerator}/{denominator} ({_ratio(numerator, denominator)})"
    return {
        "name": name,
        "formula": formula,
        "value": value,
        "note": note,
    }


def _covered_count(counts: dict[str, int], item_ids: list[str]) -> int:
    return sum(1 for item_id in item_ids if counts.get(item_id, 0) > 0)


def _sufficient_count(counts: dict[str, int], items: list[Any]) -> int:
    return sum(
        1
        for item in items
        if counts.get(_item_id(item), 0) >= _required_sample_count(item)
    )


def _insufficient_items(
    title: str,
    items: list[Any],
    counts: dict[str, int],
    *,
    minimum: int | None = None,
) -> list[str]:
    output = []
    for item in items:
        item_id = _item_id(item)
        required = minimum if minimum is not None else _required_sample_count(item)
        count = counts.get(item_id, 0)
        if count < required:
            output.append(f"{title}：{item_id} 当前 {count}，建议至少 {required}")
    return output


def _required_sample_count(item: Any) -> int:
    return 2 if getattr(item, "priority", "P1") == "P0" else 1


def _item_id(item: Any) -> str:
    return str(getattr(item, "label", "") or getattr(item, "item_id", ""))


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0%"
    return f"{numerator / denominator:.1%}"


def _profile_diversity_score(
    user_profiles: UserProfileCollection | None,
    case_cards: CaseCardCollection,
    profile_counts: dict[str, int],
) -> int:
    profile_count = len(user_profiles.profiles) if user_profiles else 0
    profile_usage = _percent(len(profile_counts), profile_count)
    profile_attribute_diversity = _profile_attribute_diversity(user_profiles)
    initial_state_diversity = _initial_state_diversity(case_cards)
    return round((profile_usage + profile_attribute_diversity + initial_state_diversity) / 3)


def _profile_attribute_diversity(user_profiles: UserProfileCollection | None) -> int:
    profiles = user_profiles.profiles if user_profiles else []
    if len(profiles) <= 1:
        return 0
    fields = [
        "personality",
        "communication_style",
        "knowledge_level",
        "risk_tendency",
        "cooperation_curve",
        "current_context",
    ]
    varied = 0
    for field in fields:
        values = {str(getattr(profile, field, "")).strip() for profile in profiles}
        values.discard("")
        if len(values) >= 2:
            varied += 1
    return _percent(varied, len(fields))


def _initial_state_diversity(case_cards: CaseCardCollection) -> int:
    cases = case_cards.cases
    if len(cases) <= 1:
        return 0
    dimensions = [
        {case.initial_state.emotion for case in cases},
        {_bucket(case.initial_state.patience) for case in cases},
        {_bucket(case.initial_state.trust) for case in cases},
        {_bucket(case.initial_state.suspicion) for case in cases},
        {case.initial_state.busy_level for case in cases},
        {case.initial_state.willingness for case in cases},
    ]
    varied = sum(1 for values in dimensions if len({value for value in values if value}) >= 2)
    return _percent(varied, len(dimensions))


def _bucket(value: int) -> str:
    if value < 34:
        return "low"
    if value < 67:
        return "medium"
    return "high"


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round(numerator / denominator * 100)


def _all_failure_modes(coverage_matrix: CoverageMatrix | None) -> set[str]:
    if not coverage_matrix:
        return set()
    return {
        item
        for row in coverage_matrix.rows
        for item in row.forbidden_failures
        if item
    }


def _covered_failure_modes(
    coverage_matrix: CoverageMatrix | None,
    matrix_counts: dict[str, int],
) -> set[str]:
    if not coverage_matrix:
        return set()
    return {
        item
        for row in coverage_matrix.rows
        if matrix_counts.get(row.matrix_id, 0) > 0
        for item in row.forbidden_failures
        if item
    }


def _append_count_section(lines: list[str], title: str, counts: dict[str, int], items: list) -> None:
    lines.extend([f"### {title}", "", "| item_id | name | case_count |", "|---|---|---:|"])
    if not items:
        lines.append("| - | - | 0 |")
        lines.append("")
        return
    for item in items:
        lines.append(f"| {item.item_id} | {item.name} | {counts.get(item.item_id, 0)} |")
    lines.append("")
