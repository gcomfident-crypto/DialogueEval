from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


Priority = Literal["P0", "P1", "P2"]
Severity = Literal["normal", "critical"]
RiskSeverity = Literal["low", "medium", "high", "critical"]
Speaker = Literal["agent", "user", "both"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelRoleConfig(StrictModel):
    provider: str
    model: str
    temperature: float = 0.2


class ProviderConfig(StrictModel):
    base_url: str
    api_key_env: str


class ModelConfig(StrictModel):
    default_provider: str
    providers: dict[str, ProviderConfig]
    models: dict[str, ModelRoleConfig]


class CaseGenerationPolicy(StrictModel):
    min_cases: int = 12
    max_cases: int = 40
    p0_ratio: float = 0.45
    coverage_per_case_min: int = 2
    coverage_per_case_max: int = 6
    require_pairwise_diversity: bool = True


class ConversationPolicy(StrictModel):
    default_max_turns: int = 12
    agent_reply_style: str = "短句、自然、电话口吻、给用户说话机会"
    user_reply_style: str = "符合画像，不泄露内部配置，不替客服完成任务"


class VariableMaterializationPolicy(StrictModel):
    enabled: bool = True
    instruction: str = (
        "将评测标准里的模板占位变量实例化为固定、自然、前后一致的业务数值，"
        "避免客服或用户在对话中看到 X/Y/Z/W/${...} 等占位符。"
    )


class ValidationPolicy(StrictModel):
    retry_on_invalid_json: int = 1
    retry_on_schema_error: int = 1
    min_coverage_label_count: int = 8


class GenerationPolicy(StrictModel):
    asset_version: str = "1.0"
    case_generation: CaseGenerationPolicy = Field(default_factory=CaseGenerationPolicy)
    conversation: ConversationPolicy = Field(default_factory=ConversationPolicy)
    variable_materialization: VariableMaterializationPolicy = Field(
        default_factory=VariableMaterializationPolicy
    )
    validation: ValidationPolicy = Field(default_factory=ValidationPolicy)


class BusinessConfig(StrictModel):
    scene_id: Optional[str] = None
    business_variables: dict[str, Any] = Field(default_factory=dict)
    knowledge_overrides: list[str] = Field(default_factory=list)
    forbidden_commitments: list[str] = Field(default_factory=list)


class GenerationMetadata(StrictModel):
    model: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    input_hash: str = ""
    source_eval_standard_path: str = ""
    asset_version: str = "1.0"


class KnowledgeItem(StrictModel):
    id: str
    name: str
    content: str
    when_to_use: str
    business_variables: list[str] = Field(default_factory=list)


class ComplianceRule(StrictModel):
    id: str
    rule: str
    severity: Severity = "normal"
    negative_examples_description: str = ""


class AgentInstruction(StrictModel):
    goal: str
    must_do: list[str] = Field(default_factory=list)
    must_not_do: list[str] = Field(default_factory=list)
    style: str = ""


class SceneAsset(StrictModel):
    scene_id: str
    scene_name: str
    source_eval_standard_path: str
    business_goal: str
    agent_role: str
    user_role: str
    success_definition: str
    knowledge_items: list[KnowledgeItem] = Field(default_factory=list)
    compliance_rules: list[ComplianceRule] = Field(default_factory=list)
    agent_instruction: AgentInstruction
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)


class CoverageLabel(StrictModel):
    label: str
    name: str
    definition: str
    evidence_required: str
    priority: Priority = "P1"
    positive_evidence_examples_description: str = ""
    negative_evidence_examples_description: str = ""


class CoveragePlan(StrictModel):
    scene_id: str
    coverage_labels: list[CoverageLabel]

    @field_validator("coverage_labels")
    @classmethod
    def unique_labels(cls, labels: list[CoverageLabel]) -> list[CoverageLabel]:
        seen: set[str] = set()
        for item in labels:
            if item.label in seen:
                raise ValueError(f"duplicate coverage label: {item.label}")
            seen.add(item.label)
        return labels


class UserProfile(StrictModel):
    profile_id: str
    identity: str
    role: str
    current_context: str
    personality: str
    communication_style: str
    knowledge_level: str
    wrong_beliefs: list[str] = Field(default_factory=list)
    risk_tendency: str = ""
    cooperation_curve: str = ""


class UserProfileCollection(StrictModel):
    scene_id: str
    profiles: list[UserProfile]

    @field_validator("profiles")
    @classmethod
    def unique_profiles(cls, profiles: list[UserProfile]) -> list[UserProfile]:
        seen: set[str] = set()
        for item in profiles:
            if item.profile_id in seen:
                raise ValueError(f"duplicate profile_id: {item.profile_id}")
            seen.add(item.profile_id)
        return profiles


class HiddenUserContext(StrictModel):
    known_facts: list[str] = Field(default_factory=list)
    unknown_facts: list[str] = Field(default_factory=list)
    wrong_beliefs: list[str] = Field(default_factory=list)
    private_goal: str = ""
    main_objection: str = ""


class InitialState(StrictModel):
    emotion: str = "neutral"
    patience: int = 70
    busy_level: str = ""
    environment: str = ""
    willingness: str = "unknown"

    @field_validator("patience")
    @classmethod
    def patience_range(cls, value: int) -> int:
        return max(0, min(100, value))


class BehaviorPolicy(StrictModel):
    disclosure_policy: str = ""
    if_agent_clear: str = ""
    if_agent_wrong: str = ""
    if_agent_too_long: str = ""
    if_agent_pushy: str = ""
    if_agent_violates_rule: str = ""


class StopPolicy(StrictModel):
    max_turns: int = 12
    success_end: str = ""
    forced_end: str = ""

    @field_validator("max_turns")
    @classmethod
    def positive_max_turns(cls, value: int) -> int:
        return max(1, value)


class CaseCard(StrictModel):
    case_id: str
    scene_id: str
    case_name: str
    priority: Priority = "P1"
    profile_id: str
    coverage_targets: list[str]
    hidden_user_context: HiddenUserContext = Field(default_factory=HiddenUserContext)
    initial_state: InitialState = Field(default_factory=InitialState)
    behavior_policy: BehaviorPolicy = Field(default_factory=BehaviorPolicy)
    stop_policy: StopPolicy = Field(default_factory=StopPolicy)

    @field_validator("coverage_targets")
    @classmethod
    def require_targets(cls, targets: list[str]) -> list[str]:
        if not targets:
            raise ValueError("case card must include coverage_targets")
        return targets


class CaseCardCollection(StrictModel):
    scene_id: str
    cases: list[CaseCard]

    @field_validator("cases")
    @classmethod
    def unique_cases(cls, cases: list[CaseCard]) -> list[CaseCard]:
        seen: set[str] = set()
        for item in cases:
            if item.case_id in seen:
                raise ValueError(f"duplicate case_id: {item.case_id}")
            seen.add(item.case_id)
        return cases


class ScoringDimension(StrictModel):
    dimension_id: str
    name: str
    weight: float
    description: str = ""
    full_score_standard: str = ""
    partial_score_rules: list[str] = Field(default_factory=list)
    deduction_rules: list[str] = Field(default_factory=list)
    zero_score_condition: str = ""
    evidence_required: str = ""

    @field_validator("weight")
    @classmethod
    def non_negative_weight(cls, value: float) -> float:
        return max(0.0, value)


class VetoRule(StrictModel):
    rule_id: str
    description: str
    severity: Severity = "critical"
    evidence_required: str = ""


class RiskScoringRule(StrictModel):
    rule_id: str
    description: str
    severity: RiskSeverity = "medium"
    default_deduction: float = 0.0
    evidence_required: str = ""

    @field_validator("default_deduction")
    @classmethod
    def non_negative_deduction(cls, value: float) -> float:
        return max(0.0, value)


class ScoringRubric(StrictModel):
    scene_id: str
    total_score: float = 100.0
    pass_threshold: float = 80.0
    dimensions: list[ScoringDimension]
    veto_rules: list[VetoRule] = Field(default_factory=list)
    risk_rules: list[RiskScoringRule] = Field(default_factory=list)
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)

    @field_validator("dimensions")
    @classmethod
    def require_dimensions(cls, dimensions: list[ScoringDimension]) -> list[ScoringDimension]:
        if not dimensions:
            raise ValueError("scoring rubric must include dimensions")
        return dimensions


class VariableAssignment(StrictModel):
    placeholder: str
    value: str
    usage: str = ""
    rationale: str = ""


class MaterializedEvalStandard(StrictModel):
    materialized_text: str
    assignments: list[VariableAssignment] = Field(default_factory=list)
    unresolved_placeholders: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TurnRecord(StrictModel):
    role: Literal["agent", "user"]
    text: str
    intent: str = ""
    emotion: str = ""
    patience: Optional[int] = None
    risk_flags: list[str] = Field(default_factory=list)


class AgentTurnOutput(StrictModel):
    visible_reply: str
    agent_intent: str
    referenced_knowledge: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    internal_notes: str = ""


class UserStateDelta(StrictModel):
    understood_facts: list[str] = Field(default_factory=list)
    new_objections: list[str] = Field(default_factory=list)
    willingness: str = ""


class UserTurnOutput(StrictModel):
    visible_reply: str
    user_intent: str
    emotion: str
    patience: int
    state_delta: UserStateDelta = Field(default_factory=UserStateDelta)
    should_end_candidate: bool = False
    end_reason_candidate: str = ""

    @field_validator("patience")
    @classmethod
    def clamp_patience(cls, value: int) -> int:
        return max(0, min(100, value))


class CoverageEvidence(StrictModel):
    label: str
    confidence: float = 0.0
    evidence: str
    speaker: Speaker = "both"

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class RiskFlag(StrictModel):
    rule_id: str
    severity: Severity = "normal"
    evidence: str = ""


class CoverageJudgeOutput(StrictModel):
    triggered_targets: list[CoverageEvidence] = Field(default_factory=list)
    missing_targets: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class ConversationState(StrictModel):
    turn_index: int = 0
    emotion: str = "neutral"
    patience: int = 70
    understood_facts: list[str] = Field(default_factory=list)
    active_objections: list[str] = Field(default_factory=list)
    triggered_targets: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    willingness: str = "unknown"
    should_end: bool = False
    end_reason: str = ""


class ConversationResult(StrictModel):
    run_id: str
    case_id: str
    scene_id: str
    priority: Priority
    planned_targets: list[str]
    triggered_targets: list[str]
    missing_targets: list[str]
    coverage_success: bool
    turns: list[TurnRecord]
    coverage_evidence: list[CoverageEvidence] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    end_reason: str


class EvidenceQuote(StrictModel):
    turn_index: int
    speaker: Speaker
    quote: str
    explanation: str = ""

    @field_validator("turn_index")
    @classmethod
    def non_negative_turn_index(cls, value: int) -> int:
        return max(0, value)


class DimensionScore(StrictModel):
    dimension_id: str
    name: str
    weight: float
    score: float
    reason: str
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)

    @field_validator("weight", "score")
    @classmethod
    def non_negative_score_number(cls, value: float) -> float:
        return max(0.0, value)


class VetoFinding(StrictModel):
    rule_id: str
    description: str
    severity: Severity = "critical"
    evidence: list[EvidenceQuote] = Field(default_factory=list)


class RiskDeduction(StrictModel):
    rule_id: str
    description: str
    severity: RiskSeverity = "medium"
    deduction: float = 0.0
    evidence: list[EvidenceQuote] = Field(default_factory=list)

    @field_validator("deduction")
    @classmethod
    def non_negative_risk_deduction(cls, value: float) -> float:
        return max(0.0, value)


class CaseEvaluationDraft(StrictModel):
    dimension_scores: list[DimensionScore]
    veto_items: list[VetoFinding] = Field(default_factory=list)
    risk_deductions: list[RiskDeduction] = Field(default_factory=list)
    final_comment: str = ""


class CaseEvaluationResult(StrictModel):
    run_id: str
    case_id: str
    scene_id: str
    priority: Priority
    raw_score: float
    risk_deduction_total: float
    total_score: float
    pass_threshold: float
    passed: bool
    veto_triggered: bool
    veto_items: list[VetoFinding] = Field(default_factory=list)
    dimension_scores: list[DimensionScore]
    risk_deductions: list[RiskDeduction] = Field(default_factory=list)
    coverage_success: bool
    missing_targets: list[str] = Field(default_factory=list)
    final_comment: str = ""


class GeneratedAssets(StrictModel):
    scene_asset: SceneAsset
    coverage_plan: CoveragePlan
    user_profiles: UserProfileCollection
    case_cards: CaseCardCollection
    scoring_rubric: ScoringRubric


class AssetGenerationState(TypedDict, total=False):
    eval_standard_path: str
    business_config_path: Optional[str]
    generation_policy_path: Optional[str]
    output_root: str
    raw_eval_standard_text: str
    eval_standard_text: str
    materialized_eval_standard: MaterializedEvalStandard
    input_hash: str
    business_config: BusinessConfig
    generation_policy: GenerationPolicy
    scene_asset: SceneAsset
    coverage_plan: CoveragePlan
    user_profiles: UserProfileCollection
    case_cards: CaseCardCollection
    scoring_rubric: ScoringRubric
    asset_dir: str


class ConversationGraphState(TypedDict, total=False):
    run_id: str
    scene_asset: SceneAsset
    coverage_plan: CoveragePlan
    user_profiles: UserProfileCollection
    case_card: CaseCard
    business_config: BusinessConfig
    conversation_state: ConversationState
    history: list[TurnRecord]
    agent_output: AgentTurnOutput
    user_output: UserTurnOutput
    coverage_output: CoverageJudgeOutput
    conversation_result: ConversationResult


class EvaluationGraphState(TypedDict, total=False):
    run_id: str
    scene_asset: SceneAsset
    coverage_plan: CoveragePlan
    scoring_rubric: ScoringRubric
    conversation_result: ConversationResult
    eval_standard_text: str
    business_config: BusinessConfig
    evaluation_draft: CaseEvaluationDraft
    case_evaluation: CaseEvaluationResult


class LLMCallRecord(StrictModel):
    call_id: str
    task_name: str
    role: str
    model: str
    temperature: float
    started_at: str
    ended_at: str
    latency_ms: int
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    success: bool
    error: str = ""
