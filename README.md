# DialogueEval

外呼任务对话仿真组件。系统以评测标准 Markdown 为输入，先由 LLM 生成场景资产，再用 LangGraph 编排 AI 客服与 AI 用户进行多轮对话，并导出覆盖率报告与量化评分报告。

核心约束：

- Python 代码不硬编码客服话术、用户话术、用户画像、固定 case 或当前两个场景的业务分支。
- 用户画像、覆盖计划、场景卡片都由 LLM 从评测标准生成，并落盘为可审计 YAML/JSON。
- 客服回复、用户回复和覆盖判定均走 LLM 结构化输出。
- 覆盖判定不依赖关键词正则或场景专属模式匹配。

## 安装

```bash
pip install -r requirements.txt
```

真实模型调用默认使用 DeepSeek OpenAI 兼容接口：

```bash
export DEEPSEEK_API_KEY="your_api_key"
```

## WebUI 与 Docker Compose

本项目提供一个中期可展示版本：

- `apps/api`：FastAPI 后端，负责资产生成、运行评测、报告读取和文件上传。
- `apps/web`：Next.js 展示端，负责工作台、新建评测、报告中心、场景资产、实验库和系统设置。
- `docker-compose.yml`：一键启动 Postgres、Phoenix、API 与 WebUI。

推荐使用 Docker Compose 启动：

```bash
docker compose up --build
```

如果需要本地开发前端，可以单独启动 API 和 Next.js：

```bash
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
cd apps/web
npm install
npm run dev -- --hostname 127.0.0.1 --port 8501
```

Compose 会启动：

- `postgres`：Phoenix 的持久化数据库，默认创建 `phoenix` 和预留的 `dialogue_eval` 数据库。
- `phoenix`：Trace、Prompts 和调试 UI，默认使用 `PHOENIX_SQL_DATABASE_URL` 连接 Postgres。
- `api`：DialogueEval FastAPI 服务，默认维护 `outputs/dialogue_eval_registry.sqlite3` 作为业务实验注册表。
- `web`：Next.js 展示端，通过 `/api/backend/*` 代理访问 FastAPI。

访问：

- API 文档：http://127.0.0.1:8000/docs
- WebUI：http://127.0.0.1:8501
- Phoenix Trace UI：http://127.0.0.1:6006

WebUI 只需要上传任务模板文件。系统会自动识别 Markdown、CSV 或 Excel；CSV/Excel 默认读取第 2 列、第 2 行之后的 Markdown。

同一份任务模板会按输入内容 hash 复用已有资产目录；重复上传或重复生成时会更新原资产，不会再新增一个同任务场景。

## Phoenix Trace

Docker Compose 会同时启动 `postgres`、`phoenix`、`api`、`web` 四个服务。API 默认开启 tracing，并把 trace 发送到 Phoenix：

```text
PHOENIX_SQL_DATABASE_URL=postgresql://dialogueeval:dialogueeval@postgres:5432/phoenix
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006/v1/traces
PHOENIX_PROJECT_NAME=dialogue-eval
DIALOGUE_EVAL_TRACING_ENABLED=true
```

在 Phoenix 里可以看到：

- `api.generate_assets`：WebUI/API 发起的一次资产生成。
- `asset.*`：评测标准读取、变量实例化、场景资产、覆盖计划、用户画像、case card、评分规则、资产落盘。
- `api.run_evaluation`：一次完整评测运行。
- `case.run`：单个 case 的运行根节点。
- `conversation.*`：AI 客服轮次、AI 用户轮次、coverage judge、状态更新、case 收尾。
- `case.evaluate` 和 `evaluation.*`：单 case 评分、维度评分聚合。
- `llm.*`：所有模型调用，包含 task、role、model、latency、token 统计、输入输出摘要、字符数和 hash。

LLM trace 默认使用摘要模式，Phoenix 里展示每条 message 的角色、长度、短预览和 `prompt_hash`，避免把完整大段提示词铺在 trace 页面里。模型真实收到的 prompt 不受影响。

```bash
# summary: 默认摘要；full: 记录完整 messages；off: 只记录长度和 hash
DIALOGUE_EVAL_TRACE_LLM_MESSAGES=summary docker compose up --build
```

如果不想采集提示词和模型输出内容，可以关闭内容采集：

```bash
DIALOGUE_EVAL_TRACE_CONTENT=false docker compose up --build
```

本地非 Docker 启动时，设置以下环境变量即可把 CLI 或 API trace 发到本机 Phoenix：

```bash
export DIALOGUE_EVAL_TRACING_ENABLED=true
export PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
export PHOENIX_PROJECT_NAME=dialogue-eval
```

## DialogueEval 实验库

Phoenix 用来观察 trace 和管理 prompt；DialogueEval 自己维护业务实验注册表，用于复现和汇总。

默认数据库：

```text
outputs/dialogue_eval_registry.sqlite3
```

核心实体：

```text
datasets              # 上传的 CSV/Excel/Markdown 输入文件
task_instructions     # 每一条 Markdown 任务指令，按内容 hash 去重
asset_versions        # 由任务指令生成的 scene_asset/coverage_plan/user_profiles/case_cards/scoring_rubric 资产版本
experiments           # 一次批量或单场景运行
case_runs             # 每个 case 的对话和评分结果
llm_calls             # 每次模型调用的摘要、token、hash、成功/失败信息
```

运行时会把 `experiment_id`、`asset_version_id`、`run_id`、`case_id`、`scene_id` 写入 Phoenix trace metadata。WebUI 的“实验库”页面可查看 registry 中沉淀的数据。

## Phoenix Datasets

Phoenix Dataset 在本项目里分成两类使用，避免把可复现输入和一次运行结果混在一起：

```text
dialogueeval_case_seeds_{scene_id}
  # 主数据集。每条 example 是评测输入：case card、用户画像、覆盖目标、资产版本引用。
  # 不包含客服输出和评分，适合后续更换模型或 prompt 后重新批量实验。

dialogueeval_generated_dialogues_{scene_id}
  # 归档数据集。每条 example 保存一次 experiment 生成的完整对话和评分结果。
  # 适合人工标注、judge 校准、失败案例复盘，不作为主 benchmark 输入集。
```

WebUI 新建评测页默认提供两个开关：

- `发布 case seed 输入集`：在生成测试设计后写入 Phoenix Dataset。
- `归档生成对话`：在完整评测结束后把对话和评分另存为 Phoenix Dataset 版本。

API 也提供独立入口：

```bash
curl -X POST http://127.0.0.1:8000/phoenix/datasets/case-seeds \
  -H 'Content-Type: application/json' \
  -d '{"scene_id":"feimaotui_contract_notify","limit":100}'

curl -X POST http://127.0.0.1:8000/phoenix/datasets/generated-dialogues \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"run_xxx"}'
```

## Phoenix Prompts

项目提示词可以同步到 Phoenix Prompts 做版本管理。Docker Compose 下 API 默认启用 Phoenix prompt provider：

```text
DIALOGUE_EVAL_PROMPTS_PROVIDER=phoenix
PHOENIX_BASE_URL=http://phoenix:6006
DIALOGUE_EVAL_PROMPT_CACHE_SECONDS=30
```

同步默认提示词：

```bash
python -m dialogue_simulator.cli sync-prompts \
  --phoenix-base-url http://127.0.0.1:6006 \
  --model-name deepseek-chat
```

也可以在 WebUI 的“提示词”页面点击“同步默认提示词到 Phoenix”。

同步后 Phoenix 中会出现这些 prompt：

```text
dialogue-eval-system-json-only
dialogue-eval-materialize-eval-standard
dialogue-eval-scene-asset
dialogue-eval-coverage-plan
dialogue-eval-user-profiles
dialogue-eval-case-cards
dialogue-eval-scoring-rubric
dialogue-eval-agent-turn
dialogue-eval-user-turn
dialogue-eval-coverage-judge
dialogue-eval-case-evaluation
```

运行时会优先按 prompt name 从 Phoenix 拉取最新版；Phoenix 不可用或指定 prompt 缺失时，默认回退到代码内置模板。若希望缺失时直接失败，可以设置：

```bash
export DIALOGUE_EVAL_PROMPTS_STRICT=true
```

Phoenix prompt 模板使用 Mustache 变量。在 Phoenix 上编辑提示词时，应保留当前 prompt 所需变量名，否则运行时对应内容会渲染为空。

运行时对话和评测类 prompt 已通过 `dialogue_simulator/runtime_context.py` 先编译为角色相关上下文：

- `dialogue-eval-agent-turn`、`dialogue-eval-user-turn`、`dialogue-eval-coverage-judge`、`dialogue-eval-case-evaluation` 使用 `{{ runtime_context }}` 和 `{{ output_schema }}`。
- 资产生成类 prompt 仍使用各自的资产生成变量，例如 `{{ eval_standard_text }}`、`{{ scene_asset }}`、`{{ coverage_plan }}`。
- 用户模型的 `runtime_context` 不包含 coverage targets，客服模型只拿当前 case 需要推进的目标定义，judge 只拿当前 case 的目标定义和对话证据。

## 生成场景资产

方式一：直接使用 Markdown 评测标准：

```bash
python -m dialogue_simulator.cli generate-assets \
  --eval-standard Resource/eval_standards/scene_1_eval_standard.md \
  --business-config configs/business_config.example.yaml \
  --generation-policy configs/generation_policy.yaml \
  --output outputs/assets
```

方式二：从 Excel 第 2 列、第 2 行开始批量抽取 Markdown 评测标准并生成资产：

```bash
python -m dialogue_simulator.cli generate-assets \
  --eval-standard-excel 命题二：外呼任务对话模型指令示例.xlsx \
  --excel-column 2 \
  --excel-start-row 2 \
  --business-config configs/business_config.example.yaml \
  --generation-policy configs/generation_policy.yaml \
  --output outputs/assets
```

只抽取 Excel 中的 Markdown，不生成资产：

```bash
python -m dialogue_simulator.cli extract-eval-standards \
  --excel 命题二：外呼任务对话模型指令示例.xlsx \
  --output-dir outputs/extracted_eval_standards
```

输出：

```text
outputs/assets/{scene_id}/scene_asset.yaml
outputs/assets/{scene_id}/coverage_plan.yaml
outputs/assets/{scene_id}/user_profiles.yaml
outputs/assets/{scene_id}/case_cards.yaml
outputs/assets/{scene_id}/scoring_rubric.yaml
outputs/assets/{scene_id}/materialized_eval_standard.md
outputs/assets/{scene_id}/variable_assignments.yaml
outputs/assets/{scene_id}/asset_generation_report.md
```

## 运行对话仿真

```bash
python -m dialogue_simulator.cli run \
  --assets outputs/assets/{scene_id} \
  --limit 10 \
  --output outputs/runs
```

输出：

```text
outputs/runs/{run_id}/conversation_log.jsonl
outputs/runs/{run_id}/coverage_report.csv
outputs/runs/{run_id}/summary_report.md
outputs/runs/{run_id}/case_evaluation.jsonl
outputs/runs/{run_id}/evaluation_report.csv
outputs/runs/{run_id}/evaluation_report.md
outputs/runs/{run_id}/case_reports/{case_id}.md
outputs/runs/{run_id}/llm_calls.jsonl
```

`run_id` 使用可读格式，例如 `run_20260516_114436_meituan_feimaotui_contract_notification`，含义是运行时间和场景 ID。

默认 `run` 会在对话仿真后继续执行评分评估。只想生成覆盖报告时加 `--skip-evaluation`。

对已有运行结果单独补评估：

```bash
python -m dialogue_simulator.cli evaluate \
  --assets outputs/assets/{scene_id} \
  --run-dir outputs/runs/{run_id}
```

## 本地结构测试

`--fake-llm` 只用于验证 schema、LangGraph 节点流转和文件导出，不用于真实业务仿真。

```bash
python -m dialogue_simulator.cli --fake-llm generate-assets \
  --eval-standard Resource/eval_standards/scene_1_eval_standard.md \
  --output outputs/assets

python -m dialogue_simulator.cli --fake-llm run \
  --assets outputs/assets/generated_scene \
  --limit 1 \
  --output outputs/runs
```

## 新场景接入

1. 准备一份新的评测标准 Markdown，结构类似 `Resource/eval_standards/scene_1_eval_standard.md`。
2. 如有变量、知识库补充或禁止承诺，写入一个业务配置 YAML/JSON。
3. 执行 `generate-assets` 生成场景资产。
4. 审阅资产文件，确认 coverage、profiles、case cards 符合预期。
5. 执行 `run` 运行 AI 客服与 AI 用户对话。

无需修改 Python 代码即可接入新场景。
