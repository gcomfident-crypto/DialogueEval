from __future__ import annotations

from typing import Any


def build_agent_runtime_context(
    *,
    scene_asset: Any,
    coverage_plan: Any,
    case_card: Any,
    business_config: Any,
    conversation_state: Any,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    case = _jsonable(case_card)
    state = _jsonable(conversation_state)
    targets = list(case.get("coverage_targets", []))
    triggered = list(state.get("triggered_targets", []))

    return {
        "scene": _scene_brief(scene_asset),
        "agent_instruction": _scene_field(scene_asset, "agent_instruction", {}),
        "knowledge_items": _knowledge_items(scene_asset),
        "compliance_rules": _compliance_rules(scene_asset),
        "case": _pick(
            case,
            "case_id",
            "case_name",
            "priority",
            "profile_id",
            "stop_policy",
        ),
        "coverage_targets": _target_definitions(coverage_plan, targets),
        "business_config": _jsonable(business_config),
        "conversation_state": state,
        "progress": {
            "turn_index": state.get("turn_index"),
            "triggered_targets": triggered,
            "remaining_targets": [target for target in targets if target not in set(triggered)],
        },
        "history": _recent_history(history, max_turns=_history_window(case)),
    }


def build_user_runtime_context(
    *,
    scene_asset: Any,
    user_profile: Any,
    case_card: Any,
    conversation_state: Any,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    case = _jsonable(case_card)
    return {
        "scene": _pick(
            _scene_brief(scene_asset),
            "scene_name",
            "business_goal",
            "agent_role",
            "user_role",
            "success_definition",
        ),
        "user_profile": _jsonable(user_profile),
        "hidden_user_context": case.get("hidden_user_context", {}),
        "initial_state": case.get("initial_state", {}),
        "behavior_policy": case.get("behavior_policy", {}),
        "stop_policy": case.get("stop_policy", {}),
        "conversation_state": _jsonable(conversation_state),
        "latest_agent_message": _latest_message(history, role="agent"),
        "history": _recent_history(history, max_turns=_history_window(case)),
    }


def build_judge_runtime_context(
    *,
    coverage_plan: Any,
    scene_asset: Any,
    case_card: Any,
    history: list[dict[str, Any]],
    current_triggered_targets: list[str],
) -> dict[str, Any]:
    case = _jsonable(case_card)
    targets = list(case.get("coverage_targets", []))
    triggered = list(current_triggered_targets)
    return {
        "scene": _scene_brief(scene_asset),
        "case": _pick(case, "case_id", "case_name", "priority", "profile_id"),
        "coverage_targets": _target_definitions(coverage_plan, targets),
        "current_triggered_targets": triggered,
        "remaining_targets": [target for target in targets if target not in set(triggered)],
        "compliance_rules": _compliance_rules(scene_asset),
        "history": _jsonable(history),
    }


def build_evaluation_runtime_context(
    *,
    eval_standard_text: str,
    scene_asset: Any,
    coverage_plan: Any,
    scoring_rubric: Any,
    conversation_result: Any,
    business_config: Any,
) -> dict[str, Any]:
    result = _jsonable(conversation_result)
    return {
        "eval_standard_text": eval_standard_text,
        "scene": _scene_brief(scene_asset),
        "target_definitions": _target_definitions(
            coverage_plan,
            list(result.get("planned_targets", [])),
        ),
        "scoring_rubric": _jsonable(scoring_rubric),
        "business_config": _jsonable(business_config),
        "conversation_result": result,
    }


def _scene_brief(scene_asset: Any) -> dict[str, Any]:
    return _pick(
        _jsonable(scene_asset),
        "scene_id",
        "scene_name",
        "business_goal",
        "agent_role",
        "user_role",
        "success_definition",
    )


def _scene_field(scene_asset: Any, key: str, default: Any) -> Any:
    return _jsonable(scene_asset).get(key, default)


def _knowledge_items(scene_asset: Any) -> list[dict[str, Any]]:
    return [
        _pick(item, "id", "name", "content", "when_to_use", "business_variables")
        for item in _jsonable(scene_asset).get("knowledge_items", [])
    ]


def _compliance_rules(scene_asset: Any) -> list[dict[str, Any]]:
    return [
        _pick(item, "id", "rule", "severity", "negative_examples_description")
        for item in _jsonable(scene_asset).get("compliance_rules", [])
    ]


def _target_definitions(coverage_plan: Any, targets: list[str]) -> list[dict[str, Any]]:
    labels = _coverage_label_map(coverage_plan)
    return [
        labels.get(target, {"label": target, "definition": "", "evidence_required": ""})
        for target in targets
    ]


def _coverage_label_map(coverage_plan: Any) -> dict[str, dict[str, Any]]:
    items = _jsonable(coverage_plan).get("coverage_labels", [])
    return {
        str(item.get("label")): _pick(
            item,
            "label",
            "name",
            "definition",
            "evidence_required",
            "priority",
            "positive_evidence_examples_description",
            "negative_evidence_examples_description",
        )
        for item in items
        if item.get("label")
    }


def _recent_history(history: list[dict[str, Any]], *, max_turns: int) -> list[dict[str, Any]]:
    items = _jsonable(history)
    if max_turns <= 0 or len(items) <= max_turns:
        return items
    return items[-max_turns:]


def _latest_message(history: list[dict[str, Any]], *, role: str) -> str:
    for item in reversed(_jsonable(history)):
        if item.get("role") == role:
            return str(item.get("text", ""))
    return ""


def _history_window(case: dict[str, Any]) -> int:
    stop_policy = case.get("stop_policy", {})
    max_turns = stop_policy.get("max_turns", 12) if isinstance(stop_policy, dict) else 12
    try:
        return max(4, int(max_turns) * 2)
    except (TypeError, ValueError):
        return 24


def _pick(value: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value[key] for key in keys if key in value}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
