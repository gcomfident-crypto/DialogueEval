from __future__ import annotations

from typing import Any, Callable

from dialogue_simulator.evaluator import aggregate_case_evaluation, evaluate_case
from dialogue_simulator.llm_client import LLMClient
from dialogue_simulator.schemas import BusinessConfig, EvaluationGraphState


try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ModuleNotFoundError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class EvaluationSequentialGraph:
    def __init__(self, nodes: list[Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._nodes = nodes

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for node in self._nodes:
            current.update(node(current))
        return current


def build_evaluation_graph(*, evaluator_llm: LLMClient):
    retry_count = 1

    def evaluate_dimensions(state: EvaluationGraphState) -> dict[str, Any]:
        draft = evaluate_case(
            evaluator_llm,
            eval_standard_text=state.get("eval_standard_text", ""),
            scene_asset=state["scene_asset"],
            coverage_plan=state["coverage_plan"],
            scoring_rubric=state["scoring_rubric"],
            conversation_result=state["conversation_result"],
            business_config=state.get("business_config") or BusinessConfig(),
            retry_count=retry_count,
        )
        return {"evaluation_draft": draft}

    def aggregate_score(state: EvaluationGraphState) -> dict[str, Any]:
        result = aggregate_case_evaluation(
            scoring_rubric=state["scoring_rubric"],
            conversation_result=state["conversation_result"],
            draft=state["evaluation_draft"],
        )
        return {"case_evaluation": result}

    nodes = [
        ("evaluate_dimensions", evaluate_dimensions),
        ("aggregate_score", aggregate_score),
    ]

    if not LANGGRAPH_AVAILABLE:
        return EvaluationSequentialGraph([node for _, node in nodes])

    workflow = StateGraph(EvaluationGraphState)
    workflow.add_node("evaluate_dimensions", evaluate_dimensions)
    workflow.add_node("aggregate_score", aggregate_score)
    workflow.set_entry_point("evaluate_dimensions")
    workflow.add_edge("evaluate_dimensions", "aggregate_score")
    workflow.add_edge("aggregate_score", END)
    return workflow.compile()
