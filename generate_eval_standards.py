import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_PROMPT = """你是一名资深的数字人对话质检专家、对话流程设计专家和评测体系架构专家。

你的任务不是复述原始指令，而是将原始任务指令转化为一套可以直接用于真实对话评测的专业评测标准。

你必须满足以下要求：
1. 先完整拆解任务指令，覆盖核心任务目标、标准流程步骤、知识点、异常处理规则、禁止项，不得遗漏。
2. 再基于拆解结果设计一套真实对话评测标准体系，要求可执行、可验证、可量化，不允许空泛表述。
3. 评测标准必须适用于真实电话对话评测，能够被人工质检员或模型评测器直接使用。
4. 每个场景必须单独输出，不得与其他场景混合。
5. 所有权重必须加总为100分。
6. 必须给出明确的合格阈值、一票否决项、扣分规则、场景适配调整逻辑。
7. 如果原始指令中存在占位符、模糊项或外部依赖信息，要显式标注为“待业务配置项”或“需结合知识库确认”。
8. 输出必须为中文 Markdown，禁止输出代码块围栏，禁止输出多余前言。
"""


USER_PROMPT_TEMPLATE = """请基于下面这个单一场景的任务指令，输出一份“结构化拆解 + 真实对话评测标准”文档。

要求：
- 这是一个独立场景，只为这个场景生成，不要泛化到其他场景。
- 拆解必须覆盖：
  1. 场景定位
  2. 核心任务目标
  3. 标准化流程步骤
  4. 核心知识点
  5. 异常/分支处理规则
  6. 禁止项/合规红线
- 评测标准必须覆盖：
  1. 整体框架
  2. 维度定义
  3. 权重分配
  4. 量化评分规则
  5. 合格阈值
  6. 一票否决项
  7. 场景调权逻辑
  8. 可直接执行的评测检查清单
- 评分规则必须避免模糊表达，尽量使用“满足/部分满足/未满足”“出现一次扣几分”“缺失关键动作记0分”这类可执行表述。
- 输出内容要适合真实对话评测，重点覆盖任务完成度、流程执行、知识准确性、合规性、异常处理能力、表达质量等方向。
- 如果某一维度不适合该场景，请说明原因后调整权重，但总分必须保持100。
- 请尽量从原文里抽取明确事实，不要擅自编造业务知识。

请严格按照以下 Markdown 结构输出：

# 场景{scene_id}评测标准

## 1. 场景定位
- 场景名称：
- 业务目标：
- 对话对象：
- 成功定义：
- 待业务配置项：

## 2. 任务指令结构化拆解
### 2.1 核心任务目标
- 

### 2.2 标准化流程步骤
1. 

### 2.3 核心知识点
- 知识点：
  - 标准表述：
  - 适用时机：

### 2.4 异常/分支处理规则
- 触发条件：
  - 应对动作：
  - 评测关注点：

### 2.5 禁止项与合规红线
- 禁止项：
  - 风险说明：

## 3. 真实对话评测标准体系
### 3.1 总体框架与权重
| 维度 | 权重 | 评测目标 | 合格要求 |
|---|---:|---|---|

### 3.2 各维度量化评分规则
#### 维度名称（X分）
- 满分标准：
- 部分得分标准：
- 失分/扣分规则：
- 记0分条件：
- 验证依据：

### 3.3 合格阈值
- 总分合格线：
- 关键维度最低要求：
- 不合格触发条件：

### 3.4 一票否决项
- 

### 3.5 场景适配调整逻辑
- 当目标是任务触达优先时：
- 当目标是知识传达优先时：
- 当目标是高风险合规优先时：

### 3.6 实操评测检查清单
- [ ] 

### 3.7 评测结论输出模板
- 总分：
- 是否合格：
- 主要失分项：
- 关键证据：
- 改进建议：

以下是任务指令原文：

{task_markdown}
"""


def parse_task_markdown(file_path: Path) -> tuple[str, str]:
    content = file_path.read_text(encoding="utf-8")

    scene_id_match = re.search(r"\*\*id\*\*:\s*(.+)", content)
    task_match = re.search(r"\*\*任务指令示例\*\*:\s*(.*)", content, re.DOTALL)

    if not scene_id_match or not task_match:
        raise ValueError(f"无法解析任务文件：{file_path}")

    scene_id = scene_id_match.group(1).strip()
    task_markdown = task_match.group(1).strip()
    if not task_markdown:
        raise ValueError(f"任务内容为空：{file_path}")

    return scene_id, task_markdown


def build_client() -> OpenAI:
    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing DEEPSEEK_API_KEY. Create a `.env` file in the project root with:\n"
            'DEEPSEEK_API_KEY="your_api_key_here"'
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def generate_standard(client: OpenAI, scene_id: str, task_markdown: str) -> str:
    response = client.chat.completions.create(
        model="deepseek-chat",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    scene_id=scene_id,
                    task_markdown=task_markdown,
                ),
            },
        ],
        stream=False,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"场景 {scene_id} 未返回有效内容。")

    lines = content.strip().splitlines()
    expected_title = f"# 场景{scene_id}评测标准"
    if not lines:
        raise ValueError(f"场景 {scene_id} 返回内容为空。")

    if lines[0].startswith("# "):
        lines[0] = expected_title
    else:
        lines.insert(0, expected_title)
        lines.insert(1, "")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="基于任务指令批量生成场景评测标准。")
    parser.add_argument(
        "--tasks-dir",
        default="Resource/tasks",
        help="任务指令 Markdown 文件目录。",
    )
    parser.add_argument(
        "--output-dir",
        default="Resource/eval_standards",
        help="评测标准输出目录。",
    )
    args = parser.parse_args()

    tasks_dir = Path(args.tasks_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    task_files = sorted(tasks_dir.glob("Task_*.md"))
    if not task_files:
        raise SystemExit(f"未在目录中找到任务文件：{tasks_dir}")

    client = build_client()

    for task_file in task_files:
        scene_id, task_markdown = parse_task_markdown(task_file)
        print(f"正在生成场景 {scene_id} 的评测标准：{task_file.name}")
        standard_markdown = generate_standard(client, scene_id, task_markdown)

        output_file = output_dir / f"scene_{scene_id}_eval_standard.md"
        output_file.write_text(standard_markdown, encoding="utf-8")
        print(f"已写入：{output_file}")


if __name__ == "__main__":
    main()
