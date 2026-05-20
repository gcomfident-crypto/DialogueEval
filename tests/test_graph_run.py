from pathlib import Path

from dialogue_simulator.graph import (
    build_asset_generation_graph,
    build_conversation_graph,
    load_generated_assets,
)
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.report_exporter import export_run_reports
from dialogue_simulator.schemas import BusinessConfig


def test_conversation_graph_and_report_export(tmp_path: Path) -> None:
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 核心目标：完成外呼任务。\n", encoding="utf-8")

    asset_graph = build_asset_generation_graph(FakeLLMClient(), output_root=tmp_path / "assets")
    asset_result = asset_graph.invoke({"eval_standard_path": str(eval_standard)})
    assets = load_generated_assets(asset_result["asset_dir"])

    run_graph = build_conversation_graph(
        agent_llm=FakeLLMClient(),
        user_llm=FakeLLMClient(),
        judge_llm=FakeLLMClient(),
    )
    result = run_graph.invoke(
        {
            "run_id": "test-run",
            "scene_asset": assets.scene_asset,
            "coverage_plan": assets.coverage_plan,
            "user_profiles": assets.user_profiles,
            "case_card": assets.case_cards.cases[0],
            "business_config": BusinessConfig(),
        }
    )

    conversation = result["conversation_result"]
    assert conversation.case_id == "case_001"
    assert conversation.turns

    report_dir = tmp_path / "run"
    export_run_reports([conversation], report_dir)
    assert (report_dir / "conversation_log.jsonl").exists()
    assert (report_dir / "coverage_report.csv").exists()
    assert (report_dir / "summary_report.md").exists()


def test_asset_generation_graph_accepts_target_case_count(tmp_path: Path) -> None:
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 核心目标：完成外呼任务。\n", encoding="utf-8")

    asset_graph = build_asset_generation_graph(FakeLLMClient(), output_root=tmp_path / "assets")
    asset_result = asset_graph.invoke(
        {
            "eval_standard_path": str(eval_standard),
            "target_case_count": 5,
        }
    )
    assets = load_generated_assets(asset_result["asset_dir"])

    assert len(assets.case_cards.cases) == 5
    assert assets.case_generation_plan is not None
    assert assets.case_generation_plan.target_case_count == 5
