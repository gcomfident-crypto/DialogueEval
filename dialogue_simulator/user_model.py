from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import schema_text, user_turn_prompt
from dialogue_simulator.schemas import (
    CaseCard,
    ConversationState,
    SceneAsset,
    TurnRecord,
    UserProfile,
    UserTurnOutput,
)


INTERNAL_TERMS = [
    "coverage",
    "测试点",
    "评测",
    "case card",
    "case_card",
    "隐藏配置",
]


def generate_user_turn(
    llm: LLMClient,
    *,
    scene_asset: SceneAsset,
    user_profile: UserProfile,
    case_card: CaseCard,
    conversation_state: ConversationState,
    history: list[TurnRecord],
    retry_count: int = 1,
) -> UserTurnOutput:
    output = complete_model(
        llm,
        task_name="user_turn",
        prompt=user_turn_prompt(
            scene_asset=scene_asset,
            user_profile=user_profile,
            case_card=case_card,
            conversation_state=conversation_state,
            history=[turn.model_dump(mode="json") for turn in history],
            output_schema=schema_text(UserTurnOutput),
        ),
        model_type=UserTurnOutput,
        retry_count=retry_count,
    )
    if contains_internal_terms(output.visible_reply):
        raise ValueError("user visible_reply leaked internal evaluation terms")
    return output


def contains_internal_terms(text: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in INTERNAL_TERMS)
