from __future__ import annotations

from dialogue_simulator.schemas import (
    CaseCard,
    ConversationState,
    CoverageJudgeOutput,
    UserTurnOutput,
)


def update_conversation_state(
    state: ConversationState,
    *,
    case_card: CaseCard,
    user_output: UserTurnOutput,
    coverage_output: CoverageJudgeOutput,
) -> ConversationState:
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

    next_turn_index = state.turn_index + 1
    should_end = user_output.should_end_candidate
    end_reason = user_output.end_reason_candidate if should_end else ""

    if next_turn_index >= case_card.stop_policy.max_turns:
        should_end = True
        end_reason = end_reason or "max_turns"

    if not coverage_output.missing_targets:
        should_end = True
        end_reason = end_reason or "coverage_complete"

    return ConversationState(
        turn_index=next_turn_index,
        emotion=user_output.emotion,
        patience=max(0, min(100, user_output.patience)),
        understood_facts=understood,
        active_objections=objections,
        triggered_targets=triggered,
        risk_flags=risk_flags,
        willingness=user_output.state_delta.willingness or state.willingness,
        should_end=should_end,
        end_reason=end_reason,
    )
