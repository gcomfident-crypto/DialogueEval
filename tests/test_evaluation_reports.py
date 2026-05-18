from pathlib import Path

from dialogue_simulator.evaluator import aggregate_case_evaluation
from dialogue_simulator.evaluation_graph import build_evaluation_graph
from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.report_exporter import export_evaluation_reports
from dialogue_simulator.schemas import (
    BusinessConfig,
    CaseEvaluationDraft,
    CheckItemEvaluation,
    ConversationResult,
    EvidenceQuote,
    ScoringCheckItem,
    ScoringDimension,
    ScoringRubric,
    TurnRecord,
)


def test_evaluation_graph_writes_case_and_total_reports(tmp_path: Path) -> None:
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 合格线：80分。\n", encoding="utf-8")

    asset_graph = build_asset_generation_graph(FakeLLMClient(), output_root=tmp_path / "assets")
    asset_result = asset_graph.invoke({"eval_standard_path": str(eval_standard)})
    assets = load_generated_assets(asset_result["asset_dir"])

    conversation = ConversationResult(
        run_id="run-1",
        case_id="CASE_001",
        scene_id=assets.scene_asset.scene_id,
        priority="P0",
        planned_targets=["C001"],
        triggered_targets=["C001"],
        missing_targets=[],
        coverage_success=True,
        turns=[TurnRecord(role="agent", text="您好，我简短说明这次外呼的核心事项。")],
        end_reason="coverage_complete",
    )

    graph = build_evaluation_graph(evaluator_llm=FakeLLMClient())
    result = graph.invoke(
        {
            "run_id": conversation.run_id,
            "scene_asset": assets.scene_asset,
            "coverage_plan": assets.coverage_plan,
            "scoring_rubric": assets.scoring_rubric,
            "conversation_result": conversation,
            "eval_standard_text": eval_standard.read_text(encoding="utf-8"),
            "business_config": BusinessConfig(),
        }
    )

    evaluation = result["case_evaluation"]
    assert evaluation.total_score == 85
    assert evaluation.passed

    report_dir = tmp_path / "reports"
    export_evaluation_reports([evaluation], report_dir)
    assert (report_dir / "case_evaluation.jsonl").exists()
    assert (report_dir / "evaluation_report.csv").exists()
    assert (report_dir / "evaluation_report.md").exists()
    assert (report_dir / "case_reports" / "CASE_001.md").exists()


def test_check_item_scoring_requires_verifiable_evidence() -> None:
    rubric = ScoringRubric(
        scene_id="scene-1",
        total_score=10,
        pass_threshold=8,
        dimensions=[
            ScoringDimension(
                dimension_id="task_completion",
                name="任务完成度",
                weight=10,
                check_items=[
                    ScoringCheckItem(
                        check_id="task_completion__must_say",
                        name="必须说明事项",
                        points=10,
                        pass_condition="客服必须说明核心事项。",
                        evidence_required="客服原话中有核心事项说明。",
                    )
                ],
            )
        ],
    )
    conversation = ConversationResult(
        run_id="run-1",
        case_id="CASE_001",
        scene_id="scene-1",
        priority="P0",
        planned_targets=["task_completion__must_say"],
        triggered_targets=[],
        missing_targets=[],
        coverage_success=True,
        turns=[TurnRecord(role="agent", text="您好，我来说明核心事项。")],
        end_reason="done",
    )
    draft = CaseEvaluationDraft(
        check_item_evaluations=[
            CheckItemEvaluation(
                check_id="task_completion__must_say",
                dimension_id="task_completion",
                name="必须说明事项",
                status="passed",
                reason="客服说明了核心事项。",
                evidence=[
                    EvidenceQuote(
                        turn_index=0,
                        speaker="agent",
                        quote="这句原文不存在",
                    )
                ],
            )
        ],
    )

    evaluation = aggregate_case_evaluation(
        scoring_rubric=rubric,
        conversation_result=conversation,
        draft=draft,
    )

    assert evaluation.total_score == 0
    assert not evaluation.passed
    assert evaluation.check_item_evaluations[0].status == "failed"
    assert any("有效证据" in item for item in evaluation.check_item_evaluations[0].missing_points)
