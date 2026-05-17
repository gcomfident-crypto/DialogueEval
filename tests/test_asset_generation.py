from pathlib import Path

from dialogue_simulator.asset_generator import _repair_and_validate_case_cards
from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.schemas import (
    AgentInstruction,
    CaseCard,
    CaseCardCollection,
    CaseGenerationPolicy,
    CoverageLabel,
    CoveragePlan,
    CoverageTaxonomy,
    CoverageTaxonomyItem,
    GenerationPolicy,
    SceneAsset,
    UserProfile,
    UserProfileCollection,
)


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


def test_case_card_coverage_targets_only_keep_coverage_labels() -> None:
    scene_asset = SceneAsset(
        scene_id="generated_scene",
        scene_name="测试场景",
        source_eval_standard_path="standard.md",
        business_goal="完成外呼任务",
        agent_role="客服",
        user_role="用户",
        success_definition="用户理解关键事项",
        agent_instruction=AgentInstruction(goal="完成任务"),
    )
    coverage_plan = CoveragePlan(
        scene_id="generated_scene",
        coverage_labels=[
            CoverageLabel(
                label="identity_confirmation",
                name="身份确认",
                definition="确认通话对象身份",
                evidence_required="对话中有身份确认证据",
                priority="P0",
            )
        ],
    )
    coverage_taxonomy = CoverageTaxonomy(
        scene_id="generated_scene",
        flow_branches=[
            CoverageTaxonomyItem(
                item_id="flow_abandonment_termination",
                name="放弃终止",
                description="用户想结束通话的流程分支",
            )
        ],
        user_behaviors=[
            CoverageTaxonomyItem(
                item_id="user_refuse_delivery",
                name="用户拒绝",
                description="用户表达拒绝配合",
            )
        ],
        risk_probes=[
            CoverageTaxonomyItem(
                item_id="risk_false_commitment",
                name="虚假承诺风险",
                description="测试客服是否做出越权承诺",
            )
        ],
        dynamic_state_paths=[
            CoverageTaxonomyItem(
                item_id="state_hesitant_to_refuse",
                name="犹豫到拒绝",
                description="用户态度从犹豫转为拒绝",
            )
        ],
    )
    user_profiles = UserProfileCollection(
        scene_id="generated_scene",
        profiles=[
            UserProfile(
                profile_id="U001",
                identity="目标用户本人",
                role="被外呼用户",
                current_context="可以接听电话",
                personality="谨慎",
                communication_style="短句",
                knowledge_level="不了解任务细节",
            )
        ],
    )
    case_cards = CaseCardCollection(
        scene_id="generated_scene",
        cases=[
            CaseCard(
                case_id="case_007",
                scene_id="generated_scene",
                case_name="标签归位验证",
                profile_id="U001",
                coverage_targets=[
                    "identity_confirmation",
                    "flow_abandonment_termination",
                    "user_refuse_delivery",
                    "risk_false_commitment",
                    "state_hesitant_to_refuse",
                ],
            )
        ],
    )
    policy = GenerationPolicy(
        case_generation=CaseGenerationPolicy(min_cases=1, target_cases=1, max_cases=5)
    )

    repaired = _repair_and_validate_case_cards(
        case_cards,
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
        user_profiles=user_profiles,
        generation_policy=policy,
        coverage_taxonomy=coverage_taxonomy,
    )

    repaired_case = repaired.cases[0]
    assert repaired_case.coverage_targets == ["identity_confirmation"]
    assert repaired_case.flow_branch_tags == ["flow_abandonment_termination"]
    assert repaired_case.user_behavior_tags == ["user_refuse_delivery"]
    assert repaired_case.risk_probe_tags == ["risk_false_commitment"]
    assert repaired_case.dynamic_state_path_tags == ["state_hesitant_to_refuse"]


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
