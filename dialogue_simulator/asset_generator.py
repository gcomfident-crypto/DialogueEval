from __future__ import annotations

from pathlib import Path

from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import (
    SYSTEM_JSON_ONLY,
    case_cards_prompt,
    coverage_plan_prompt,
    materialize_eval_standard_prompt,
    scene_asset_prompt,
    schema_text,
    scoring_rubric_prompt,
    user_profiles_prompt,
)
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseCardCollection,
    CoveragePlan,
    GenerationMetadata,
    GenerationPolicy,
    MaterializedEvalStandard,
    SceneAsset,
    ScoringRubric,
    UserProfileCollection,
    utc_now_iso,
)
from dialogue_simulator.structured_output import StructuredOutputError, parse_model


def complete_model(
    llm: LLMClient,
    *,
    task_name: str,
    prompt: str,
    model_type: type,
    retry_count: int = 1,
):
    messages = [
        {"role": "system", "content": SYSTEM_JSON_ONLY},
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
    raise StructuredOutputError(last_error)


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


def generate_case_cards(
    llm: LLMClient,
    *,
    eval_standard_text: str,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    user_profiles: UserProfileCollection,
    generation_policy: GenerationPolicy,
    retry_count: int,
) -> CaseCardCollection:
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
    labels = {item.label for item in coverage_plan.coverage_labels}
    profile_ids = {item.profile_id for item in user_profiles.profiles}
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
        invalid_targets = [
            target for target in case_card.coverage_targets if target not in labels
        ]
        if invalid_targets:
            raise ValueError(
                f"{case_card.case_id} contains targets outside coverage plan: "
                f"{', '.join(invalid_targets)}"
            )
        if case_card.profile_id not in profile_ids:
            raise ValueError(
                f"{case_card.case_id} references unknown profile_id {case_card.profile_id}"
            )
        repaired_cases.append(case_card.model_copy(update={"scene_id": scene_asset.scene_id}))
    return case_cards.model_copy(
        update={"scene_id": scene_asset.scene_id, "cases": repaired_cases}
    )


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
    return rubric.model_copy(
        update={"scene_id": scene_asset.scene_id, "generation_metadata": metadata}
    )


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
