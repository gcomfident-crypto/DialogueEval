from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from dialogue_simulator.agent_model import generate_agent_turn
from dialogue_simulator.asset_generator import (
    generate_case_cards,
    generate_case_generation_plan,
    generate_coverage_matrix,
    generate_coverage_plan,
    generate_coverage_taxonomy,
    generate_scene_asset,
    generate_scoring_rubric,
    generate_user_profiles,
    materialize_eval_standard,
    write_asset_generation_report,
    write_coverage_gap_report,
)
from dialogue_simulator.coverage_judge import judge_coverage
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.schemas import (
    AssetGenerationState,
    BusinessConfig,
    CaseCardCollection,
    CaseGenerationPlan,
    ConversationGraphState,
    ConversationResult,
    ConversationState,
    CoverageMatrix,
    CoverageJudgeOutput,
    CoveragePlan,
    CoverageTaxonomy,
    GenerationPolicy,
    GeneratedAssets,
    SceneAsset,
    ScoringRubric,
    TurnRecord,
    UserProfile,
    UserProfileCollection,
)
from dialogue_simulator.state_updater import generate_state_update, update_conversation_state
from dialogue_simulator.storage import (
    file_sha256,
    load_model,
    read_structured_file,
    read_text,
    write_model,
)
from dialogue_simulator.tracing import trace_span
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

        with trace_span(
            "asset.load_eval_standard",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "load_eval_standard",
                "dialogue_eval.eval_standard_path": str(eval_standard_path),
            },
            input_data={
                "eval_standard_path": eval_standard_path,
                "business_config_path": business_config_path,
                "generation_policy_path": generation_policy_path,
            },
        ) as span:
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

            result = {
                "raw_eval_standard_text": raw_eval_standard_text,
                "eval_standard_text": eval_standard_text,
                "materialized_eval_standard": materialized_eval_standard,
                "input_hash": file_sha256(eval_standard_path),
                "business_config": business_config,
                "generation_policy": generation_policy,
            }
            span.set_output(
                {
                    "input_hash": result["input_hash"],
                    "raw_length": len(raw_eval_standard_text),
                    "materialized": materialized_eval_standard is not None,
                    "materialized_length": len(eval_standard_text),
                }
            )
            return result

    def generate_scene_brief(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_scene_brief",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_scene_brief",
                "dialogue_eval.input_hash": state["input_hash"],
            },
            input_data={"eval_standard_text": state["eval_standard_text"]},
        ) as span:
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
            result = {"scene_asset": scene_asset.model_copy(update={"generation_metadata": metadata})}
            span.set_output(
                {
                    "scene_id": result["scene_asset"].scene_id,
                    "scene_name": result["scene_asset"].scene_name,
                }
            )
            return result

    def generate_coverage(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_coverage_plan",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_coverage_plan",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            coverage_plan = generate_coverage_plan(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": coverage_plan.scene_id,
                    "coverage_label_count": len(coverage_plan.coverage_labels),
                }
            )
            return {"coverage_plan": coverage_plan}

    def generate_profiles(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_user_profiles",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_user_profiles",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            user_profiles = generate_user_profiles(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": user_profiles.scene_id,
                    "profile_count": len(user_profiles.profiles),
                }
            )
            return {"user_profiles": user_profiles}

    def generate_rubric(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_scoring_rubric",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_scoring_rubric",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            scoring_rubric = generate_scoring_rubric(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                input_hash=state["input_hash"],
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": scoring_rubric.scene_id,
                    "dimension_count": len(scoring_rubric.dimensions),
                    "total_score": scoring_rubric.total_score,
                    "pass_threshold": scoring_rubric.pass_threshold,
                }
            )
            return {"scoring_rubric": scoring_rubric}

    def generate_taxonomy(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_coverage_taxonomy",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_coverage_taxonomy",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            taxonomy = generate_coverage_taxonomy(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                scoring_rubric=state["scoring_rubric"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": taxonomy.scene_id,
                    "task_target_count": len(taxonomy.task_targets),
                    "flow_branch_count": len(taxonomy.flow_branches),
                    "user_behavior_count": len(taxonomy.user_behaviors),
                    "risk_probe_count": len(taxonomy.risk_probes),
                    "dynamic_state_path_count": len(taxonomy.dynamic_state_paths),
                }
            )
            return {"coverage_taxonomy": taxonomy}

    def generate_matrix(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_coverage_matrix",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_coverage_matrix",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            matrix = generate_coverage_matrix(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                coverage_taxonomy=state["coverage_taxonomy"],
                scoring_rubric=state["scoring_rubric"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": matrix.scene_id,
                    "row_count": len(matrix.rows),
                    "planned_case_count": sum(row.case_count for row in matrix.rows),
                }
            )
            return {"coverage_matrix": matrix}

    def generate_case_plan(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_case_generation_plan",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_case_generation_plan",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            plan = generate_case_generation_plan(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                coverage_taxonomy=state["coverage_taxonomy"],
                coverage_matrix=state["coverage_matrix"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
            )
            span.set_output(
                {
                    "scene_id": plan.scene_id,
                    "target_case_count": plan.target_case_count,
                    "allocated_case_count": sum(item.case_count for item in plan.allocations),
                }
            )
            return {"case_generation_plan": plan}

    def generate_cases(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.generate_case_cards",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "generate_case_cards",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            policy = state["generation_policy"]
            case_cards = generate_case_cards(
                llm,
                eval_standard_text=state["eval_standard_text"],
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                user_profiles=state["user_profiles"],
                generation_policy=policy,
                retry_count=policy.validation.retry_on_schema_error,
                coverage_taxonomy=state.get("coverage_taxonomy"),
                coverage_matrix=state.get("coverage_matrix"),
                case_generation_plan=state.get("case_generation_plan"),
            )
            span.set_output(
                {
                    "scene_id": case_cards.scene_id,
                    "case_count": len(case_cards.cases),
                }
            )
            return {"case_cards": case_cards}

    def validate_assets(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.validate_assets",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "validate_assets",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
            },
        ) as span:
            GeneratedAssets(
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                coverage_taxonomy=state.get("coverage_taxonomy"),
                coverage_matrix=state.get("coverage_matrix"),
                case_generation_plan=state.get("case_generation_plan"),
                user_profiles=state["user_profiles"],
                case_cards=state["case_cards"],
                scoring_rubric=state["scoring_rubric"],
            )
            span.set_output({"valid": True})
            return {}

    def persist_assets(state: AssetGenerationState) -> dict[str, Any]:
        with trace_span(
            "asset.persist_assets",
            attributes={
                "dialogue_eval.graph": "asset_generation",
                "dialogue_eval.node": "persist_assets",
                "dialogue_eval.scene_id": state["scene_asset"].scene_id,
                "dialogue_eval.input_hash": state["input_hash"],
            },
        ) as span:
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
            if state.get("coverage_taxonomy") is not None:
                write_model(asset_dir / "coverage_taxonomy.yaml", state["coverage_taxonomy"])
            if state.get("coverage_matrix") is not None:
                write_model(asset_dir / "coverage_matrix.yaml", state["coverage_matrix"])
            if state.get("case_generation_plan") is not None:
                write_model(asset_dir / "case_generation_plan.yaml", state["case_generation_plan"])
            write_model(asset_dir / "user_profiles.yaml", state["user_profiles"])
            write_model(asset_dir / "case_cards.yaml", state["case_cards"])
            write_model(asset_dir / "scoring_rubric.yaml", state["scoring_rubric"])
            write_coverage_gap_report(
                asset_dir,
                coverage_plan=state["coverage_plan"],
                coverage_taxonomy=state.get("coverage_taxonomy"),
                coverage_matrix=state.get("coverage_matrix"),
                case_generation_plan=state.get("case_generation_plan"),
                case_cards=state["case_cards"],
            )
            materialized_eval_standard = state.get("materialized_eval_standard")
            if materialized_eval_standard is not None:
                (asset_dir / "materialized_eval_standard.md").write_text(
                    materialized_eval_standard.materialized_text.rstrip() + "\n",
                    encoding="utf-8",
                )
                write_model(asset_dir / "variable_assignments.yaml", materialized_eval_standard)
            write_asset_generation_report(asset_dir, state["scene_asset"])
            result = {"asset_dir": str(asset_dir)}
            span.set_output(
                {
                    "asset_dir": str(asset_dir),
                    "reused_existing_asset": existing_asset_dir is not None,
                }
            )
            return result

    nodes = [
        ("load_eval_standard", load_eval_standard),
        ("generate_scene_brief", generate_scene_brief),
        ("generate_coverage_plan", generate_coverage),
        ("generate_scoring_rubric", generate_rubric),
        ("generate_coverage_taxonomy", generate_taxonomy),
        ("generate_user_profiles", generate_profiles),
        ("generate_coverage_matrix", generate_matrix),
        ("generate_case_generation_plan", generate_case_plan),
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
    state_llm: LLMClient | None = None,
):
    retry_count = 1
    state_model = state_llm or user_llm

    def initialize_case(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        initial = case_card.initial_state
        with trace_span(
            "conversation.initialize_case",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "initialize_case",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
                "dialogue_eval.scene_id": case_card.scene_id,
            },
            input_data=case_card,
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            result = {
                "conversation_state": ConversationState(
                    emotion=initial.emotion,
                    patience=initial.patience,
                    trust=initial.trust,
                    suspicion=initial.suspicion,
                    urgency=initial.urgency,
                    understanding=initial.understanding,
                    willingness=initial.willingness,
                ),
                "history": [],
                "state_trace": [],
            }
            span.set_output(result["conversation_state"])
            return result

    def agent_turn(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        with trace_span(
            "conversation.agent_turn",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "agent_turn",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
                "dialogue_eval.turn_index": len(state["history"]) + 1,
            },
            input_data={
                "conversation_state": state["conversation_state"],
                "history": state["history"],
            },
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            agent_output = generate_agent_turn(
                agent_llm,
                scene_asset=state["scene_asset"],
                coverage_plan=state["coverage_plan"],
                case_card=case_card,
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
            span.set_output(
                {
                    "visible_reply": agent_output.visible_reply,
                    "agent_intent": agent_output.agent_intent,
                    "risk_flags": agent_output.risk_flags,
                }
            )
            return {"agent_output": agent_output, "history": history}

    def user_turn(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        profile = _profile_for_case(state)
        with trace_span(
            "conversation.user_turn",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "user_turn",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
                "dialogue_eval.profile_id": profile.profile_id,
                "dialogue_eval.turn_index": len(state["history"]) + 1,
            },
            input_data={
                "conversation_state": state["conversation_state"],
                "history": state["history"],
                "user_profile": profile,
            },
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            user_output = generate_user_turn(
                user_llm,
                scene_asset=state["scene_asset"],
                user_profile=profile,
                case_card=case_card,
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
            span.set_output(
                {
                    "visible_reply": user_output.visible_reply,
                    "user_intent": user_output.user_intent,
                    "emotion": user_output.emotion,
                    "patience": user_output.patience,
                }
            )
            return {"user_output": user_output, "history": history}

    def coverage_node(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        with trace_span(
            "conversation.coverage_judge",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "coverage_judge",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
                "dialogue_eval.turn_count": len(state["history"]),
            },
            input_data={
                "history": state["history"],
                "current_triggered_targets": state["conversation_state"].triggered_targets,
            },
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            coverage_output = judge_coverage(
                judge_llm,
                coverage_plan=state["coverage_plan"],
                scene_asset=state["scene_asset"],
                case_card=case_card,
                history=state["history"],
                current_triggered_targets=state["conversation_state"].triggered_targets,
                retry_count=retry_count,
            )
            span.set_output(
                {
                    "triggered_targets": [
                        item.model_dump(mode="json")
                        for item in coverage_output.triggered_targets
                    ],
                    "missing_targets": coverage_output.missing_targets,
                    "risk_flags": coverage_output.risk_flags,
                }
            )
            return {"coverage_output": coverage_output}

    def state_update(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        with trace_span(
            "conversation.state_update",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "state_update",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
            },
            input_data={
                "conversation_state": state["conversation_state"],
                "user_output": state["user_output"],
                "coverage_output": state["coverage_output"],
                "history": state["history"],
            },
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            profile = _profile_for_case(state)
            state_update_output = generate_state_update(
                state_model,
                scene_asset=state["scene_asset"],
                user_profile=profile,
                case_card=case_card,
                conversation_state=state["conversation_state"],
                agent_output=state["agent_output"],
                user_output=state["user_output"],
                coverage_output=state["coverage_output"],
                history=state["history"],
                retry_count=retry_count,
            )
            updated, transition = update_conversation_state(
                state["conversation_state"],
                case_card=case_card,
                user_output=state["user_output"],
                coverage_output=state["coverage_output"],
                state_update=state_update_output,
            )
            state_trace = list(state.get("state_trace") or [])
            state_trace.append(transition)
            span.set_output(
                {
                    "conversation_state": updated,
                    "state_update": state_update_output,
                    "transition": transition,
                }
            )
            return {
                "conversation_state": updated,
                "state_update_output": state_update_output,
                "state_trace": state_trace,
            }

    def finalize_case(state: ConversationGraphState) -> dict[str, Any]:
        case_card = state["case_card"]
        with trace_span(
            "conversation.finalize_case",
            attributes={
                "dialogue_eval.graph": "conversation",
                "dialogue_eval.node": "finalize_case",
                **_conversation_trace_attributes(state),
                "dialogue_eval.run_id": state["run_id"],
                "dialogue_eval.case_id": case_card.case_id,
            },
            input_data={"history": state["history"], "conversation_state": state["conversation_state"]},
            session_id=state["run_id"],
            metadata=_conversation_trace_metadata(state, case_card),
        ) as span:
            conversation_state = state["conversation_state"]
            coverage_output = state.get("coverage_output") or CoverageJudgeOutput()
            triggered = conversation_state.triggered_targets
            missing = [
                target
                for target in case_card.coverage_targets
                if target not in set(triggered)
            ]
            conversation_result = ConversationResult(
                run_id=state["run_id"],
                case_id=case_card.case_id,
                scene_id=case_card.scene_id,
                priority=case_card.priority,
                planned_targets=case_card.coverage_targets,
                triggered_targets=triggered,
                missing_targets=missing,
                coverage_success=not missing,
                turns=state["history"],
                coverage_evidence=coverage_output.triggered_targets,
                risk_flags=conversation_state.risk_flags,
                state_trace=state.get("state_trace") or [],
                end_reason=conversation_state.end_reason or "finished",
            )
            span.set_output(
                {
                    "coverage_success": conversation_result.coverage_success,
                    "missing_targets": conversation_result.missing_targets,
                    "turn_count": len(conversation_result.turns),
                    "risk_flags": conversation_result.risk_flags,
                }
            )
            return {"conversation_result": conversation_result}

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
    if state.get("coverage_taxonomy") is not None:
        state["coverage_taxonomy"] = state["coverage_taxonomy"].model_copy(update={"scene_id": scene_id})
    if state.get("coverage_matrix") is not None:
        state["coverage_matrix"] = state["coverage_matrix"].model_copy(update={"scene_id": scene_id})
    if state.get("case_generation_plan") is not None:
        state["case_generation_plan"] = state["case_generation_plan"].model_copy(update={"scene_id": scene_id})
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


def _conversation_trace_attributes(state: ConversationGraphState) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "dialogue_eval.experiment_id": state.get("experiment_id", ""),
            "dialogue_eval.asset_version_id": state.get("asset_version_id", ""),
        }.items()
        if value
    }


def _conversation_trace_metadata(
    state: ConversationGraphState,
    case_card,
) -> dict[str, str]:
    return {
        "experiment_id": state.get("experiment_id", ""),
        "asset_version_id": state.get("asset_version_id", ""),
        "run_id": state.get("run_id", ""),
        "case_id": case_card.case_id,
        "scene_id": case_card.scene_id,
    }


def load_generated_assets(asset_dir: str | Path) -> GeneratedAssets:
    path = Path(asset_dir)
    coverage_taxonomy = (
        load_model(path / "coverage_taxonomy.yaml", CoverageTaxonomy)
        if (path / "coverage_taxonomy.yaml").is_file()
        else None
    )
    coverage_matrix = (
        load_model(path / "coverage_matrix.yaml", CoverageMatrix)
        if (path / "coverage_matrix.yaml").is_file()
        else None
    )
    case_generation_plan = (
        load_model(path / "case_generation_plan.yaml", CaseGenerationPlan)
        if (path / "case_generation_plan.yaml").is_file()
        else None
    )
    return GeneratedAssets(
        scene_asset=load_model(path / "scene_asset.yaml", SceneAsset),
        coverage_plan=load_model(path / "coverage_plan.yaml", CoveragePlan),
        coverage_taxonomy=coverage_taxonomy,
        coverage_matrix=coverage_matrix,
        case_generation_plan=case_generation_plan,
        user_profiles=load_model(
            path / "user_profiles.yaml",
            UserProfileCollection,
        ),
        case_cards=load_model(path / "case_cards.yaml", CaseCardCollection),
        scoring_rubric=load_model(path / "scoring_rubric.yaml", ScoringRubric),
    )
