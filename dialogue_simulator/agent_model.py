from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import agent_turn_prompt, schema_text
from dialogue_simulator.schemas import (
    AgentTurnOutput,
    BusinessConfig,
    CaseCard,
    ConversationState,
    CoveragePlan,
    SceneAsset,
    TurnRecord,
)


def generate_agent_turn(
    llm: LLMClient,
    *,
    scene_asset: SceneAsset,
    coverage_plan: CoveragePlan,
    case_card: CaseCard,
    business_config: BusinessConfig,
    conversation_state: ConversationState,
    history: list[TurnRecord],
    retry_count: int = 1,
) -> AgentTurnOutput:
    return complete_model(
        llm,
        task_name="agent_turn",
        prompt=agent_turn_prompt(
            scene_asset=scene_asset,
            coverage_plan=coverage_plan,
            case_card=case_card,
            business_config=business_config,
            conversation_state=conversation_state,
            history=[turn.model_dump(mode="json") for turn in history],
            output_schema=schema_text(AgentTurnOutput),
        ),
        model_type=AgentTurnOutput,
        retry_count=retry_count,
    )
