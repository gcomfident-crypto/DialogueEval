from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from dialogue_simulator.agent_model import generate_agent_turn
from dialogue_simulator.asset_generator import (
    generate_case_cards,
    generate_coverage_plan,
    generate_scene_asset,
    generate_scoring_rubric,
    generate_user_profiles,
    materialize_eval_standard,
    write_asset_generation_report,
)
from dialogue_simulator.coverage_judge import judge_coverage
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.schemas import (
    AssetGenerationState,
    BusinessConfig,
    CaseCardCollection,
    ConversationGraphState,
    ConversationResult,
    ConversationState,
    CoverageJudgeOutput,
    CoveragePlan,
    GenerationPolicy,
    GeneratedAssets,
    SceneAsset,
    ScoringRubric,
    TurnRecord,
    UserProfile,
    UserProfileCollection,
)
from dialogue_simulator.state_updater import update_conversation_state
from dialogue_simulator.storage import (
    file_sha256,
    load_model,
    read_structured_file,
    read_text,
    write_model,
)
from dialogue_simulator.user_model import generate_user_turn


try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ModuleNotFoundError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class SequentialGraph:
    def __init__(self, nodes: list[Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._nodes = nodes

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for node in self._nodes:
            current.update(node(current))
        return current


def build_asset_generation_graph(
    llm: LLMClient,
    *,
    output_root: str | Path,
):
    retry_count = 1

    def load_eval_standard(state: AssetGenerationState) -> dict[str, Any]:
        eval_standard_path = state["eval_standard_path"]
        business_config_path = state.get("business_config_path")
        generation_policy_path = state.get("generation_policy_path")

        business_config = (
            BusinessConfig.model_validate(read_structured_file(business_config_path))
            if business_config_path
            else BusinessConfig()
        )
        generation_policy = (
            GenerationPolicy.model_validate(read_structured_file(generation_policy_path))
            if generation_policy_path
            else GenerationPolicy()
        )
        raw_eval_standard_text = read_text(eval_standard_path)
        eval_standard_text = raw_eval_standard_text
        materialized_eval_standard = None
        if generation_policy.variable_materialization.enabled:
            materialized_eval_standard = materialize_eval_standard(
                llm,
                eval_standard_text=raw_eval_standard_text,
                business_config=business_config,
                generation_policy=generation_policy,
                retry_count=generation_policy.validation.retry_on_schema_error,
            )
            eval_standard_text = materialized_eval_standard.materialized_text

        return {
            "raw_eval_standard_text": raw_eval_standard_text,
            "eval_standard_text": eval_standard_text,
            "materialized_eval_standard": materialized_eval_standard,
            "input_hash": file_sha256(eval_standard_path),
            "business_config": business_config,
            "generation_policy": generation_policy,
        }

    def generate_scene_brief(state: AssetGenerationState) -> dict[str, Any]:
        policy = state["generation_policy"]
        scene_asset = generate_scene_asset(
            llm,
            eval_standard_text=state["eval_standard_text"],
            eval_standard_path=state["eval_standard_path"],
            business_config=state["business_config"],
            input_hash=state["input_hash"],
            retry_count=policy.validation.retry_on_schema_error,
        )
        metadata = scene_asset.generation_metadata.model_copy(
            update={"asset_version": policy.asset_version}
        )
        return {"scene_asset": scene_asset.model_copy(update={"generation_metadata": metadata})}

    def generate_coverage(state: AssetGenerationState) -> dict[str, Any]:
        policy = state["generation_policy"]
        return {
            "coverage_plan": generate_coverage_plan(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
        }

    def generate_profiles(state: AssetGenerationState) -> dict[str, Any]:
        policy = state["generation_policy"]
        return {
            "user_profiles": generate_user_profiles(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
        }

    def generate_rubric(state: AssetGenerationState) -> dict[str, Any]:
        policy = state["generation_policy"]
        return {
            "scoring_rubric": generate_scoring_rubric(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                input_hash=state["input_hash"],
                retry_count=policy.validation.retry_on_schema_error,
            )
        }

    def generate_cases(state: AssetGenerationState) -> dict[str, Any]:
        policy = state["generation_policy"]
        return {
            "case_cards": generate_case_cards(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                user_profiles=state["user_profiles"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
        }

    def validate_assets(state: AssetGenerationState) -> dict[str, Any]:
        GeneratedAssets(
            scene_asset=state["scene_asset"],
            coverage_plan=state["coverage_plan"],
            user_profiles=state["user_profiles"],
            case_cards=state["case_cards"],
            scoring_rubric=state["scoring_rubric"],
        )
        return {}

    def persist_assets(state: AssetGenerationState) -> dict[str, Any]:
        root = Path(output_root)
        existing_asset_dir = _find_asset_dir_by_input_hash(root, state["input_hash"])
        scene_id = (
            _load_existing_scene_id(existing_asset_dir)
            if existing_asset_dir is not None
            else state["scene_asset"].scene_id
        )
        _normalize_scene_ids(state, scene_id)

        asset_dir = existing_asset_dir or root / scene_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        write_model(asset_dir / "scene_asset.yaml", state["scene_asset"])
        write_model(asset_dir / "coverage_plan.yaml", state["coverage_plan"])
        write_model(asset_dir / "user_profiles.yaml", state["user_profiles"])
        write_model(asset_dir / "case_cards.yaml", state["case_cards"])
        write_model(asset_dir / "scoring_rubric.yaml", state["scoring_rubric"])
        materialized_eval_standard = state.get("materialized_eval_standard")
        if materialized_eval_standard is not None:
            (asset_dir / "materialized_eval_standard.md").write_text(
                materialized_eval_standard.materialized_text.rstrip() + "\n",
                encoding="utf-8",
            )
            write_model(asset_dir / "variable_assignments.yaml", materialized_eval_standard)
        write_asset_generation_report(asset_dir, state["scene_asset"])
        return {"asset_dir": str(asset_dir)}

    nodes = [
        ("load_eval_standard", load_eval_standard),
        ("generate_scene_brief", generate_scene_brief),
        ("generate_coverage_plan", generate_coverage),
        ("generate_scoring_rubric", generate_rubric),
        ("generate_user_profiles", generate_profiles),
        ("generate_case_cards", generate_cases),
        ("validate_assets", validate_assets),
        ("persist_assets", persist_assets),
    ]
    return _compile_graph(AssetGenerationState, nodes)


def build_conversation_graph(
    *,
    agent_llm: LLMClient,
    user_llm: LLMClient,
    judge_llm: LLMClient,
):
    retry_count = 1

    def initialize_case(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        initial = case_card.initial_state
        return {
            "conversation_state": ConversationState(
                emotion=initial.emotion,
                patience=initial.patience,
                willingness=initial.willingness,
            ),
            "history": [],
        }

    def agent_turn(state: ConversationGraphState) -> dict[str, Any]:
        agent_output = generate_agent_turn(
            agent_llm,
            scene_asset=state["scene_asset"],
            coverage_plan=state["coverage_plan"],
            case_card=state["case_card"],
            business_config=state.get("business_config") or BusinessConfig(),
            conversation_state=state["conversation_state"],
            history=state["history"],
            retry_count=retry_count,
        )
        history = list(state["history"])
        history.append(
            TurnRecord(
                role="agent",
                text=agent_output.visible_reply,
                intent=agent_output.agent_intent,
                risk_flags=agent_output.risk_flags,
            )
        )
        return {"agent_output": agent_output, "history": history}

    def user_turn(state: ConversationGraphState) -> dict[str, Any]:
        profile = _profile_for_case(state)
        user_output = generate_user_turn(
            user_llm,
            scene_asset=state["scene_asset"],
            user_profile=profile,
            case_card=state["case_card"],
            conversation_state=state["conversation_state"],
            history=state["history"],
            retry_count=retry_count,
        )
        history = list(state["history"])
        history.append(
            TurnRecord(
                role="user",
                text=user_output.visible_reply,
                intent=user_output.user_intent,
                emotion=user_output.emotion,
                patience=user_output.patience,
            )
        )
        return {"user_output": user_output, "history": history}

    def coverage_node(state: ConversationGraphState) -> dict[str, Any]:
        coverage_output = judge_coverage(
            judge_llm,
            coverage_plan=state["coverage_plan"],
            scene_asset=state["scene_asset"],
            case_card=state["case_card"],
            history=state["history"],
            current_triggered_targets=state["conversation_state"].triggered_targets,
            retry_count=retry_count,
        )
        return {"coverage_output": coverage_output}

    def state_update(state: ConversationGraphState) -> dict[str, Any]:
        updated = update_conversation_state(
            state["conversation_state"],
            case_card=state["case_card"],
            user_output=state["user_output"],
            coverage_output=state["coverage_output"],
        )
        return {"conversation_state": updated}

    def finalize_case(state: ConversationGraphState) -> dict[str, Any]:
        conversation_state = state["conversation_state"]
        coverage_output = state.get("coverage_output") or CoverageJudgeOutput()
        triggered = conversation_state.triggered_targets
        missing = [
            target
            for target in state["case_card"].coverage_targets
            if target not in set(triggered)
        ]
        return {
            "conversation_result": ConversationResult(
                run_id=state["run_id"],
                case_id=state["case_card"].case_id,
                scene_id=state["case_card"].scene_id,
                priority=state["case_card"].priority,
                planned_targets=state["case_card"].coverage_targets,
                triggered_targets=triggered,
                missing_targets=missing,
                coverage_success=not missing,
                turns=state["history"],
                coverage_evidence=coverage_output.triggered_targets,
                risk_flags=conversation_state.risk_flags,
                end_reason=conversation_state.end_reason or "finished",
            )
        }

    if not LANGGRAPH_AVAILABLE:
        return ConversationSequentialGraph(
            initialize_case=initialize_case,
            agent_turn=agent_turn,
            user_turn=user_turn,
            coverage_node=coverage_node,
            state_update=state_update,
            finalize_case=finalize_case,
        )

    workflow = StateGraph(ConversationGraphState)
    workflow.add_node("initialize_case", initialize_case)
    workflow.add_node("agent_turn", agent_turn)
    workflow.add_node("user_turn", user_turn)
    workflow.add_node("coverage_judge", coverage_node)
    workflow.add_node("state_update", state_update)
    workflow.add_node("finalize_case", finalize_case)
    workflow.set_entry_point("initialize_case")
    workflow.add_edge("initialize_case", "agent_turn")
    workflow.add_edge("agent_turn", "user_turn")
    workflow.add_edge("user_turn", "coverage_judge")
    workflow.add_edge("coverage_judge", "state_update")
    workflow.add_conditional_edges(
        "state_update",
        lambda state: "finalize_case"
        if state["conversation_state"].should_end
        else "agent_turn",
        {"agent_turn": "agent_turn", "finalize_case": "finalize_case"},
    )
    workflow.add_edge("finalize_case", END)
    return workflow.compile()


class ConversationSequentialGraph:
    def __init__(
        self,
        *,
        initialize_case: Callable[[dict[str, Any]], dict[str, Any]],
        agent_turn: Callable[[dict[str, Any]], dict[str, Any]],
        user_turn: Callable[[dict[str, Any]], dict[str, Any]],
        coverage_node: Callable[[dict[str, Any]], dict[str, Any]],
        state_update: Callable[[dict[str, Any]], dict[str, Any]],
        finalize_case: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._initialize_case = initialize_case
        self._agent_turn = agent_turn
        self._user_turn = user_turn
        self._coverage_node = coverage_node
        self._state_update = state_update
        self._finalize_case = finalize_case

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        current.update(self._initialize_case(current))
        while True:
            current.update(self._agent_turn(current))
            current.update(self._user_turn(current))
            current.update(self._coverage_node(current))
            current.update(self._state_update(current))
            if current["conversation_state"].should_end:
                break
        current.update(self._finalize_case(current))
        return current


def _profile_for_case(state: ConversationGraphState) -> UserProfile:
    case_card = state["case_card"]
    for profile in state["user_profiles"].profiles:
        if profile.profile_id == case_card.profile_id:
            return profile
    raise ValueError(f"profile_id not found for case {case_card.case_id}")


def _compile_graph(state_type: type, nodes: list[tuple[str, Callable]]):
    if not LANGGRAPH_AVAILABLE:
        return SequentialGraph([node for _, node in nodes])

    workflow = StateGraph(state_type)
    previous_name = ""
    for name, node in nodes:
        workflow.add_node(name, node)
        if previous_name:
            workflow.add_edge(previous_name, name)
        previous_name = name
    workflow.set_entry_point(nodes[0][0])
    workflow.add_edge(nodes[-1][0], END)
    return workflow.compile()


def _find_asset_dir_by_input_hash(output_root: Path, input_hash: str) -> Path | None:
    if not input_hash or not output_root.exists():
        return None
    for scene_file in sorted(output_root.glob("*/scene_asset.yaml")):
        try:
            scene_asset = load_model(scene_file, SceneAsset)
        except Exception:
            continue
        if scene_asset.generation_metadata.input_hash == input_hash:
            return scene_file.parent
    return None


def _load_existing_scene_id(asset_dir: Path | None) -> str:
    if asset_dir is None:
        return ""
    try:
        scene_asset = load_model(asset_dir / "scene_asset.yaml", SceneAsset)
    except Exception:
        return asset_dir.name
    return scene_asset.scene_id or asset_dir.name


def _normalize_scene_ids(state: AssetGenerationState, scene_id: str) -> None:
    state["scene_asset"] = state["scene_asset"].model_copy(update={"scene_id": scene_id})
    state["coverage_plan"] = state["coverage_plan"].model_copy(update={"scene_id": scene_id})
    state["user_profiles"] = state["user_profiles"].model_copy(update={"scene_id": scene_id})
    state["case_cards"] = state["case_cards"].model_copy(
        update={
            "scene_id": scene_id,
            "cases": [
                case_card.model_copy(update={"scene_id": scene_id})
                for case_card in state["case_cards"].cases
            ],
        }
    )
    state["scoring_rubric"] = state["scoring_rubric"].model_copy(
        update={"scene_id": scene_id}
    )


def load_generated_assets(asset_dir: str | Path) -> GeneratedAssets:
    path = Path(asset_dir)
    return GeneratedAssets(
        scene_asset=load_model(path / "scene_asset.yaml", SceneAsset),
        coverage_plan=load_model(path / "coverage_plan.yaml", CoveragePlan),
        user_profiles=load_model(
            path / "user_profiles.yaml",
            UserProfileCollection,
        ),
        case_cards=load_model(path / "case_cards.yaml", CaseCardCollection),
        scoring_rubric=load_model(path / "scoring_rubric.yaml", ScoringRubric),
    )
