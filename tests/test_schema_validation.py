from dialogue_simulator.schemas import (
    AgentInstruction,
    CaseCard,
    CoverageLabel,
    CoveragePlan,
    SceneAsset,
)


def test_case_card_requires_coverage_targets() -> None:
    try:
        CaseCard(
            case_id="CASE_001",
            scene_id="generated_scene",
            case_name="missing targets",
            profile_id="U001",
            coverage_targets=[],
        )
    except ValueError as exc:
        assert "coverage_targets" in str(exc)
    else:
        raise AssertionError("CaseCard accepted empty coverage_targets")


def test_coverage_labels_must_be_unique() -> None:
    label = CoverageLabel(
        label="C001",
        name="核心目标",
        definition="完成核心目标",
        evidence_required="有语义证据",
    )
    try:
        CoveragePlan(scene_id="generated_scene", coverage_labels=[label, label])
    except ValueError as exc:
        assert "duplicate coverage label" in str(exc)
    else:
        raise AssertionError("CoveragePlan accepted duplicate labels")


def test_scene_asset_schema_accepts_generic_content() -> None:
    asset = SceneAsset(
        scene_id="generated_scene",
        scene_name="通用场景",
        source_eval_standard_path="standard.md",
        business_goal="完成外呼任务",
        agent_role="客服",
        user_role="用户",
        success_definition="用户理解后结束",
        agent_instruction=AgentInstruction(goal="完成任务"),
    )
    assert asset.scene_id == "generated_scene"
