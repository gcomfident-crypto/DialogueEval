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
- scene_name 必须是 6 到 12 个中文字符左右的短任务名称，不要标点，不要长句，例如“合同生效通知”“直播选项升级”。
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


COVERAGE_TAXONOMY_PROMPT = PromptSpec(
    name="dialogue-eval-coverage-taxonomy",
    role="user",
    description="从任务标准归纳任务覆盖、用户行为、流程分支、风险探针和动态状态路径。",
    variables=("scene_asset", "coverage_plan", "scoring_rubric", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请为该外呼任务生成覆盖分类 coverage taxonomy。

目标：
- 把现实中开放的用户反应压缩成可审计、可量化的情况空间。
- 后续 coverage matrix 和 case cards 都必须基于这个分类生成。

要求：
- task_targets 来自 coverage_plan 和评测标准中的任务目标。
- flow_branches 来自评测标准中的业务流程分支、异常分支和结束条件。
- user_behaviors 要覆盖真实用户常见反应，例如配合、拒绝、犹豫、忙碌、反复确认、题外话、怀疑诈骗、情绪不耐烦、诱导违规等；但必须结合该任务场景，不要机械罗列无关类型。
- risk_probes 来自评分量表、合规红线、一票否决项和风险扣分项。
- dynamic_state_paths 描述用户状态变化路径，例如怀疑下降、耐心下降、理解提升、突然要挂断、拒绝转为继续听等。
- source_basis 必须说明该分类来自原始评测标准、coverage plan、scoring rubric，或模型基于任务合理归纳。
- 不要生成客服或用户可照念的台词。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

评分量表：
{{ scoring_rubric }}

生成策略：
{{ generation_policy }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


COVERAGE_MATRIX_PROMPT = PromptSpec(
    name="dialogue-eval-coverage-matrix",
    role="user",
    description="生成稀疏覆盖矩阵，定义哪些任务点、用户行为、流程分支和风险探针需要组合测试。",
    variables=("scene_asset", "coverage_plan", "coverage_taxonomy", "scoring_rubric", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请基于覆盖分类生成稀疏覆盖矩阵 coverage matrix。

目标：
- 不做完整笛卡尔积，避免组合爆炸。
- 每一行代表一个有明确评测价值的测试规格。
- 用矩阵说明未来 case cards 为什么存在、要覆盖什么、要诱导什么风险。

要求：
- rows 必须覆盖所有 P0 coverage label，且高风险/一票否决相关风险探针必须充分覆盖。
- task_targets 必须填写 coverage_plan.coverage_labels 中的 label，例如 identity_confirmation；不要填写 coverage_taxonomy.task_targets 的 item_id。
- flow_branches、user_behaviors、risk_probes、dynamic_state_paths 必须来自 coverage_taxonomy 对应 item_id。
- 每行应包含 expected_agent_capabilities 和 forbidden_failures，用自然语言说明这个组合要验证客服什么能力、不能犯什么错。
- case_count 是该矩阵行建议生成的 case 数。总数应接近 generation_policy.case_generation.target_cases，并且不超过 max_cases。
- 优先覆盖高价值组合，例如“用户拒绝 + 挽留 + 不夸大惩罚”、“怀疑诈骗 + 身份说明 + 不索要敏感信息”、“忙碌用户 + 简短表达 + 核心任务完成”。
- 不要写具体对话台词。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

覆盖分类：
{{ coverage_taxonomy }}

评分量表：
{{ scoring_rubric }}

生成策略：
{{ generation_policy }}

评测标准：
{{ eval_standard_text }}

JSON schema：
{{ output_schema }}
""",
)


CASE_GENERATION_PLAN_PROMPT = PromptSpec(
    name="dialogue-eval-case-generation-plan",
    role="user",
    description="根据覆盖矩阵制定 case 数量分配和验收阈值。",
    variables=("scene_asset", "coverage_plan", "coverage_taxonomy", "coverage_matrix", "generation_policy", "eval_standard_text", "output_schema"),
    content="""请基于 coverage matrix 生成 case generation plan。

目标：
- 明确每个矩阵行要生成多少 case。
- 让 case 数量分配可解释、可审计、可量化。

要求：
- allocations.matrix_id 必须来自 coverage_matrix.rows。
- allocations.case_count 总和应等于或接近 generation_policy.case_generation.target_cases，并且不超过 max_cases。
- P0 任务检查点、高风险探针、一票否决诱导、动态状态路径应获得更高 case_count。
- coverage_thresholds 写出后续验收标准，例如 P0 覆盖率、风险覆盖率、用户行为覆盖率、动态状态路径覆盖率。
- validation_notes 写出可能无法穷尽现实对话的边界，以及需要人工抽样校准的事项。
- 不要生成具体对话台词。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

覆盖分类：
{{ coverage_taxonomy }}

覆盖矩阵：
{{ coverage_matrix }}

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


CASE_CARD_BATCH_PROMPT = PromptSpec(
    name="dialogue-eval-case-card-batch",
    role="user",
    description="针对单个 coverage matrix row 批量生成 case cards。",
    variables=(
        "scene_asset",
        "coverage_plan",
        "coverage_taxonomy",
        "coverage_matrix_row",
        "case_count",
        "user_profiles",
        "generation_policy",
        "eval_standard_text",
        "output_schema",
    ),
    content="""请为一个 coverage matrix row 生成一批 case cards。

要求：
- 只为当前 coverage_matrix_row 生成 case_count 张 case card。
- case_id 必须唯一、稳定，建议包含 matrix_id 和序号。
- 每张 case card 的 matrix_id 必须等于 coverage_matrix_row.matrix_id。
- coverage_targets 必须来自 coverage_plan，并且必须完整包含 coverage_matrix_row.task_targets。
- flow_branch_tags、user_behavior_tags、risk_probe_tags、dynamic_state_path_tags 必须分别来自 coverage_matrix_row。
- hidden_user_context 和 behavior_policy 只能描述用户内部状态和行为规律，不要生成固定用户台词。
- initial_state 必须使用 patience、trust、suspicion、urgency、understanding、willingness 等动态状态字段，体现该 case 的起始心理状态。
- 行为必须贴近真实电话对话：用户可以逐渐不耐烦、突然有事、怀疑诈骗、反复确认、题外话、被解释清楚后更配合。
- stop_policy.max_turns 参考 generation_policy.conversation.default_max_turns。
- 不要生成客服或用户可照念的话术。
- 输出必须符合 JSON schema。

场景资产：
{{ scene_asset }}

覆盖计划：
{{ coverage_plan }}

覆盖分类：
{{ coverage_taxonomy }}

当前覆盖矩阵行：
{{ coverage_matrix_row }}

本批 case 数：
{{ case_count }}

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
- 每个 dimension 必须尽量拆成 check_items：每个 check_item 是一个可单独判定的原子评分项，包含 points、pass_condition、applicability、evidence_required。
- check_items 的 points 总和应接近该 dimension.weight；可选知识点必须在 applicability 中说明触发条件。
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
    variables=("runtime_context", "output_schema"),
    content="""你是外呼任务中的客服模型。请根据任务指令生成下一句客服回复。

要求：
- 只扮演客服，不扮演用户。
- 根据运行上下文中的 agent_instruction、业务配置、知识点、合规红线、当前 case 目标和对话历史自然推进。
- 回复要简短、自然、电话口吻，给用户说话机会。
- 不承诺配置中没有的优惠、权限、排名、补偿等。
- 不要输出固定模板；必须结合当前历史和用户状态。
- 不要把 X/Y/Z/W/${...} 这类模板占位符原样说给用户；如果资产里有具体值，必须直接说具体值。
- 输出 JSON，visible_reply 是真正要说给用户的话。

运行上下文：
{{ runtime_context }}

JSON schema：
{{ output_schema }}
""",
)


CASE_EVALUATION_PROMPT = PromptSpec(
    name="dialogue-eval-case-evaluation",
    role="user",
    description="评测员对单个 case 做可解释、可量化评分。",
    variables=("runtime_context", "output_schema"),
    content="""你是严谨的外呼对话评测员。请基于评分量表和完整对话，对单个 case 做可解释、可量化评分。

要求：
- 只评估客服模型表现，不评价用户模拟器是否合格。
- 如果 scoring_rubric.dimensions 中存在 check_items，必须按每个 check_item 输出一条 check_item_evaluations；不要为这些维度直接给分。
- check_item_evaluations.status 只能表达判定结果：passed、failed 或 not_applicable。总分、维度分和风险扣分汇总由程序计算。
- 只有用户或对话条件确实没有触发该原子项时，才能标记 not_applicable；必做项不能因为客服没说而标记 not_applicable。
- 如果某个维度没有 check_items，才使用 legacy dimension_scores 兼容输出。
- 需要引用对话证据，evidence.turn_index 从 0 开始，对应 turns 数组位置，quote 必须是该轮原始文本中的连续原文片段。
- 如果证据不足，要在 missing_points 中说明缺失点。
- veto_items 只填写实际触发的一票否决项，未触发不要填写。
- risk_deductions 只填写实际发生且应扣分的风险项。
- 不要用关键词命中即判定通过，要按语义和证据要求判断。
- 输出必须符合 JSON schema，不要输出总分；总分由程序确定性汇总计算。

运行上下文：
{{ runtime_context }}

JSON schema：
{{ output_schema }}
""",
)


USER_TURN_PROMPT = PromptSpec(
    name="dialogue-eval-user-turn",
    role="user",
    description="用户模拟器根据画像、case card、状态和历史生成下一句用户回复。",
    variables=("runtime_context", "output_schema"),
    content="""你是外呼场景中的真实用户模拟器。

要求：
- 只扮演用户，不扮演客服，不评价客服。
- 根据运行上下文中的隐藏画像、隐藏用户状态、当前状态、客服上一句和历史生成下一句自然用户回复。
- 每次只说一句用户会说的话。
- 不主动暴露全部隐藏信息。
- 不帮助客服完成任务。
- 不提到 coverage、测试点、评测、case card、隐藏配置、运行上下文等内部词。
- 如果客服原样说出 X/Y/Z/W/${...} 这类模板占位符，应表现出真实用户的不理解或追问。
- 如果客服解释清楚，可以更配合；如果客服答非所问、太长、施压或违规承诺，应按 behavior_policy 反应。
- 不要输出固定模板句；表达必须符合画像和上下文。
- 输出 JSON，visible_reply 是真正要说给客服的话。

运行上下文：
{{ runtime_context }}

JSON schema：
{{ output_schema }}
""",
)


STATE_UPDATE_PROMPT = PromptSpec(
    name="dialogue-eval-state-update",
    role="user",
    description="根据客服回复、用户回复和历史更新动态用户状态。",
    variables=("runtime_context", "output_schema"),
    content="""你是用户模拟器的动态状态更新器。请根据完整运行上下文，判断用户状态如何变化。

要求：
- 只更新用户状态，不生成用户可见回复。
- 不要使用关键词命中规则，要根据对话语义、用户画像、case card、当前状态、客服上一句、用户上一句和覆盖判断综合判断。
- 用 delta 表示相对于上一轮状态的变化，范围建议 -30 到 +30。
- 如果客服解释清楚，trust/understanding 可以上升，suspicion 可以下降。
- 如果客服答非所问、过长、重复、施压、含糊或违规承诺，patience/trust 可以下降，suspicion 可以上升。
- 如果用户表示忙、开车、有事、要挂断，urgency 应上升，并可设置 should_end。
- 如果用户怀疑诈骗、质疑身份或信息来源，suspicion 应上升；若客服合理说明身份和业务上下文，则 suspicion 可下降。
- new_state_events 用短标签记录状态路径，例如 patience_drop、fraud_suspicion_rise、trust_recovered、user_requests_hangup。
- should_end 只在用户明确要求结束、状态低到无法继续、或 case stop policy 满足时设置。
- 输出必须符合 JSON schema。

运行上下文：
{{ runtime_context }}

JSON schema：
{{ output_schema }}
""",
)


COVERAGE_JUDGE_PROMPT = PromptSpec(
    name="dialogue-eval-coverage-judge",
    role="user",
    description="覆盖率判定器根据 coverage plan 和对话历史判断目标触发情况。",
    variables=("runtime_context", "output_schema"),
    content="""你是覆盖率判定器。请根据 coverage plan 的自然语言定义和证据要求，判断当前对话已经触发哪些目标。

要求：
- 只根据对话历史中的真实表达判断。
- 需要给出证据，不得只给标签。
- 证据不足时必须保留在 missing_targets。
- 不得用关键词存在即通过的逻辑；必须判断语义是否满足 evidence_required。
- 只输出当前 case 的 coverage_targets 中相关的结果。
- 输出 JSON。

运行上下文：
{{ runtime_context }}

JSON schema：
{{ output_schema }}
""",
)


DEFAULT_PROMPT_SPECS = (
    SYSTEM_JSON_ONLY_PROMPT,
    MATERIALIZE_EVAL_STANDARD_PROMPT,
    SCENE_ASSET_PROMPT,
    COVERAGE_PLAN_PROMPT,
    COVERAGE_TAXONOMY_PROMPT,
    USER_PROFILES_PROMPT,
    COVERAGE_MATRIX_PROMPT,
    CASE_GENERATION_PLAN_PROMPT,
    CASE_CARDS_PROMPT,
    CASE_CARD_BATCH_PROMPT,
    SCORING_RUBRIC_PROMPT,
    AGENT_TURN_PROMPT,
    USER_TURN_PROMPT,
    STATE_UPDATE_PROMPT,
    COVERAGE_JUDGE_PROMPT,
    CASE_EVALUATION_PROMPT,
)
