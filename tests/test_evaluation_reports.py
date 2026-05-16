from pathlib import Path

from dialogue_simulator.evaluation_graph import build_evaluation_graph
from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.report_exporter import export_evaluation_reports
from dialogue_simulator.schemas import (
    BusinessConfig,
    ConversationResult,
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
