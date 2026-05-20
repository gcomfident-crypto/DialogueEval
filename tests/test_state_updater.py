from dialogue_simulator.schemas import (
    CaseCard,
    ConversationState,
    CoverageEvidence,
    CoverageJudgeOutput,
    StateUpdateOutput,
    UserStateDelta,
    UserTurnOutput,
)
from dialogue_simulator.state_updater import update_conversation_state


def _case_card() -> CaseCard:
    return CaseCard(
        case_id="case_001",
        scene_id="scene_001",
        case_name="测试 case",
        profile_id="profile_001",
        coverage_targets=["natural_conversation_style"],
    )


def _coverage_complete() -> CoverageJudgeOutput:
    return CoverageJudgeOutput(
        triggered_targets=[
            CoverageEvidence(
                label="natural_conversation_style",
                confidence=1.0,
                evidence="客服表达自然。",
                speaker="agent",
            )
        ],
        missing_targets=[],
    )


def _state_update(**overrides) -> StateUpdateOutput:
    data = {
        "emotion": "neutral",
        "willingness": "high",
        "rationale": "test",
    }
    data.update(overrides)
    return StateUpdateOutput(**data)


def _user_turn(text: str, **overrides) -> UserTurnOutput:
    data = {
        "visible_reply": text,
        "user_intent": "确认信息",
        "emotion": "neutral",
        "patience": 80,
        "state_delta": UserStateDelta(willingness="high"),
    }
    data.update(overrides)
    return UserTurnOutput(**data)


def test_coverage_complete_does_not_end_when_user_still_has_question() -> None:
    next_state, _ = update_conversation_state(
        ConversationState(),
        case_card=_case_card(),
        user_output=_user_turn(
            "好的，那我先确认一下，这个奖励到账时间您大概什么时候能查清楚？",
            user_intent="确认奖励规则并追问到账时间",
        ),
        coverage_output=_coverage_complete(),
        state_update=_state_update(next_user_intent_hint="等待客服回答奖励到账时间"),
    )

    assert next_state.should_end is False
    assert next_state.end_reason == ""


def test_coverage_complete_can_end_after_user_confirmation() -> None:
    next_state, _ = update_conversation_state(
        ConversationState(),
        case_card=_case_card(),
        user_output=_user_turn("好的，我知道了，今天可以开始配送。"),
        coverage_output=_coverage_complete(),
        state_update=_state_update(),
    )

    assert next_state.should_end is True
    assert next_state.end_reason == "coverage_complete"


def test_explicit_user_end_still_takes_priority() -> None:
    next_state, _ = update_conversation_state(
        ConversationState(),
        case_card=_case_card(),
        user_output=_user_turn(
            "不用说了，我挂了。",
            should_end_candidate=True,
            end_reason_candidate="用户要求挂断",
        ),
        coverage_output=_coverage_complete(),
        state_update=_state_update(),
    )

    assert next_state.should_end is True
    assert next_state.end_reason == "用户要求挂断"
