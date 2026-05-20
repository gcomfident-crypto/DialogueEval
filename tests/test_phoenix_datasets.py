from pathlib import Path

from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.phoenix_datasets import (
    build_case_seed_examples,
    build_generated_dialogue_examples,
    publish_case_seed_dataset,
)
from dialogue_simulator.schemas import BusinessConfig
from dialogue_simulator.graph import build_conversation_graph


def test_case_seed_examples_store_inputs_without_outputs(tmp_path: Path) -> None:
    assets, asset_dir = _fake_assets(tmp_path, target_case_count=3)

    examples = build_case_seed_examples(
        assets=assets,
        asset_dir=asset_dir,
        asset_version_id="av_test",
    )

    assert len(examples) == 3
    assert "input" in examples[0]
    assert examples[0]["output"] == {}
    assert examples[0]["metadata"]["dialogueeval_dataset_type"] == "case_seed"
    assert examples[0]["input"]["case_card"]["case_id"] == "case_001"


def test_generated_dialogue_examples_store_outputs_as_archive(tmp_path: Path) -> None:
    assets, asset_dir = _fake_assets(tmp_path, target_case_count=1)
    run_graph = build_conversation_graph(
        agent_llm=FakeLLMClient(),
        user_llm=FakeLLMClient(),
        judge_llm=FakeLLMClient(),
    )
    result = run_graph.invoke(
        {
            "run_id": "run_test",
            "scene_asset": assets.scene_asset,
            "coverage_plan": assets.coverage_plan,
            "user_profiles": assets.user_profiles,
            "case_card": assets.case_cards.cases[0],
            "business_config": BusinessConfig(),
        }
    )

    examples = build_generated_dialogue_examples(
        assets=assets,
        asset_dir=asset_dir,
        asset_version_id="av_test",
        run_dir=tmp_path / "run",
        run_id="run_test",
        experiment_id="exp_run_test",
        conversations=[result["conversation_result"]],
        evaluations=[],
    )

    assert len(examples) == 1
    assert examples[0]["metadata"]["dialogueeval_dataset_type"] == "generated_dialogue"
    assert "conversation" in examples[0]["output"]
    assert examples[0]["output"]["summary"]["turn_count"] > 0


def test_publish_case_seed_dataset_uses_phoenix_client(monkeypatch, tmp_path: Path) -> None:
    assets, asset_dir = _fake_assets(tmp_path, target_case_count=2)
    fake_client = _FakePhoenixClient()
    monkeypatch.setattr(
        "dialogue_simulator.phoenix_datasets._phoenix_client",
        lambda base_url: fake_client,
    )

    result = publish_case_seed_dataset(
        assets=assets,
        asset_dir=asset_dir,
        asset_version_id="av_test",
        base_url="http://phoenix.test",
    )

    assert result["status"] == "created"
    assert result["example_count"] == 2
    assert fake_client.datasets.created_examples[0]["metadata"]["dialogueeval_dataset_type"] == "case_seed"


def _fake_assets(tmp_path: Path, *, target_case_count: int):
    eval_standard = tmp_path / "eval_standard.md"
    eval_standard.write_text("# 场景评测标准\n\n- 核心目标：完成外呼任务。\n", encoding="utf-8")
    asset_graph = build_asset_generation_graph(FakeLLMClient(), output_root=tmp_path / "assets")
    result = asset_graph.invoke(
        {
            "eval_standard_path": str(eval_standard),
            "target_case_count": target_case_count,
        }
    )
    asset_dir = Path(result["asset_dir"])
    return load_generated_assets(asset_dir), asset_dir


class _FakePhoenixClient:
    def __init__(self) -> None:
        self.datasets = _FakeDatasets()


class _FakeDatasets:
    def __init__(self) -> None:
        self.created_examples = []

    def add_examples_to_dataset(self, **kwargs):
        raise RuntimeError("dataset does not exist")

    def create_dataset(self, **kwargs):
        self.created_examples = kwargs["examples"]
        return {"id": "dataset_test", "version_id": "version_test"}
