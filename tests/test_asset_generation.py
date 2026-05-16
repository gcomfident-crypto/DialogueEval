from pathlib import Path

from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.schemas import SceneAsset


def test_asset_generation_graph_writes_assets(tmp_path: Path) -> None:
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 核心目标：完成外呼任务。\n", encoding="utf-8")

    graph = build_asset_generation_graph(FakeLLMClient(), output_root=tmp_path / "assets")
    result = graph.invoke({"eval_standard_path": str(eval_standard)})

    asset_dir = Path(result["asset_dir"])
    assert (asset_dir / "scene_asset.yaml").exists()
    assert (asset_dir / "coverage_plan.yaml").exists()
    assert (asset_dir / "user_profiles.yaml").exists()
    assert (asset_dir / "case_cards.yaml").exists()
    assert (asset_dir / "scoring_rubric.yaml").exists()
    assert (asset_dir / "materialized_eval_standard.md").exists()
    assert (asset_dir / "variable_assignments.yaml").exists()

    assets = load_generated_assets(asset_dir)
    assert assets.scene_asset.scene_id == "generated_scene"
    assert len(assets.coverage_plan.coverage_labels) >= 8
    assert len(assets.case_cards.cases) >= 12
    assert assets.scoring_rubric.total_score == 100


def test_asset_generation_reuses_directory_for_same_input_hash(tmp_path: Path) -> None:
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 核心目标：完成外呼任务。\n", encoding="utf-8")
    llm = ChangingSceneFakeLLM()
    graph = build_asset_generation_graph(llm, output_root=tmp_path / "assets")

    first = graph.invoke({"eval_standard_path": str(eval_standard)})
    second = graph.invoke({"eval_standard_path": str(eval_standard)})

    assert first["asset_dir"] == second["asset_dir"]
    assert not (tmp_path / "assets" / "generated_scene_2").exists()
    assets = load_generated_assets(first["asset_dir"])
    assert assets.scene_asset.scene_id == "generated_scene_1"
    assert assets.coverage_plan.scene_id == "generated_scene_1"
    assert assets.case_cards.cases[0].scene_id == "generated_scene_1"


class ChangingSceneFakeLLM(FakeLLMClient):
    def __init__(self) -> None:
        self.call_records = []
        self._scene_index = 0

    def _payload_for_task(self, task_name: str):
        payload = super()._payload_for_task(task_name)
        if task_name == "scene_asset":
            self._scene_index += 1
            assert isinstance(payload, SceneAsset)
            return payload.model_copy(update={"scene_id": f"generated_scene_{self._scene_index}"})
        return payload
