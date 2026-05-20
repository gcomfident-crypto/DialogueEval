from pathlib import Path

from dialogue_simulator.evaluator import aggregate_case_evaluation
from dialogue_simulator.evaluation_graph import build_evaluation_graph
from dialogue_simulator.graph import build_asset_generation_graph, load_generated_assets
from dialogue_simulator.llm_client import FakeLLMClient
from dialogue_simulator.report_exporter import export_evaluation_reports
from dialogue_simulator.rubric_validator import validate_scoring_rubric
from dialogue_simulator.schemas import (
    AgentInstruction,
    BusinessConfig,
    CaseEvaluationDraft,
    CaseValidityAssessment,
    CheckItemEvaluation,
    ComplianceRule,
    ConversationResult,
    CoverageLabel,
    CoveragePlan,
    EvidenceQuote,
    RiskDeduction,
    RiskScoringRule,
    ScoringCheckItem,
    ScoringDimension,
    ScoringRubric,
    SceneAsset,
    TurnRecord,
    VetoFinding,
    VetoRule,
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
    export_evaluation_reports(
        [evaluation],
        report_dir,
        conversations=[conversation],
        coverage_plan=assets.coverage_plan,
        scoring_rubric=assets.scoring_rubric,
    )
    assert (report_dir / "case_evaluation.jsonl").exists()
    assert (report_dir / "evaluation_report.csv").exists()
    total_report = report_dir / "evaluation_report.md"
    assert total_report.exists()
    total_report_text = total_report.read_text(encoding="utf-8")
    assert "## 3. 核心量化指标" in total_report_text
    assert "总通过率" in total_report_text
    assert "P0 指令覆盖率" in total_report_text
    assert "风险发现率" in total_report_text
    assert "稳定性" in total_report_text
    case_report = report_dir / "case_reports" / "CASE_001.md"
    assert case_report.exists()
    report_text = case_report.read_text(encoding="utf-8")
    assert "## 3. 原子评分项" in report_text
    assert "失分" in report_text


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


def test_rubric_validator_detects_unmapped_p0_and_compliance_rule() -> None:
    scene_asset = SceneAsset(
        scene_id="scene-1",
        scene_name="测试场景",
        source_eval_standard_path="standard.md",
        business_goal="完成外呼任务",
        agent_role="客服",
        user_role="用户",
        success_definition="用户理解后结束",
        agent_instruction=AgentInstruction(goal="完成任务"),
        compliance_rules=[
            ComplianceRule(id="R001", rule="不得虚假承诺", severity="critical")
        ],
    )
    coverage_plan = CoveragePlan(
        scene_id="scene-1",
        coverage_labels=[
            CoverageLabel(
                label="must_confirm",
                name="确认意愿",
                definition="必须确认用户意愿",
                evidence_required="客服询问用户意愿",
                priority="P0",
            )
        ],
    )
    rubric = ScoringRubric(
        scene_id="scene-1",
        total_score=100,
        dimensions=[
            ScoringDimension(
                dimension_id="task_completion",
                name="任务完成度",
                weight=100,
                check_items=[
                    ScoringCheckItem(
                        check_id="task_completion__other",
                        name="其它事项",
                        points=100,
                        pass_condition="完成其它事项",
                    )
                ],
            )
        ],
    )

    errors = validate_scoring_rubric(
        scoring_rubric=rubric,
        coverage_plan=coverage_plan,
        scene_asset=scene_asset,
    )

    assert any("P0 coverage labels" in item for item in errors)
    assert any("compliance rules" in item for item in errors)


def test_defect_injection_veto_and_risk_are_normalized_once() -> None:
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
                    )
                ],
            )
        ],
        veto_rules=[
            VetoRule(
                rule_id="veto_false_commitment",
                description="客服承诺未授权补贴。",
                severity="critical",
            )
        ],
        risk_rules=[
            RiskScoringRule(
                rule_id="risk_missing_willingness",
                description="客服未确认用户意愿。",
                severity="medium",
                default_deduction=3,
            )
        ],
    )
    conversation = ConversationResult(
        run_id="run-1",
        case_id="CASE_BAD",
        scene_id="scene-1",
        priority="P0",
        planned_targets=["task_completion__must_say"],
        triggered_targets=[],
        missing_targets=[],
        coverage_success=True,
        turns=[TurnRecord(role="agent", text="我保证给你额外补贴，先照做就行。")],
        end_reason="done",
    )
    evidence = [
        EvidenceQuote(
            turn_index=0,
            speaker="agent",
            quote="我保证给你额外补贴，先照做就行。",
        )
    ]
    draft = CaseEvaluationDraft(
        check_item_evaluations=[
            CheckItemEvaluation(
                check_id="task_completion__must_say",
                dimension_id="task_completion",
                status="passed",
                reason="客服有回复。",
                evidence=evidence,
            )
        ],
        risk_deductions=[
            RiskDeduction(
                rule_id="risk_missing_willingness",
                description="",
                deduction=3,
                evidence=evidence,
            ),
            RiskDeduction(
                rule_id="risk_missing_willingness",
                description="",
                deduction=3,
                evidence=evidence,
            ),
            RiskDeduction(
                rule_id="unknown_risk",
                description="未知风险",
                deduction=5,
                evidence=evidence,
            ),
        ],
        veto_items=[
            VetoFinding(rule_id="veto_false_commitment", description="", evidence=evidence),
            VetoFinding(rule_id="unknown_veto", description="未知一票否决", evidence=evidence),
        ],
    )

    evaluation = aggregate_case_evaluation(
        scoring_rubric=rubric,
        conversation_result=conversation,
        draft=draft,
    )

    assert evaluation.veto_triggered
    assert not evaluation.passed
    assert len(evaluation.veto_items) == 1
    assert evaluation.veto_items[0].description == "客服承诺未授权补贴。"
    assert len(evaluation.risk_deductions) == 1
    assert evaluation.risk_deduction_total == 3
    assert evaluation.total_score == 7


def test_invalid_user_simulation_case_is_not_counted_as_passed() -> None:
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
                    )
                ],
            )
        ],
    )
    conversation = ConversationResult(
        run_id="run-1",
        case_id="CASE_INVALID",
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
        case_validity=CaseValidityAssessment(
            status="invalid_user_simulation",
            reason="用户模拟器没有触发预设测试条件。",
        ),
        check_item_evaluations=[
            CheckItemEvaluation(
                check_id="task_completion__must_say",
                dimension_id="task_completion",
                status="passed",
                reason="客服说明了核心事项。",
                evidence=[
                    EvidenceQuote(
                        turn_index=0,
                        speaker="agent",
                        quote="您好，我来说明核心事项。",
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

    assert evaluation.total_score == 10
    assert evaluation.case_validity.status == "invalid_user_simulation"
    assert not evaluation.passed
