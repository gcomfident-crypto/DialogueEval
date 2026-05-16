from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from dialogue_simulator.prompt_registry import (
    AGENT_TURN_PROMPT,
    CASE_CARDS_PROMPT,
    CASE_EVALUATION_PROMPT,
    COVERAGE_JUDGE_PROMPT,
    COVERAGE_PLAN_PROMPT,
    MATERIALIZE_EVAL_STANDARD_PROMPT,
    SCENE_ASSET_PROMPT,
    SCORING_RUBRIC_PROMPT,
    SYSTEM_JSON_ONLY,
    SYSTEM_JSON_ONLY_PROMPT,
    USER_PROFILES_PROMPT,
    USER_TURN_PROMPT,
)
from dialogue_simulator.prompt_store import render_prompt_text
from dialogue_simulator.runtime_context import (
    build_agent_runtime_context,
    build_evaluation_runtime_context,
    build_judge_runtime_context,
    build_user_runtime_context,
)


def system_json_only_prompt() -> str:
    return render_prompt_text(SYSTEM_JSON_ONLY_PROMPT)


def schema_text(model_type: type[BaseModel]) -> str:
    return json.dumps(model_type.model_json_schema(), ensure_ascii=False, indent=2)


def json_text(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, indent=2)


def scene_asset_prompt(
    eval_standard_text: str,
    business_config: BaseModel,
    input_hash: str,
    output_schema: str,
) -> str:
    return render_prompt_text(
        SCENE_ASSET_PROMPT,
        {
            "input_hash": input_hash,
            "business_config": json_text(business_config),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def materialize_eval_standard_prompt(
    eval_standard_text: str,
    business_config: BaseModel,
    generation_policy: BaseModel,
    output_schema: str,
) -> str:
    return render_prompt_text(
        MATERIALIZE_EVAL_STANDARD_PROMPT,
        {
            "business_config": json_text(business_config),
            "generation_policy": json_text(generation_policy),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def coverage_plan_prompt(
    eval_standard_text: str,
    scene_asset: BaseModel,
    generation_policy: BaseModel,
    output_schema: str,
) -> str:
    return render_prompt_text(
        COVERAGE_PLAN_PROMPT,
        {
            "scene_asset": json_text(scene_asset),
            "generation_policy": json_text(generation_policy),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def user_profiles_prompt(
    eval_standard_text: str,
    scene_asset: BaseModel,
    coverage_plan: BaseModel,
    generation_policy: BaseModel,
    output_schema: str,
) -> str:
    return render_prompt_text(
        USER_PROFILES_PROMPT,
        {
            "scene_asset": json_text(scene_asset),
            "coverage_plan": json_text(coverage_plan),
            "generation_policy": json_text(generation_policy),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def case_cards_prompt(
    eval_standard_text: str,
    scene_asset: BaseModel,
    coverage_plan: BaseModel,
    user_profiles: BaseModel,
    generation_policy: BaseModel,
    output_schema: str,
) -> str:
    return render_prompt_text(
        CASE_CARDS_PROMPT,
        {
            "scene_asset": json_text(scene_asset),
            "coverage_plan": json_text(coverage_plan),
            "user_profiles": json_text(user_profiles),
            "generation_policy": json_text(generation_policy),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def scoring_rubric_prompt(
    eval_standard_text: str,
    scene_asset: BaseModel,
    coverage_plan: BaseModel,
    output_schema: str,
) -> str:
    return render_prompt_text(
        SCORING_RUBRIC_PROMPT,
        {
            "scene_asset": json_text(scene_asset),
            "coverage_plan": json_text(coverage_plan),
            "eval_standard_text": eval_standard_text,
            "output_schema": output_schema,
        },
    )


def agent_turn_prompt(
    scene_asset: BaseModel,
    coverage_plan: BaseModel,
    case_card: BaseModel,
    business_config: BaseModel,
    conversation_state: BaseModel,
    history: list[dict[str, Any]],
    output_schema: str,
) -> str:
    runtime_context = build_agent_runtime_context(
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
        case_card=case_card,
        business_config=business_config,
        conversation_state=conversation_state,
        history=history,
    )
    return render_prompt_text(
        AGENT_TURN_PROMPT,
        {
            "runtime_context": json_text(runtime_context),
            "scene_asset": json_text(scene_asset),
            "coverage_plan": json_text(coverage_plan),
            "case_card": json_text(case_card),
            "business_config": json_text(business_config),
            "conversation_state": json_text(conversation_state),
            "history": json_text(history),
            "output_schema": output_schema,
        },
    )


def case_evaluation_prompt(
    eval_standard_text: str,
    scene_asset: BaseModel,
    coverage_plan: BaseModel,
    scoring_rubric: BaseModel,
    conversation_result: BaseModel,
    business_config: BaseModel,
    output_schema: str,
) -> str:
    runtime_context = build_evaluation_runtime_context(
        eval_standard_text=eval_standard_text,
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
        scoring_rubric=scoring_rubric,
        conversation_result=conversation_result,
        business_config=business_config,
    )
    return render_prompt_text(
        CASE_EVALUATION_PROMPT,
        {
            "runtime_context": json_text(runtime_context),
            "eval_standard_text": eval_standard_text,
            "scene_asset": json_text(scene_asset),
            "coverage_plan": json_text(coverage_plan),
            "scoring_rubric": json_text(scoring_rubric),
            "business_config": json_text(business_config),
            "conversation_result": json_text(conversation_result),
            "output_schema": output_schema,
        },
    )


def user_turn_prompt(
    scene_asset: BaseModel,
    user_profile: BaseModel,
    case_card: BaseModel,
    conversation_state: BaseModel,
    history: list[dict[str, Any]],
    output_schema: str,
) -> str:
    runtime_context = build_user_runtime_context(
        scene_asset=scene_asset,
        user_profile=user_profile,
        case_card=case_card,
        conversation_state=conversation_state,
        history=history,
    )
    return render_prompt_text(
        USER_TURN_PROMPT,
        {
            "runtime_context": json_text(runtime_context),
            "scene_asset": json_text(scene_asset),
            "user_profile": json_text(user_profile),
            "case_card": json_text(case_card),
            "conversation_state": json_text(conversation_state),
            "history": json_text(history),
            "output_schema": output_schema,
        },
    )


def coverage_judge_prompt(
    coverage_plan: BaseModel,
    scene_asset: BaseModel,
    case_card: BaseModel,
    history: list[dict[str, Any]],
    current_triggered_targets: list[str],
    output_schema: str,
) -> str:
    runtime_context = build_judge_runtime_context(
        coverage_plan=coverage_plan,
        scene_asset=scene_asset,
        case_card=case_card,
        history=history,
        current_triggered_targets=current_triggered_targets,
    )
    return render_prompt_text(
        COVERAGE_JUDGE_PROMPT,
        {
            "runtime_context": json_text(runtime_context),
            "coverage_plan": json_text(coverage_plan),
            "scene_asset": json_text(scene_asset),
            "case_card": json_text(case_card),
            "current_triggered_targets": json_text(current_triggered_targets),
            "history": json_text(history),
            "output_schema": output_schema,
        },
    )
