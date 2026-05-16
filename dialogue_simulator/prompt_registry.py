from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSpec:
    name: str
    role: str
    content: str
    description: str
    variables: tuple[str, ...] = ()


SYSTEM_JSON_ONLY = "你必须只输出合法 JSON，不输出解释、代码块或分析过程。"


SYSTEM_JSON_ONLY_PROMPT = PromptSpec(
    name="dialogue-eval-system-json-only",
    role="system",
    content=SYSTEM_JSON_ONLY,
    description="所有结构化输出任务共用的 system prompt。",
)


SCENE_ASSET_PROMPT = PromptSpec(
    name="dialogue-eval-scene-asset",
    role="user",
    description="从评测标准和业务配置生成场景资产 scene_asset。",
    variables=("input_hash", "business_config", "eval_standard_text", "output_schema"),
    content="""请基于下面的外呼任务评测标准和业务配置，生成可执行的场景资产。

要求：
- 只从评测标准和业务配置中抽取或合理归纳，不编造未给出的业务规则。
- 不要生成客服或用户可照念的固定话术。
- 不要依赖当前场景名称的硬编码，输出应适用于通用对话仿真组件。
- knowledge_items 应覆盖任务知识、分支处理和合规红线中可供客服使用的事实。
- compliance_rules 应覆盖一票否决项和禁止项。
- scene_id 可根据场景名称或业务目标生成稳定、简短的英文/拼音标识。
- generation_metadata.input_hash 必须填写：{{ input_hash }}
- 输出必须符合 JSON schema。

业务配置：
{{ business_config }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


MATERIALIZE_EVAL_STANDARD_PROMPT = PromptSpec(
    name="dialogue-eval-materialize-eval-standard",
    role="user",
    description="将评测标准中的 X/Y/Z/W/${...} 等模板变量实例化为固定业务值。",
    variables=("business_config", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请把下面的外呼任务评测标准中的模板占位变量实例化为固定业务值。

目标：
- 后续场景资产、客服模型、用户模型和评测模型都只能看到自然、具体、可理解的任务内容。
- 不要让客服或用户在对话中看到 X/Y/Z/W/${...} 这类占位符。

要求：
- 优先使用业务配置 business_variables 中已有的变量值。
- 对评测标准中会被客服说出、会影响用户理解或会参与评测的占位变量，生成固定且前后一致的自然值。
- 数量、天数、时间点、金额、姓名、机构名等模板变量都要实例化成合理示例值。
- 不改变原任务流程、约束、合规红线和评分意图。
- 不生成客服或用户可照念的新话术，只替换原文中的变量并保留 Markdown 结构。
- 如果某个占位符确实必须保留，放入 unresolved_placeholders 并说明原因；否则不要保留占位符。
- assignments 记录每个占位符被替换成什么值，以及它的用途。
- 输出必须符合 JSON schema。

业务配置：
{{ business_config }}

生成策略：
{{ generation_policy }}

评测标准原文：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


COVERAGE_PLAN_PROMPT = PromptSpec(
    name="dialogue-eval-coverage-plan",
    role="user",
    description="为场景生成 coverage plan。",
    variables=("scene_asset", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请为该外呼任务生成覆盖计划 coverage plan。

要求：
- coverage label 必须来自评测标准中的任务目标、流程、知识点、异常分支、合规红线和表达质量要求。
- label 命名必须通用稳定，不要假设代码里有任何预置标签。
- evidence_required 要写清楚判定通过需要看到的自然语言证据。
- positive_evidence_examples_description 只能描述证据类型，不得写成可照念话术。
- 不要使用关键词命中即通过的标准。
- 输出 label 数量要满足 generation_policy.validation.min_coverage_label_count。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

生成策略：
{{ generation_policy }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


USER_PROFILES_PROMPT = PromptSpec(
    name="dialogue-eval-user-profiles",
    role="user",
    description="为场景生成用户画像集合。",
    variables=("scene_asset", "coverage_plan", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请生成该外呼任务的用户画像集合。

要求：
- 用户画像由模型生成，不能照抄固定 case。
- 画像要覆盖身份、状态、性格、认知、行为、语言风格、风险倾向。
- 要包含配合、忙碌、困惑、质疑、拒绝、诱导违规等多样类型，但不要写具体对话台词。
- 每个 profile_id 必须唯一。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

生成策略：
{{ generation_policy }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


CASE_CARDS_PROMPT = PromptSpec(
    name="dialogue-eval-case-cards",
    role="user",
    description="基于 coverage plan 和用户画像生成 case cards。",
    variables=(
        "scene_asset",
        "coverage_plan",
        "user_profiles",
        "generation_policy",
        "eval_standard_text",
        "output_schema",
    ),
    content="""请生成该外呼任务的 case cards。

要求：
- case cards 必须基于 coverage plan 和 user profiles 生成，不得使用预置场景表。
- 每张 case card 必须有 coverage_targets，且 targets 必须来自 coverage_plan。
- case 数量应在 generation_policy.case_generation.min_cases 与 max_cases 之间。
- 优先覆盖 P0 标签，同时保证身份、状态、性格、认知、行为和语言风格多样。
- hidden_user_context 和 behavior_policy 只能描述用户内部状态与行为规律，不要生成固定用户台词。
- stop_policy.max_turns 参考 generation_policy.conversation.default_max_turns。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

用户画像：
{{ user_profiles }}

生成策略：
{{ generation_policy }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


SCORING_RUBRIC_PROMPT = PromptSpec(
    name="dialogue-eval-scoring-rubric",
    role="user",
    description="基于评测标准生成 scoring rubric。",
    variables=("scene_asset", "coverage_plan", "eval_standard_text", "output_schema"),
    content="""请基于外呼任务评测标准生成可执行的评分量表 scoring rubric。

要求：
- 评分量表必须来自评测标准中的权重、合格阈值、一票否决项、扣分规则和检查清单。
- 如果评测标准中已有明确权重，例如任务完成度30分、流程执行25分，应按原文保留。
- 如果评测标准有模糊扣分规则，要归纳成可执行的自然语言规则，不要编造业务事实。
- dimensions 的 weight 总和应接近 total_score。
- veto_rules 只放一票否决项或严重合规红线。
- risk_rules 放可扣分但不一定一票否决的风险项。
- 不要生成客服或用户可直接照念的话术。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


AGENT_TURN_PROMPT = PromptSpec(
    name="dialogue-eval-agent-turn",
    role="user",
    description="客服模型根据任务资产和对话历史生成下一句客服回复。",
    variables=(
        "scene_asset",
        "coverage_plan",
        "case_card",
        "business_config",
        "conversation_state",
        "history",
        "output_schema",
    ),
    content="""你是外呼任务中的客服模型。请根据任务指令生成下一句客服回复。

要求：
- 只扮演客服，不扮演用户。
- 根据 agent_instruction、业务配置、知识点、合规红线、coverage plan 和对话历史自然推进。
- 回复要简短、自然、电话口吻，给用户说话机会。
- 不承诺配置中没有的优惠、权限、排名、补偿等。
- 不要输出固定模板；必须结合当前历史和用户状态。
- 不要把 X/Y/Z/W/${...} 这类模板占位符原样说给用户；如果资产里有具体值，必须直接说具体值。
- 输出 JSON，visible_reply 是真正要说给用户的话。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

当前 case：
{{ case_card }}

业务配置：
{{ business_config }}

对话状态：
{{ conversation_state }}

对话历史：
{{ history }}

JSON schema：
{{ output_schema }}
""",
)


CASE_EVALUATION_PROMPT = PromptSpec(
    name="dialogue-eval-case-evaluation",
    role="user",
    description="评测员对单个 case 做可解释、可量化评分。",
    variables=(
        "eval_standard_text",
        "scene_asset",
        "coverage_plan",
        "scoring_rubric",
        "business_config",
        "conversation_result",
        "output_schema",
    ),
    content="""你是严谨的外呼对话评测员。请基于评分量表和完整对话，对单个 case 做可解释、可量化评分。

要求：
- 只评估客服模型表现，不评价用户模拟器是否合格。
- 必须按 scoring_rubric.dimensions 逐项打分，每个维度都要输出一条 dimension_scores。
- 每个维度 score 必须在 0 到该维度 weight 之间。
- 需要引用对话证据，evidence.turn_index 从 0 开始，对应 turns 数组位置。
- 如果证据不足，要在 missing_points 中说明缺失点。
- veto_items 只填写实际触发的一票否决项，未触发不要填写。
- risk_deductions 只填写实际发生且应扣分的风险项。
- 不要用关键词命中即判定通过，要按语义和证据要求判断。
- 输出必须符合 JSON schema，不要输出总分；总分由程序汇总计算。

评测标准原文：
{{ eval_standard_text }}

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

评分量表：
{{ scoring_rubric }}

业务配置：
{{ business_config }}

单 case 对话结果：
{{ conversation_result }}

JSON schema：
{{ output_schema }}
""",
)


USER_TURN_PROMPT = PromptSpec(
    name="dialogue-eval-user-turn",
    role="user",
    description="用户模拟器根据画像、case card、状态和历史生成下一句用户回复。",
    variables=("scene_asset", "user_profile", "case_card", "conversation_state", "history", "output_schema"),
    content="""你是外呼场景中的真实用户模拟器。

要求：
- 只扮演用户，不扮演客服，不评价客服。
- 根据隐藏画像、case card、当前状态、客服上一句和完整历史生成下一句自然用户回复。
- 每次只说一句用户会说的话。
- 不主动暴露全部隐藏信息。
- 不帮助客服完成任务。
- 不提到 coverage、测试点、评测、case card、隐藏配置等内部词。
- 如果客服原样说出 X/Y/Z/W/${...} 这类模板占位符，应表现出真实用户的不理解或追问。
- 如果客服解释清楚，可以更配合；如果客服答非所问、太长、施压或违规承诺，应按 behavior_policy 反应。
- 不要输出固定模板句；表达必须符合画像和上下文。
- 输出 JSON，visible_reply 是真正要说给客服的话。

场景资产：
{{ scene_asset }}

隐藏用户画像：
{{ user_profile }}

隐藏 case card：
{{ case_card }}

当前用户状态：
{{ conversation_state }}

对话历史：
{{ history }}

JSON schema：
{{ output_schema }}
""",
)


COVERAGE_JUDGE_PROMPT = PromptSpec(
    name="dialogue-eval-coverage-judge",
    role="user",
    description="覆盖率判定器根据 coverage plan 和对话历史判断目标触发情况。",
    variables=(
        "coverage_plan",
        "scene_asset",
        "case_card",
        "current_triggered_targets",
        "history",
        "output_schema",
    ),
    content="""你是覆盖率判定器。请根据 coverage plan 的自然语言定义和证据要求，判断当前对话已经触发哪些目标。

要求：
- 只根据对话历史中的真实表达判断。
- 需要给出证据，不得只给标签。
- 证据不足时必须保留在 missing_targets。
- 不得用关键词存在即通过的逻辑；必须判断语义是否满足 evidence_required。
- 只输出当前 case 的 coverage_targets 中相关的结果。
- 输出 JSON。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

当前 case：
{{ case_card }}

当前已触发目标：
{{ current_triggered_targets }}

对话历史：
{{ history }}

JSON schema：
{{ output_schema }}
""",
)


DEFAULT_PROMPT_SPECS = (
    SYSTEM_JSON_ONLY_PROMPT,
    MATERIALIZE_EVAL_STANDARD_PROMPT,
    SCENE_ASSET_PROMPT,
    COVERAGE_PLAN_PROMPT,
    USER_PROFILES_PROMPT,
    CASE_CARDS_PROMPT,
    SCORING_RUBRIC_PROMPT,
    AGENT_TURN_PROMPT,
    USER_TURN_PROMPT,
    COVERAGE_JUDGE_PROMPT,
    CASE_EVALUATION_PROMPT,
)
