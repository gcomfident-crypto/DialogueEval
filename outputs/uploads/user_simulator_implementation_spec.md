# 外呼对话 AI 用户模拟与客服生成组件实现规格说明

> 用途：把这份文档直接发给代码生成模型，让它按规格实现一个可扩展的“外呼任务对话仿真组件”。
> 核心思路：不要在代码里硬编码客服话术、用户话术、用户画像或固定场景卡。系统应以评测标准 Markdown 和业务配置为输入，通过 LLM 生成场景资产，再由 LangGraph 编排“AI 客服模型”和“AI 用户模型”自动对话，输出可追踪的日志、覆盖率和报告。

---

## 1. 目标与边界

实现一个 Python 组件，用于针对任意外呼任务评测标准自动生成用户模拟资产，并运行 AI 客服与 AI 用户的多轮对话。

必须支持以下输入方式：

```text
Resource/eval_standards/scene_1_eval_standard.md
Resource/eval_standards/scene_2_eval_standard.md
```

以后新增场景时，只需要提供类似的评测标准 Markdown 和可选业务配置，系统就能生成：

1. 场景元信息
2. 覆盖标签与覆盖计划
3. 用户画像集合
4. 场景卡片集合
5. 客服模型任务指令
6. 用户模拟器任务指令
7. 对话日志、覆盖报告和资产生成报告

严禁把当前两个场景、客服说法、用户说法、固定 case 表或 FAQ 答案写死在 Python 代码里。

---

## 2. 强制原则

1. **禁止硬编码话术**：客服回复、用户回复、开场白、追问、拒绝、忙碌、开车、投诉等内容都必须由模型根据配置和历史生成。
2. **禁止硬编码场景卡**：用户画像、case 数量、coverage_targets、trigger_plan、stop_condition 等必须由资产生成 LLM 基于评测标准生成，并落盘为 YAML 或 JSON。
3. **禁止把当前两个场景写进业务逻辑**：代码只能识别通用 schema，不得出现 `scene_1` 或 `scene_2` 的专属分支逻辑。
4. **尽量避免正则/模式匹配**：不要用正则或关键词匹配判断客服是否说到某点、用户是否触发某点。覆盖判断、状态判断、对话质量判断应优先通过 LLM 结构化判定完成。
5. **用户不是评委**：用户模型只扮演真实客户或骑手，不评价客服是否合格，不暴露覆盖标签、测试点、评测标准等内部信息。
6. **客服由 AI 生成**：客服模型根据任务指令、业务配置、对话历史生成下一句话，不允许用 stub 固定回复代替核心实现。测试中可以使用 fake LLM，但 fake 只能返回结构化样例，不能成为业务逻辑。
7. **先生成资产，再跑对话**：不能在对话运行时临时拼凑场景；必须先把可审计的场景资产写入配置文件，再由 runner 加载执行。
8. **所有模型输出必须结构化**：资产生成、用户回复、客服回复、覆盖判定、状态更新都要要求 LLM 输出合法 JSON，并做 schema 校验、重试和失败兜底。
9. **可复现**：资产生成和对话运行都要记录输入文件 hash、模型名、temperature、生成时间、版本号、随机种子或 run_id。
10. **组件化可扩展**：核心能力要封装成可被其他项目调用的 Python 包和 LangGraph workflow，而不仅是单个脚本。

---

## 3. 总体架构

```text
dialogue_simulator/
  __init__.py
  cli.py
  schemas.py
  llm_client.py
  structured_output.py
  asset_generator.py
  prompt_templates.py
  graph.py
  agent_model.py
  user_model.py
  coverage_judge.py
  state_updater.py
  report_exporter.py
  storage.py
configs/
  model_config.yaml
  generation_policy.yaml
  business_config.example.yaml
outputs/
  assets/
  runs/
tests/
  test_asset_generation.py
  test_graph_run.py
  test_schema_validation.py
```

运行分两阶段：

```text
阶段 A：资产生成
评测标准 Markdown + 业务配置
→ LLM 生成 scene_asset.yaml
→ LLM 生成 coverage_plan.yaml
→ LLM 生成 user_profiles.yaml
→ LLM 生成 case_cards.yaml
→ schema 校验与资产报告

阶段 B：对话仿真
加载生成资产
→ LangGraph 初始化对话状态
→ AI 客服生成下一句
→ AI 用户生成下一句
→ LLM 覆盖判定
→ LLM 状态更新
→ 判断是否结束
→ 导出日志与报告
```

---

## 4. LangGraph 流程要求

必须用 LangGraph 实现核心流程，至少包含两个 graph。

### 4.1 AssetGenerationGraph

节点：

1. `load_eval_standard`
   - 读取评测标准 Markdown。
   - 读取可选业务配置 YAML/JSON。
   - 计算输入 hash。

2. `generate_scene_brief`
   - LLM 从评测标准中生成通用场景摘要、业务目标、角色定义、合规红线、必备知识点。
   - 输出 `SceneAsset`。

3. `generate_coverage_plan`
   - LLM 根据评测标准生成 coverage labels。
   - 每个 label 要包含名称、自然语言定义、证据要求、适用触发条件。
   - 不允许代码内预置当前两个场景的标签。

4. `generate_user_profiles`
   - LLM 基于评测维度生成多样化用户画像。
   - 画像必须覆盖身份、状态、性格、认知、行为、语言风格、风险倾向。

5. `generate_case_cards`
   - LLM 根据场景摘要、覆盖计划、用户画像生成 case cards。
   - 每张卡要包含 `coverage_targets`、`hidden_user_context`、`initial_state`、`behavior_policy`、`stop_policy`。
   - case 数量由配置控制，不能写死。

6. `validate_assets`
   - 用 Pydantic 校验结构。
   - 如缺失必需字段，调用 LLM 修复一次；仍失败则报错。

7. `persist_assets`
   - 写入 YAML/JSON。
   - 记录生成元数据。

### 4.2 ConversationGraph

节点：

1. `initialize_case`
   - 加载一张生成的 case card。
   - 初始化 `ConversationState`。

2. `agent_turn`
   - AI 客服模型根据 `AgentInstruction`、业务配置、覆盖目标、对话历史生成下一句客服回复。
   - 输出 JSON：`visible_reply`、`agent_intent`、`referenced_knowledge`、`risk_flags`。
   - 客服回复不得由代码模板拼接。

3. `user_turn`
   - AI 用户模型根据隐藏场景卡、用户画像、状态、客服上一句、对话历史生成下一句用户回复。
   - 输出 JSON：`visible_reply`、`user_intent`、`emotion`、`patience`、`state_delta`、`should_end_candidate`。
   - 用户回复不得由代码模板拼接。

4. `coverage_judge`
   - LLM 根据对话历史和 coverage plan 判断每个 target 是否已有证据触发。
   - 输出 `triggered_targets`、`evidence`、`confidence`、`missing_targets`。
   - 禁止仅凭关键词、正则或固定模式匹配判断覆盖。

5. `state_update`
   - LLM 或结构化规则根据用户输出、覆盖判定、风险标记更新状态。
   - 允许做通用数值边界处理，如 patience 限制在 0-100；不得做场景专属硬编码。

6. `should_continue`
   - 根据 max_turns、用户是否明确结束、覆盖是否完成、风险是否需要继续追问判断是否结束。

7. `finalize_case`
   - 生成 `ConversationResult`。
   - 导出一行 JSONL 和覆盖汇总数据。

---

## 5. 配置文件要求

### 5.1 model_config.yaml

```yaml
default_provider: deepseek
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
models:
  asset_generator:
    provider: deepseek
    model: deepseek-chat
    temperature: 0.2
  agent:
    provider: deepseek
    model: deepseek-chat
    temperature: 0.5
  user:
    provider: deepseek
    model: deepseek-chat
    temperature: 0.8
  judge:
    provider: deepseek
    model: deepseek-chat
    temperature: 0.1
```

### 5.2 generation_policy.yaml

```yaml
asset_version: "1.0"
case_generation:
  min_cases: 12
  max_cases: 40
  p0_ratio: 0.45
  coverage_per_case_min: 2
  coverage_per_case_max: 6
  require_pairwise_diversity: true
conversation:
  default_max_turns: 12
  agent_reply_style: "短句、自然、电话口吻、给用户说话机会"
  user_reply_style: "符合画像，不泄露内部配置，不替客服完成任务"
validation:
  retry_on_invalid_json: 1
  retry_on_schema_error: 1
  min_coverage_label_count: 8
```

### 5.3 business_config.yaml

业务配置只能放可变业务变量、知识库补充、真实系统名等，不得放固定客服话术或固定用户话术。

```yaml
scene_id: auto_or_user_defined
business_variables:
  rider_name: 张师傅
  single_day_min_orders: 20
  multi_day_min_orders: 18
  continuous_days: 3
knowledge_overrides: []
forbidden_commitments: []
```

---

## 6. 生成资产 schema

### 6.1 SceneAsset

```json
{
  "scene_id": "auto_generated_scene_id",
  "scene_name": "",
  "source_eval_standard_path": "",
  "business_goal": "",
  "agent_role": "",
  "user_role": "",
  "success_definition": "",
  "knowledge_items": [
    {
      "id": "K001",
      "name": "",
      "content": "",
      "when_to_use": "",
      "business_variables": []
    }
  ],
  "compliance_rules": [
    {
      "id": "R001",
      "rule": "",
      "severity": "normal|critical",
      "negative_examples_description": ""
    }
  ],
  "agent_instruction": {
    "goal": "",
    "must_do": [],
    "must_not_do": [],
    "style": ""
  },
  "generation_metadata": {
    "model": "",
    "created_at": "",
    "input_hash": ""
  }
}
```

### 6.2 CoveragePlan

```json
{
  "scene_id": "",
  "coverage_labels": [
    {
      "label": "C001",
      "name": "",
      "definition": "",
      "evidence_required": "",
      "priority": "P0|P1|P2",
      "positive_evidence_examples_description": "",
      "negative_evidence_examples_description": ""
    }
  ]
}
```

`positive_evidence_examples_description` 只能描述证据类型，不得写成客服或用户可直接照念的话术。

### 6.3 UserProfile

```json
{
  "profile_id": "U001",
  "identity": "",
  "role": "",
  "current_context": "",
  "personality": "",
  "communication_style": "",
  "knowledge_level": "",
  "wrong_beliefs": [],
  "risk_tendency": "",
  "cooperation_curve": ""
}
```

### 6.4 CaseCard

```json
{
  "case_id": "CASE_001",
  "scene_id": "",
  "case_name": "",
  "priority": "P0|P1|P2",
  "profile_id": "U001",
  "coverage_targets": ["C001", "C002"],
  "hidden_user_context": {
    "known_facts": [],
    "unknown_facts": [],
    "wrong_beliefs": [],
    "private_goal": "",
    "main_objection": ""
  },
  "initial_state": {
    "emotion": "neutral",
    "patience": 70,
    "busy_level": "",
    "environment": "",
    "willingness": "unknown"
  },
  "behavior_policy": {
    "disclosure_policy": "",
    "if_agent_clear": "",
    "if_agent_wrong": "",
    "if_agent_too_long": "",
    "if_agent_pushy": "",
    "if_agent_violates_rule": ""
  },
  "stop_policy": {
    "max_turns": 12,
    "success_end": "",
    "forced_end": ""
  }
}
```

---

## 7. 模型输出 schema

### 7.1 客服模型输出

```json
{
  "visible_reply": "",
  "agent_intent": "",
  "referenced_knowledge": [],
  "risk_flags": [],
  "internal_notes": ""
}
```

发给用户模型的只有 `visible_reply` 和对话历史；`internal_notes` 只写入内部日志，不得暴露给用户。

### 7.2 用户模型输出

```json
{
  "visible_reply": "",
  "user_intent": "",
  "emotion": "",
  "patience": 0,
  "state_delta": {
    "understood_facts": [],
    "new_objections": [],
    "willingness": ""
  },
  "should_end_candidate": false,
  "end_reason_candidate": ""
}
```

### 7.3 覆盖判定输出

```json
{
  "triggered_targets": [
    {
      "label": "C001",
      "confidence": 0.0,
      "evidence": "第几轮哪一方表达了什么含义",
      "speaker": "agent|user|both"
    }
  ],
  "missing_targets": ["C002"],
  "risk_flags": [
    {
      "rule_id": "R001",
      "severity": "critical",
      "evidence": ""
    }
  ]
}
```

---

## 8. Prompt 设计要求

Prompt 必须集中放在 `prompt_templates.py` 或 YAML 配置中，不允许散落在业务逻辑里。

### 8.1 资产生成 Prompt

资产生成模型必须被明确要求：

- 只从评测标准和业务配置中抽取或合理归纳，不编造未给出的业务规则。
- 输出合法 JSON。
- 生成的是可执行的模拟资产，不是评测报告摘要。
- 用户画像与 case card 要多样化，覆盖身份、状态、性格、认知、行为、语言风格和风险倾向。
- 不生成客服或用户可直接照念的固定话术。

### 8.2 客服模型 Prompt

客服模型必须被明确要求：

- 只扮演客服。
- 根据 `agent_instruction`、业务配置、知识点、合规红线和对话历史生成下一句。
- 话术自然、简短、可被打断。
- 不承诺配置中没有的优惠、权限、排名、补偿等。
- 输出 JSON，不输出分析过程。

### 8.3 用户模型 Prompt

用户模型必须被明确要求：

- 只扮演用户。
- 根据隐藏画像、case card、当前状态和对话历史生成下一句。
- 不主动暴露全部隐藏信息。
- 不帮客服完成任务。
- 不提到 coverage、测试点、评测、case card 等内部词。
- 不输出固定模板句；表达必须符合画像和上下文。
- 输出 JSON，不输出分析过程。

### 8.4 覆盖判定 Prompt

覆盖判定模型必须被明确要求：

- 根据 coverage label 的自然语言定义和证据要求判定。
- 需要给出证据，不得只给标签。
- 证据不足时标为 missing。
- 不使用关键词存在即通过的逻辑。

---

## 9. 状态更新规则

状态 schema：

```json
{
  "turn_index": 0,
  "emotion": "neutral",
  "patience": 70,
  "understood_facts": [],
  "active_objections": [],
  "triggered_targets": [],
  "risk_flags": [],
  "willingness": "unknown",
  "should_end": false,
  "end_reason": ""
}
```

状态更新应由 `state_update` 节点综合以下信息完成：

- 用户模型输出的 `state_delta`
- 覆盖判定输出
- 风险标记
- max_turns
- stop_policy

可以使用通用数值规则做边界修正，例如 patience 必须在 0 到 100 之间。不得写入某个场景专属的 if/else。

---

## 10. 输出文件

### 10.1 资产输出

```text
outputs/assets/{scene_id}/scene_asset.yaml
outputs/assets/{scene_id}/coverage_plan.yaml
outputs/assets/{scene_id}/user_profiles.yaml
outputs/assets/{scene_id}/case_cards.yaml
outputs/assets/{scene_id}/asset_generation_report.md
```

### 10.2 对话日志

`conversation_log.jsonl` 每个 case 一行：

```json
{
  "run_id": "",
  "case_id": "",
  "scene_id": "",
  "planned_targets": [],
  "triggered_targets": [],
  "missing_targets": [],
  "coverage_success": true,
  "turns": [
    {
      "role": "agent",
      "text": "",
      "intent": "",
      "risk_flags": []
    },
    {
      "role": "user",
      "text": "",
      "intent": "",
      "emotion": "",
      "patience": 70
    }
  ],
  "coverage_evidence": [],
  "end_reason": ""
}
```

### 10.3 覆盖报告

`coverage_report.csv` 字段：

```text
run_id,case_id,scene_id,priority,planned_targets,triggered_targets,missing_targets,coverage_success,turns_count,end_reason
```

### 10.4 Markdown 汇总

必须包含：

```text
总 case 数
成功完成对话数
每个 scene 的覆盖率
P0 场景通过率
未触发 coverage_targets 列表
风险标记列表
需要补测的 case_id
资产来源与模型配置
```

---

## 11. CLI 要求

必须提供两个入口。

### 11.1 生成场景资产

```bash
python -m dialogue_simulator.cli generate-assets \
  --eval-standard Resource/eval_standards/scene_1_eval_standard.md \
  --business-config configs/business_config.example.yaml \
  --generation-policy configs/generation_policy.yaml \
  --output outputs/assets
```

### 11.2 运行对话仿真

```bash
python -m dialogue_simulator.cli run \
  --assets outputs/assets/{scene_id} \
  --limit 10 \
  --output outputs/runs
```

### 11.3 本地测试模式

允许 `--fake-llm` 用于单元测试，但 fake LLM 只能服务于测试 schema、图节点流转和文件导出：

- 不得把 fake LLM 设计为当前两个场景的业务替身。
- 不得在 fake LLM 中硬编码客服/用户话术。
- fake 输出只能是最小合法结构，测试真实生成质量时必须使用真实 LLM。

---

## 12. 最小实现伪代码

```python
def generate_assets(eval_standard_path, business_config_path, generation_policy_path):
    graph = build_asset_generation_graph()
    result = graph.invoke({
        "eval_standard_path": eval_standard_path,
        "business_config_path": business_config_path,
        "generation_policy_path": generation_policy_path,
    })
    return result["asset_dir"]


def run_conversations(asset_dir, limit=None):
    assets = load_generated_assets(asset_dir)
    graph = build_conversation_graph()
    results = []

    for case_card in assets.case_cards[:limit]:
        result = graph.invoke({
            "scene_asset": assets.scene_asset,
            "coverage_plan": assets.coverage_plan,
            "user_profiles": assets.user_profiles,
            "case_card": case_card,
            "conversation_state": init_state(case_card),
        })
        results.append(result["conversation_result"])

    export_reports(results)
    return results
```

---

## 13. 验收标准

代码完成后至少满足：

1. 能从 `Resource/eval_standards/scene_1_eval_standard.md` 生成完整资产文件。
2. 能从 `Resource/eval_standards/scene_2_eval_standard.md` 生成完整资产文件。
3. 新增任意同结构评测标准 Markdown 时，不需要改 Python 代码即可生成新场景资产。
4. 生成的用户画像和 case card 来自 LLM 输出，并落盘为 YAML 或 JSON。
5. 客服每轮回复由 AI 生成，不存在当前场景专属固定话术分支。
6. 用户每轮回复由 AI 生成，不存在当前场景专属固定话术分支。
7. 覆盖判定由 LLM 结构化完成，不依赖关键词正则或场景专属模式匹配。
8. 所有 LLM 输出均经过 JSON 解析、schema 校验、失败重试和错误报告。
9. LangGraph 中能清晰看到资产生成和对话运行节点。
10. 能导出 JSONL、CSV、Markdown 三种运行报告。
11. 单元测试覆盖 schema 校验、graph 节点流转、报告导出、fake LLM 模式。
12. README 包含资产生成、对话运行、模型配置、新场景接入方法。

---

## 14. 明确禁止的实现方式

以下实现不合格：

1. 在 `agent_client.py` 中按 coverage target 返回固定客服句子。
2. 在 `user_simulator.py` 中按 case_id 或 target 返回固定用户句子。
3. 在代码中写死 `S1_`、`S2_` 标签含义或两个场景的 FAQ。
4. 用正则或关键词匹配代替 LLM 覆盖判定。
5. 把 55 个 case 直接写入 `case_library.json` 作为主要实现。
6. 只实现 dry-run，不接真实 LLM。
7. 运行时不落盘资产，导致场景卡不可审计。
8. 用户回复出现“测试点、coverage、评测、场景卡”等内部词。

---

## 15. 给代码生成模型的最终指令

请根据本规格实现一个 Python + LangGraph 的外呼对话仿真组件。不要只写思路，要输出完整代码文件结构。实现必须以“评测标准 Markdown → LLM 生成场景资产 → LangGraph 驱动 AI 客服与 AI 用户对话 → LLM 覆盖判定 → 报告导出”为主线。严禁硬编码客服话术、用户话术、用户画像、场景卡和当前两个场景的业务分支。代码需能本地运行，包含 README、示例配置、示例命令和最小单元测试。
