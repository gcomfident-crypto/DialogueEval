from __future__ import annotations

import hashlib
import json
import os
import time
from uuid import uuid4
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import OpenAI

from dialogue_simulator.schemas import (
    AgentInstruction,
    AgentTurnOutput,
    BehaviorPolicy,
    BusinessConfig,
    CaseEvaluationDraft,
    CaseCard,
    CaseCardCollection,
    ComplianceRule,
    CoverageEvidence,
    CoverageJudgeOutput,
    CoverageLabel,
    CoveragePlan,
    GenerationMetadata,
    HiddenUserContext,
    InitialState,
    KnowledgeItem,
    ModelConfig,
    ModelRoleConfig,
    RiskFlag,
    RiskDeduction,
    ScoringDimension,
    ScoringRubric,
    SceneAsset,
    StopPolicy,
    UserProfile,
    UserProfileCollection,
    UserStateDelta,
    DimensionScore,
    EvidenceQuote,
    LLMCallRecord,
    MaterializedEvalStandard,
    UserTurnOutput,
    VariableAssignment,
    utc_now_iso,
)
from dialogue_simulator.tracing import trace_span


class LLMClient(Protocol):
    model_name: str

    def complete(self, messages: list[dict[str, str]], *, task_name: str) -> str:
        ...


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key_env: str,
        model: str,
        temperature: float = 0.2,
        role: str = "",
    ) -> None:
        load_dotenv()
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing {api_key_env}. Set it in the environment or use --fake-llm for tests."
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model
        self._temperature = temperature
        self.role = role
        self.call_records: list[LLMCallRecord] = []

    @classmethod
    def from_config(cls, config: ModelConfig, role: str) -> "OpenAICompatibleClient":
        role_config = config.models[role]
        provider = config.providers[role_config.provider]
        return cls(
            base_url=provider.base_url,
            api_key_env=provider.api_key_env,
            model=role_config.model,
            temperature=role_config.temperature,
            role=role,
        )

    def complete(self, messages: list[dict[str, str]], *, task_name: str) -> str:
        started_at = utc_now_iso()
        started = time.monotonic()
        call_id = uuid4().hex
        prompt_summary = _message_summary(messages)
        with trace_span(
            f"llm.{task_name}",
            kind="llm",
            attributes={
                "llm.call_id": call_id,
                "llm.task_name": task_name,
                "llm.role": self.role,
                "llm.model_name": self.model_name,
                "llm.temperature": self._temperature,
                "llm.message_count": prompt_summary["message_count"],
                "llm.prompt_chars": prompt_summary["prompt_chars"],
                "llm.prompt_hash": prompt_summary["prompt_hash"],
                "llm.trace_message_mode": _trace_message_mode(),
            },
            input_data=_messages_trace_payload(messages, prompt_summary),
        ) as span:
            try:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self._temperature,
                    stream=False,
                )
                content = response.choices[0].message.content
                if not content:
                    raise RuntimeError(f"LLM returned empty content for task {task_name}.")
                record = self._record_from_response(
                    call_id=call_id,
                    task_name=task_name,
                    started_at=started_at,
                    started=started,
                    response=response,
                    success=True,
                    error="",
                    prompt_summary=prompt_summary,
                    completion=content,
                )
                self.call_records.append(record)
                span.set_attributes(
                    {
                        "llm.prompt_tokens": record.prompt_tokens,
                        "llm.completion_tokens": record.completion_tokens,
                        "llm.total_tokens": record.total_tokens,
                        "llm.latency_ms": record.latency_ms,
                        "llm.success": True,
                        "llm.completion_chars": record.completion_chars,
                        "llm.completion_hash": record.completion_hash,
                    }
                )
                span.set_output(_completion_trace_payload(content))
                return content
            except Exception as exc:
                self.call_records.append(
                    LLMCallRecord(
                        call_id=call_id,
                        task_name=task_name,
                        role=self.role,
                        model=self.model_name,
                        temperature=self._temperature,
                        started_at=started_at,
                        ended_at=utc_now_iso(),
                        latency_ms=int((time.monotonic() - started) * 1000),
                        message_count=prompt_summary["message_count"],
                        prompt_chars=prompt_summary["prompt_chars"],
                        prompt_hash=prompt_summary["prompt_hash"],
                        success=False,
                        error=str(exc),
                    )
                )
                span.set_attributes({"llm.success": False, "llm.error": str(exc)})
                raise

    def _record_from_response(
        self,
        *,
        call_id: str,
        task_name: str,
        started_at: str,
        started: float,
        response: Any,
        success: bool,
        error: str,
        prompt_summary: dict[str, Any],
        completion: str,
    ) -> LLMCallRecord:
        usage = getattr(response, "usage", None)
        return LLMCallRecord(
            call_id=call_id,
            task_name=task_name,
            role=self.role,
            model=self.model_name,
            temperature=self._temperature,
            started_at=started_at,
            ended_at=utc_now_iso(),
            latency_ms=int((time.monotonic() - started) * 1000),
            message_count=prompt_summary["message_count"],
            prompt_chars=prompt_summary["prompt_chars"],
            prompt_hash=prompt_summary["prompt_hash"],
            completion_chars=len(completion),
            completion_hash=_text_hash(completion),
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
            estimated_cost=None,
            success=success,
            error=error,
        )


class FakeLLMClient:
    """Generic fake for schema and graph tests, not a business simulator."""

    model_name = "fake-llm"
    role = "fake"
    call_records: list[LLMCallRecord] = []

    def complete(self, messages: list[dict[str, str]], *, task_name: str) -> str:
        call_id = uuid4().hex
        prompt_summary = _message_summary(messages)
        with trace_span(
            f"llm.{task_name}",
            kind="llm",
            attributes={
                "llm.call_id": call_id,
                "llm.task_name": task_name,
                "llm.role": self.role,
                "llm.model_name": self.model_name,
                "llm.temperature": 0.0,
                "llm.fake": True,
                "llm.message_count": prompt_summary["message_count"],
                "llm.prompt_chars": prompt_summary["prompt_chars"],
                "llm.prompt_hash": prompt_summary["prompt_hash"],
                "llm.trace_message_mode": _trace_message_mode(),
            },
            input_data=_messages_trace_payload(messages, prompt_summary),
        ) as span:
            payload = self._payload_for_task(task_name)
            output = payload.model_dump_json() if hasattr(payload, "model_dump_json") else payload
            self.call_records.append(
                LLMCallRecord(
                    call_id=call_id,
                    task_name=task_name,
                    role=self.role,
                    model=self.model_name,
                    temperature=0.0,
                    started_at=utc_now_iso(),
                    ended_at=utc_now_iso(),
                    latency_ms=0,
                    message_count=prompt_summary["message_count"],
                    prompt_chars=prompt_summary["prompt_chars"],
                    prompt_hash=prompt_summary["prompt_hash"],
                    completion_chars=len(str(output)),
                    completion_hash=_text_hash(str(output)),
                    success=True,
                )
            )
            span.set_attributes(
                {
                    "llm.success": True,
                    "llm.latency_ms": 0,
                    "llm.completion_chars": len(str(output)),
                    "llm.completion_hash": _text_hash(str(output)),
                }
            )
            span.set_output(_completion_trace_payload(str(output)))
            return output

    def _payload_for_task(self, task_name: str) -> Any:
        if task_name == "eval_standard_materialization":
            return MaterializedEvalStandard(
                materialized_text=(
                    "# 场景评测标准\n\n"
                    "- 核心目标：完成外呼任务。\n"
                    "- 示例变量：单日 10 单，多日每天 8 单，连续 7 天。"
                ),
                assignments=[
                    VariableAssignment(
                        placeholder="X",
                        value="10",
                        usage="单日合同最低单量",
                        rationale="fake LLM 用于结构测试的固定值。",
                    )
                ],
                unresolved_placeholders=[],
                notes=["fake output for graph validation"],
            )
        if task_name == "scene_asset":
            return SceneAsset(
                scene_id="generated_scene",
                scene_name="模型生成场景",
                source_eval_standard_path="",
                business_goal="根据评测标准完成一次外呼任务。",
                agent_role="外呼客服",
                user_role="被外呼用户",
                success_definition="用户理解关键事项，对话自然结束。",
                knowledge_items=[
                    KnowledgeItem(
                        id="K001",
                        name="核心信息",
                        content="客服需要根据评测标准传达核心信息。",
                        when_to_use="任务推进时使用。",
                    )
                ],
                compliance_rules=[
                    ComplianceRule(
                        id="R001",
                        rule="不得承诺评测标准或业务配置中没有的事项。",
                        severity="critical",
                        negative_examples_description="未经授权的优惠、补偿或权限承诺。",
                    )
                ],
                agent_instruction=AgentInstruction(
                    goal="完成外呼任务并保持合规。",
                    must_do=["确认身份", "传达核心事项", "处理用户疑问"],
                    must_not_do=["不得编造承诺", "不得长篇压迫式表达"],
                    style="简短、自然、电话口吻。",
                ),
                generation_metadata=GenerationMetadata(
                    model=self.model_name,
                    created_at=utc_now_iso(),
                    input_hash="fake",
                ),
            )
        if task_name == "coverage_plan":
            return CoveragePlan(
                scene_id="generated_scene",
                coverage_labels=[
                    CoverageLabel(
                        label=f"C{i:03d}",
                        name=name,
                        definition=f"需要在对话中完成：{name}",
                        evidence_required=f"对话中出现满足“{name}”语义的表达。",
                        priority="P0" if i <= 3 else "P1",
                        positive_evidence_examples_description="可由客服或用户的语义确认构成证据。",
                        negative_evidence_examples_description="只提到无关内容或证据不足。",
                    )
                    for i, name in enumerate(
                        [
                            "身份确认",
                            "核心信息传达",
                            "用户疑问处理",
                            "合规边界遵守",
                            "异常分支处理",
                            "表达简洁自然",
                            "结束确认",
                            "业务知识准确",
                        ],
                        start=1,
                    )
                ],
            )
        if task_name == "user_profiles":
            return UserProfileCollection(
                scene_id="generated_scene",
                profiles=[
                    UserProfile(
                        profile_id="U001",
                        identity="目标用户本人",
                        role="业务相关用户",
                        current_context="可以接听电话，但希望对方简短。",
                        personality="谨慎",
                        communication_style="短句、口语化",
                        knowledge_level="只了解部分信息",
                        wrong_beliefs=["以为这通电话不重要"],
                        risk_tendency="可能追问边界问题",
                        cooperation_curve="解释清楚后逐渐配合",
                    )
                ],
            )
        if task_name == "case_cards":
            return CaseCardCollection(
                scene_id="generated_scene",
                cases=[
                    CaseCard(
                        case_id=f"CASE_{index:03d}",
                        scene_id="generated_scene",
                        case_name=f"通用流程验证 {index}",
                        priority="P0" if index <= 6 else "P1",
                        profile_id="U001",
                        coverage_targets=[
                            f"C{((index - 1) % 8) + 1:03d}",
                            f"C{(index % 8) + 1:03d}",
                        ],
                        hidden_user_context=HiddenUserContext(
                            unknown_facts=["核心任务信息"],
                            private_goal="尽快确认这通电话是否有必要继续。",
                            main_objection="不确定对方说明是否和自己有关。",
                        ),
                        initial_state=InitialState(
                            emotion="neutral",
                            patience=70,
                            busy_level="一般",
                            environment="可通话",
                            willingness="unknown",
                        ),
                        behavior_policy=BehaviorPolicy(
                            disclosure_policy="只根据客服提问逐步透露信息。",
                            if_agent_clear="更配合并确认理解。",
                            if_agent_wrong="继续追问。",
                            if_agent_too_long="要求对方简短。",
                            if_agent_pushy="变得谨慎。",
                            if_agent_violates_rule="追问对方是否确定。",
                        ),
                        stop_policy=StopPolicy(
                            max_turns=4,
                            success_end="关键目标已覆盖且用户理解。",
                            forced_end="达到最大轮次或用户明确结束。",
                        ),
                    )
                    for index in range(1, 13)
                ],
            )
        if task_name == "scoring_rubric":
            return ScoringRubric(
                scene_id="generated_scene",
                total_score=100,
                pass_threshold=80,
                dimensions=[
                    ScoringDimension(
                        dimension_id="task_completion",
                        name="任务完成度",
                        weight=40,
                        description="核心任务是否完成。",
                        full_score_standard="核心任务均已完成。",
                        partial_score_rules=["部分完成按证据给分。"],
                        deduction_rules=["缺失核心事项扣分。"],
                        zero_score_condition="完全未触达任务。",
                        evidence_required="对话中有明确语义证据。",
                    ),
                    ScoringDimension(
                        dimension_id="compliance",
                        name="合规性",
                        weight=30,
                        description="是否遵守合规边界。",
                        full_score_standard="无违规承诺和压迫表达。",
                        partial_score_rules=["轻微风险酌情扣分。"],
                        deduction_rules=["出现风险按严重程度扣分。"],
                        zero_score_condition="触发严重红线。",
                        evidence_required="对话中可定位证据。",
                    ),
                    ScoringDimension(
                        dimension_id="expression",
                        name="表达质量",
                        weight=30,
                        description="表达是否自然简洁。",
                        full_score_standard="自然、简洁、给用户说话机会。",
                        partial_score_rules=["偶发冗长酌情扣分。"],
                        deduction_rules=["重复或过长扣分。"],
                        zero_score_condition="全程不可理解。",
                        evidence_required="对话轮次证据。",
                    ),
                ],
                veto_rules=[],
                risk_rules=[],
            )
        if task_name == "agent_turn":
            return AgentTurnOutput(
                visible_reply="您好，我简短说明这次外呼的核心事项。",
                agent_intent="开场并推进核心信息",
                referenced_knowledge=["K001"],
                risk_flags=[],
                internal_notes="fake output for graph validation",
            )
        if task_name == "user_turn":
            return UserTurnOutput(
                visible_reply="你先简单说重点，我听一下。",
                user_intent="要求简短说明",
                emotion="neutral",
                patience=68,
                state_delta=UserStateDelta(
                    understood_facts=[],
                    new_objections=[],
                    willingness="listening",
                ),
                should_end_candidate=False,
                end_reason_candidate="",
            )
        if task_name == "coverage_judge":
            return CoverageJudgeOutput(
                triggered_targets=[
                    CoverageEvidence(
                        label="C001",
                        confidence=0.8,
                        evidence="客服进行了开场并尝试确认任务相关事项。",
                        speaker="agent",
                    )
                ],
                missing_targets=["C002", "C003"],
                risk_flags=[],
            )
        if task_name == "case_evaluation":
            return CaseEvaluationDraft(
                dimension_scores=[
                    DimensionScore(
                        dimension_id="task_completion",
                        name="任务完成度",
                        weight=40,
                        score=30,
                        reason="客服触达了主要任务，但仍有细节可补。",
                        evidence=[
                            EvidenceQuote(
                                turn_index=0,
                                speaker="agent",
                                quote="您好，我简短说明这次外呼的核心事项。",
                                explanation="客服开始推进任务。",
                            )
                        ],
                        missing_points=["部分细节不足"],
                    ),
                    DimensionScore(
                        dimension_id="compliance",
                        name="合规性",
                        weight=30,
                        score=30,
                        reason="未发现明显合规风险。",
                        evidence=[],
                        missing_points=[],
                    ),
                    DimensionScore(
                        dimension_id="expression",
                        name="表达质量",
                        weight=30,
                        score=25,
                        reason="表达简洁，但对话推进仍可更充分。",
                        evidence=[],
                        missing_points=[],
                    ),
                ],
                veto_items=[],
                risk_deductions=[
                    RiskDeduction(
                        rule_id="generic_expression_gap",
                        description="表达或推进存在轻微不足。",
                        severity="low",
                        deduction=0,
                        evidence=[],
                    )
                ],
                final_comment="fake evaluation for graph validation",
            )
        raise ValueError(f"Unsupported fake LLM task: {task_name}")


def _messages_trace_payload(
    messages: list[dict[str, str]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    mode = _trace_message_mode()
    if mode == "full":
        return {
            **summary,
            "messages": messages,
        }
    if mode == "off":
        return summary
    return {
        **summary,
        "messages": [
            {
                "role": message.get("role", ""),
                "content_chars": len(str(message.get("content", ""))),
                "content_preview": _preview(str(message.get("content", "")), 240),
            }
            for message in messages
        ],
    }


def _completion_trace_payload(content: str) -> dict[str, Any] | str:
    mode = _trace_message_mode()
    if mode == "full":
        return content
    payload = {
        "completion_chars": len(content),
        "completion_hash": _text_hash(content),
    }
    if mode == "summary":
        payload["completion_preview"] = _preview(content, 300)
    return payload


def _message_summary(messages: list[dict[str, str]]) -> dict[str, Any]:
    serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "message_count": len(messages),
        "prompt_chars": sum(len(str(message.get("content", ""))) for message in messages),
        "prompt_hash": _text_hash(serialized),
    }


def _trace_message_mode() -> str:
    mode = os.getenv("DIALOGUE_EVAL_TRACE_LLM_MESSAGES", "summary").strip().lower()
    return mode if mode in {"summary", "full", "off"} else "summary"


def _preview(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"...<truncated {len(text) - max_chars} chars>"


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def role_config_or_default(config: ModelConfig, role: str) -> ModelRoleConfig:
    if role in config.models:
        return config.models[role]
    return config.models["asset_generator"]
