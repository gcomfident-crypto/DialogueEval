from __future__ import annotations

from dialogue_simulator.asset_generator import complete_model
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.prompt_templates import schema_text, state_update_prompt
from dialogue_simulator.schemas import (
    AgentTurnOutput,
    CaseCard,
    ConversationState,
    CoverageJudgeOutput,
    SceneAsset,
    StateSnapshot,
    StateTransitionRecord,
    StateUpdateOutput,
    TurnRecord,
    UserProfile,
    UserTurnOutput,
)


def generate_state_update(
    llm: LLMClient,
    *,
    scene_asset: SceneAsset,
    user_profile: UserProfile,
    case_card: CaseCard,
    conversation_state: ConversationState,
    agent_output: AgentTurnOutput,
    user_output: UserTurnOutput,
    coverage_output: CoverageJudgeOutput,
    history: list[TurnRecord],
    retry_count: int = 1,
) -> StateUpdateOutput:
    return complete_model(
        llm,
        task_name="state_update",
        prompt=state_update_prompt(
            scene_asset=scene_asset,
            user_profile=user_profile,
            case_card=case_card,
            conversation_state=conversation_state,
            agent_output=agent_output,
            user_output=user_output,
            coverage_output=coverage_output,
            history=[turn.model_dump(mode="json") for turn in history],
            output_schema=schema_text(StateUpdateOutput),
        ),
        model_type=StateUpdateOutput,
        retry_count=retry_count,
    )


def update_conversation_state(
    state: ConversationState,
    *,
    case_card: CaseCard,
    user_output: UserTurnOutput,
    coverage_output: CoverageJudgeOutput,
    state_update: StateUpdateOutput | None = None,
) -> tuple[ConversationState, StateTransitionRecord]:
    state_update = state_update or StateUpdateOutput(
        patience_delta=user_output.patience - state.patience,
        emotion=user_output.emotion,
        willingness=user_output.state_delta.willingness,
        should_end=user_output.should_end_candidate,
        end_reason=user_output.end_reason_candidate,
        rationale="fallback deterministic state merge",
    )
    triggered = list(state.triggered_targets)
    for item in coverage_output.triggered_targets:
        if item.label not in triggered:
            triggered.append(item.label)

    understood = list(state.understood_facts)
    for fact in user_output.state_delta.understood_facts:
        if fact not in understood:
            understood.append(fact)

    objections = list(state.active_objections)
    for objection in user_output.state_delta.new_objections:
        if objection not in objections:
            objections.append(objection)

    risk_flags = list(state.risk_flags)
    for risk in coverage_output.risk_flags:
        if risk not in risk_flags:
            risk_flags.append(risk)

    state_events = list(state.state_events)
    for event in state_update.new_state_events:
        if event not in state_events:
            state_events.append(event)

    next_turn_index = state.turn_index + 1
    should_end = user_output.should_end_candidate or state_update.should_end
    end_reason = (
        user_output.end_reason_candidate
        or state_update.end_reason
        if should_end
        else ""
    )

    if next_turn_index >= case_card.stop_policy.max_turns:
        should_end = True
        end_reason = end_reason or "max_turns"

    if not coverage_output.missing_targets:
        should_end = True
        end_reason = end_reason or "coverage_complete"

    next_state = ConversationState(
        turn_index=next_turn_index,
        emotion=state_update.emotion or user_output.emotion,
        patience=_clamp(state.patience + state_update.patience_delta),
        trust=_clamp(state.trust + state_update.trust_delta),
        suspicion=_clamp(state.suspicion + state_update.suspicion_delta),
        urgency=_clamp(state.urgency + state_update.urgency_delta),
        understanding=_clamp(state.understanding + state_update.understanding_delta),
        understood_facts=understood,
        active_objections=objections,
        triggered_targets=triggered,
        risk_flags=risk_flags,
        state_events=state_events,
        willingness=state_update.willingness or user_output.state_delta.willingness or state.willingness,
        should_end=should_end,
        end_reason=end_reason,
    )
    transition = StateTransitionRecord(
        turn_index=next_turn_index,
        previous_state=_snapshot(state),
        update=state_update,
        next_state=_snapshot(next_state),
        user_intent=user_output.user_intent,
        rationale=state_update.rationale,
    )
    return next_state, transition


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _snapshot(state: ConversationState) -> StateSnapshot:
    return StateSnapshot(
        turn_index=state.turn_index,
        emotion=state.emotion,
        patience=state.patience,
        trust=state.trust,
        suspicion=state.suspicion,
        urgency=state.urgency,
        understanding=state.understanding,
        willingness=state.willingness,
    )
