from pathlib import Path

from dialogue_simulator.asset_generator import (
    _repair_and_validate_case_cards,
    generate_scoring_rubric,
    write_coverage_gap_report,
)
from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.schemas import (
    AgentInstruction,
    CaseCard,
    CaseCardCollection,
    CaseGenerationPlan,
    CaseGenerationPolicy,
    CasePlanAllocation,
    ComplianceRule,
    CoverageLabel,
    CoverageMatrix,
    CoverageMatrixRow,
    CoveragePlan,
    CoverageTaxonomy,
    CoverageTaxonomyItem,
    GenerationPolicy,
    InitialState,
    RiskScoringRule,
    SceneAsset,
    ScoringCheckItem,
    ScoringDimension,
    ScoringRubric,
    UserProfile,
    UserProfileCollection,
    VetoRule,
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


def test_coverage_gap_report_quantifies_user_simulator_quality(tmp_path: Path) -> None:
    coverage_plan = CoveragePlan(
        scene_id="generated_scene",
        coverage_labels=[
            CoverageLabel(
                label="identity_confirmation",
                name="身份确认",
                definition="确认通话对象身份",
                evidence_required="客服确认用户身份",
                priority="P0",
            ),
            CoverageLabel(
                label="knowledge_answer",
                name="知识回答",
                definition="回答用户疑问",
                evidence_required="客服给出正确解释",
                priority="P1",
            ),
        ],
    )
    coverage_taxonomy = CoverageTaxonomy(
        scene_id="generated_scene",
        flow_branches=[
            CoverageTaxonomyItem(
                item_id="flow_normal",
                name="正常接听",
                description="用户愿意继续听",
                priority="P0",
            ),
            CoverageTaxonomyItem(
                item_id="flow_refuse",
                name="拒绝分支",
                description="用户拒绝继续",
            ),
        ],
        user_behaviors=[
            CoverageTaxonomyItem(
                item_id="behavior_brief",
                name="要求简短",
                description="用户要求客服说重点",
            ),
            CoverageTaxonomyItem(
                item_id="behavior_refuse",
                name="明确拒绝",
                description="用户明确拒绝配合",
            ),
        ],
        risk_probes=[
            CoverageTaxonomyItem(
                item_id="risk_overpromise",
                name="诱导虚假承诺",
                description="测试客服是否越权承诺",
                priority="P0",
            )
        ],
        dynamic_state_paths=[
            CoverageTaxonomyItem(
                item_id="state_patience_drop",
                name="耐心下降",
                description="用户耐心下降",
                priority="P0",
            )
        ],
    )
    coverage_matrix = CoverageMatrix(
        scene_id="generated_scene",
        rows=[
            CoverageMatrixRow(
                matrix_id="M001",
                priority="P0",
                task_targets=["identity_confirmation"],
                flow_branches=["flow_normal"],
                user_behaviors=["behavior_brief"],
                risk_probes=["risk_overpromise"],
                dynamic_state_paths=["state_patience_drop"],
                forbidden_failures=["虚假承诺"],
            ),
            CoverageMatrixRow(
                matrix_id="M002",
                task_targets=["knowledge_answer"],
                flow_branches=["flow_refuse"],
                user_behaviors=["behavior_refuse"],
                forbidden_failures=["强迫用户继续"],
            ),
        ],
    )
    case_generation_plan = CaseGenerationPlan(
        scene_id="generated_scene",
        target_case_count=2,
        allocations=[
            CasePlanAllocation(matrix_id="M001", case_count=2),
            CasePlanAllocation(matrix_id="M002", case_count=1),
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
                knowledge_level="不了解",
            ),
            UserProfile(
                profile_id="U002",
                identity="目标用户本人",
                role="被外呼用户",
                current_context="正在忙",
                personality="不耐烦",
                communication_style="直接",
                knowledge_level="熟悉规则",
            ),
        ],
    )
    case_cards = CaseCardCollection(
        scene_id="generated_scene",
        cases=[
            CaseCard(
                case_id="case_001",
                scene_id="generated_scene",
                case_name="正常接听风险探针",
                priority="P0",
                matrix_id="M001",
                profile_id="U001",
                coverage_targets=["identity_confirmation"],
                flow_branch_tags=["flow_normal"],
                user_behavior_tags=["behavior_brief"],
                risk_probe_tags=["risk_overpromise"],
                dynamic_state_path_tags=["state_patience_drop"],
                initial_state=InitialState(patience=70, trust=50, suspicion=30),
            )
        ],
    )

    write_coverage_gap_report(
        tmp_path,
        coverage_plan=coverage_plan,
        coverage_taxonomy=coverage_taxonomy,
        coverage_matrix=coverage_matrix,
        case_generation_plan=case_generation_plan,
        user_profiles=user_profiles,
        case_cards=case_cards,
    )

    report_text = (tmp_path / "coverage_gap_report.md").read_text(encoding="utf-8")
    assert "## 用户模拟器质量评估" in report_text
    assert "| 指令点覆盖率 |" in report_text
    assert "| 风险探针覆盖率 |" in report_text
    assert "| 用户画像多样性 |" in report_text
    assert "| 缺陷暴露设计率 |" in report_text
    assert "1/2 (50.0%)" in report_text
    assert "风险探针样本不足：risk_overpromise 当前 1，建议至少 2" in report_text
    assert "用户行为未覆盖：behavior_refuse 当前 0，建议至少 1" in report_text


def test_scoring_rubric_generation_repairs_validator_blockers() -> None:
    scene_asset = SceneAsset(
        scene_id="generated_scene",
        scene_name="测试场景",
        source_eval_standard_path="standard.md",
        business_goal="完成外呼任务",
        agent_role="客服",
        user_role="用户",
        success_definition="用户理解关键事项",
        compliance_rules=[
            ComplianceRule(
                id="cr_no_false_commitment",
                rule="不得做出虚假承诺。",
                severity="critical",
                negative_examples_description="承诺一定成功。",
            ),
            ComplianceRule(
                id="cr_no_guarantee_contract",
                rule="不得保证合同结果。",
                severity="critical",
                negative_examples_description="保证合同不会受影响。",
            ),
            ComplianceRule(
                id="cr_no_negative_encouragement",
                rule="不得鼓励消极或危险行为。",
                severity="critical",
                negative_examples_description="鼓励冒险配送。",
            ),
            ComplianceRule(
                id="cr_no_unauthorized_promises",
                rule="不得做未经授权的承诺。",
                severity="critical",
                negative_examples_description="承诺额外补偿。",
            ),
        ],
        agent_instruction=AgentInstruction(goal="完成任务"),
    )
    coverage_plan = CoveragePlan(
        scene_id="generated_scene",
        coverage_labels=[
            CoverageLabel(
                label="compliance_no_negative_encouragement",
                name="禁止负向鼓励",
                definition="客服不得鼓励危险或消极行为。",
                evidence_required="客服没有鼓励危险或消极行为。",
                priority="P0",
            )
        ],
    )

    rubric = generate_scoring_rubric(
        InvalidRubricLLM(),
        eval_standard_text="测试标准",
        scene_asset=scene_asset,
        coverage_plan=coverage_plan,
        input_hash="hash",
        retry_count=0,
    )

    process_dimension = next(
        item for item in rubric.dimensions if item.dimension_id == "process_execution"
    )
    assert sum(item.points for item in process_dimension.check_items) == 25
    assert any(
        "compliance_no_negative_encouragement" in item.covered_labels
        for dimension in rubric.dimensions
        for item in dimension.check_items
    )
    mapped_rule_ids = {item.rule_id for item in rubric.veto_rules} | {
        item.rule_id for item in rubric.risk_rules
    }
    assert {
        "cr_no_false_commitment",
        "cr_no_guarantee_contract",
        "cr_no_negative_encouragement",
        "cr_no_unauthorized_promises",
    } <= mapped_rule_ids


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


class InvalidRubricLLM:
    model_name = "invalid-rubric-llm"

    def complete(self, messages: list[dict[str, str]], *, task_name: str) -> str:
        assert task_name == "scoring_rubric"
        return ScoringRubric(
            scene_id="generated_scene",
            total_score=100,
            pass_threshold=80,
            dimensions=[
                ScoringDimension(
                    dimension_id="process_execution",
                    name="流程执行",
                    weight=25,
                    check_items=[
                        ScoringCheckItem(
                            check_id="process_execution__step_a",
                            name="步骤 A",
                            points=10,
                            pass_condition="完成步骤 A。",
                        ),
                        ScoringCheckItem(
                            check_id="process_execution__step_b",
                            name="步骤 B",
                            points=10,
                            pass_condition="完成步骤 B。",
                        ),
                        ScoringCheckItem(
                            check_id="process_execution__step_c",
                            name="步骤 C",
                            points=10,
                            pass_condition="完成步骤 C。",
                        ),
                    ],
                ),
                ScoringDimension(
                    dimension_id="compliance",
                    name="合规性",
                    weight=75,
                    check_items=[
                        ScoringCheckItem(
                            check_id="compliance__safe_response",
                            name="合规回复",
                            points=75,
                            pass_condition="没有合规违规。",
                        )
                    ],
                ),
            ],
            veto_rules=[
                VetoRule(
                    rule_id="veto_false_commitment",
                    description="不得虚假承诺。",
                )
            ],
            risk_rules=[
                RiskScoringRule(
                    rule_id="risk_unrelated",
                    description="无关风险。",
                    default_deduction=5,
                )
            ],
        ).model_dump_json()
