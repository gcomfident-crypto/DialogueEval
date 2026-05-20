from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dialogue_simulator.eval_standard_loader import (
    extract_markdown_from_csv,
    extract_markdown_from_excel,
    is_csv_path,
)
from dialogue_simulator.evaluation_graph import build_evaluation_graph
from dialogue_simulator.graph import (
    build_asset_generation_graph,
    build_conversation_graph,
    load_generated_assets,
)
from dialogue_simulator.llm_client import FakeLLMClient, OpenAICompatibleClient
from dialogue_simulator.report_exporter import (
    export_evaluation_reports,
    export_llm_call_records,
    export_run_reports,
)
from dialogue_simulator.schemas import BusinessConfig, ConversationResult, ModelConfig
from dialogue_simulator.storage import read_structured_file, read_text
from dialogue_simulator.prompt_store import prompt_status, sync_default_prompts
from dialogue_simulator.tracing import setup_tracing, shutdown_tracing, trace_span


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="外呼对话 AI 仿真组件")
    parser.add_argument(
        "--model-config",
        default="configs/model_config.yaml",
        help="模型配置 YAML/JSON。",
    )
    parser.add_argument(
        "--fake-llm",
        action="store_true",
        help="仅用于本地测试 schema 和 graph 流程，不用于真实业务仿真。",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate-assets", help="从评测标准生成场景资产。")
    generate.add_argument("--eval-standard", help="评测标准 Markdown 路径。")
    generate.add_argument("--eval-standard-excel", help="从 Excel/CSV 第二列开始批量抽取评测标准。")
    generate.add_argument("--excel-column", type=int, default=2, help="Excel 中 Markdown 所在列，1-based，默认第2列。")
    generate.add_argument("--excel-start-row", type=int, default=2, help="Excel 起始行，1-based，默认第2行。")
    generate.add_argument("--excel-sheet", help="Excel sheet 名，不填则使用第一个 sheet。")
    generate.add_argument(
        "--extracted-output-dir",
        default="outputs/extracted_eval_standards",
        help="从 Excel 抽取出的 Markdown 文件保存目录。",
    )
    generate.add_argument("--business-config", help="业务配置 YAML/JSON 路径。")
    generate.add_argument(
        "--generation-policy",
        default="configs/generation_policy.yaml",
        help="资产生成策略 YAML/JSON。",
    )
    generate.add_argument("--output", default="outputs/assets", help="资产输出根目录。")

    run = subparsers.add_parser("run", help="运行对话仿真。")
    run.add_argument("--assets", required=True, help="资产目录。")
    run.add_argument("--business-config", help="运行时业务配置 YAML/JSON 路径。")
    run.add_argument("--limit", type=int, help="最多运行多少张 case card。")
    run.add_argument("--output", default="outputs/runs", help="运行报告输出根目录。")
    run.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="只生成对话覆盖报告，不生成评分报告。",
    )

    evaluate = subparsers.add_parser("evaluate", help="对已有 run 目录生成评分报告。")
    evaluate.add_argument("--assets", required=True, help="资产目录。")
    evaluate.add_argument("--run-dir", required=True, help="已有运行报告目录。")
    evaluate.add_argument("--business-config", help="运行时业务配置 YAML/JSON 路径。")

    extract = subparsers.add_parser("extract-eval-standards", help="从 Excel/CSV 抽取评测标准 Markdown。")
    extract.add_argument("--excel", required=True, help="Excel 或 CSV 文件路径。")
    extract.add_argument("--output-dir", default="outputs/extracted_eval_standards", help="Markdown 输出目录。")
    extract.add_argument("--excel-column", type=int, default=2, help="Excel 中 Markdown 所在列，1-based，默认第2列。")
    extract.add_argument("--excel-start-row", type=int, default=2, help="Excel 起始行，1-based，默认第2行。")
    extract.add_argument("--excel-sheet", help="Excel sheet 名，不填则使用第一个 sheet。")

    sync_prompts = subparsers.add_parser("sync-prompts", help="同步默认提示词到 Phoenix Prompts。")
    sync_prompts.add_argument("--phoenix-base-url", default=None, help="Phoenix base URL，默认读取 PHOENIX_BASE_URL。")
    sync_prompts.add_argument("--model-name", default="deepseek-chat", help="提示词版本记录的模型名。")
    sync_prompts.add_argument("--dry-run", action="store_true", help="只列出将同步的提示词，不写入 Phoenix。")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    setup_tracing("dialogue-eval-cli")
    try:
        if args.command == "generate-assets":
            generate_assets_command(args)
            return
        if args.command == "run":
            run_command(args)
            return
        if args.command == "evaluate":
            evaluate_command(args)
            return
        if args.command == "extract-eval-standards":
            extract_eval_standards_command(args)
            return
        if args.command == "sync-prompts":
            sync_prompts_command(args)
            return
        raise SystemExit(f"Unknown command: {args.command}")
    finally:
        shutdown_tracing()


def generate_assets_command(args: argparse.Namespace) -> None:
    eval_standard_paths = resolve_eval_standard_paths(args)
    llm = build_llm(args, "asset_generator")
    asset_dirs = []
    with trace_span(
        "cli.generate_assets",
        attributes={"dialogue_eval.command": "generate-assets"},
        input_data={
            "eval_standard_paths": [str(path) for path in eval_standard_paths],
            "business_config": args.business_config,
            "generation_policy": args.generation_policy,
            "output": args.output,
        },
    ) as span:
        for index, eval_standard_path in enumerate(eval_standard_paths, start=1):
            print(f"正在生成资产 {index}/{len(eval_standard_paths)}：{eval_standard_path}", flush=True)
            graph = build_asset_generation_graph(llm, output_root=args.output)
            result = graph.invoke(
                {
                    "eval_standard_path": str(eval_standard_path),
                    "business_config_path": args.business_config,
                    "generation_policy_path": args.generation_policy,
                }
            )
            asset_dirs.append(Path(result["asset_dir"]))
            export_llm_call_records(get_call_records([llm]), result["asset_dir"])
            print(f"资产已生成：{Path(result['asset_dir']).resolve()}")

        span.set_output({"asset_dirs": [str(path) for path in asset_dirs]})

    if len(asset_dirs) > 1:
        print("批量生成完成：")
        for asset_dir in asset_dirs:
            print(f"- {asset_dir.resolve()}")


def resolve_eval_standard_paths(args: argparse.Namespace) -> list[Path]:
    if bool(args.eval_standard) == bool(args.eval_standard_excel):
        raise SystemExit("请二选一提供 --eval-standard 或 --eval-standard-excel。")

    if args.eval_standard:
        return [Path(args.eval_standard)]

    if is_csv_path(args.eval_standard_excel):
        extracted = extract_markdown_from_csv(
            args.eval_standard_excel,
            args.extracted_output_dir,
            column=args.excel_column,
            start_row=args.excel_start_row,
        )
    else:
        extracted = extract_markdown_from_excel(
            args.eval_standard_excel,
            args.extracted_output_dir,
            column=args.excel_column,
            start_row=args.excel_start_row,
            sheet_name=args.excel_sheet,
        )
    if not extracted:
        raise SystemExit("Excel 中没有抽取到有效 Markdown 内容。")
    print("已从 Excel 抽取评测标准：")
    for item in extracted:
        print(f"- row {item.source_row}: {item.output_path}")
    return [Path(item.output_path) for item in extracted]


def extract_eval_standards_command(args: argparse.Namespace) -> None:
    if is_csv_path(args.excel):
        extracted = extract_markdown_from_csv(
            args.excel,
            args.output_dir,
            column=args.excel_column,
            start_row=args.excel_start_row,
        )
    else:
        extracted = extract_markdown_from_excel(
            args.excel,
            args.output_dir,
            column=args.excel_column,
            start_row=args.excel_start_row,
            sheet_name=args.excel_sheet,
        )
    if not extracted:
        raise SystemExit("Excel 中没有抽取到有效 Markdown 内容。")
    print(f"已抽取 {len(extracted)} 份评测标准：")
    for item in extracted:
        print(f"- row {item.source_row}: {Path(item.output_path).resolve()}")


def sync_prompts_command(args: argparse.Namespace) -> None:
    print("Phoenix Prompt 配置：")
    status = prompt_status()
    print(f"- base_url: {args.phoenix_base_url or status['phoenix_base_url']}")
    print(f"- prompt_count: {status['prompt_count']}")
    results = sync_default_prompts(
        base_url=args.phoenix_base_url,
        model_name=args.model_name,
        dry_run=args.dry_run,
    )
    for result in results:
        suffix = f" version={result.version_id}" if result.version_id else ""
        error = f" error={result.error}" if result.error else ""
        print(f"- {result.name}: {result.status}{suffix}{error}")


def run_command(args: argparse.Namespace) -> None:
    assets = load_generated_assets(args.assets)
    business_config = (
        BusinessConfig.model_validate(read_structured_file(args.business_config))
        if args.business_config
        else BusinessConfig()
    )
    agent_llm = build_llm(args, "agent")
    user_llm = build_llm(args, "user")
    judge_llm = build_llm(args, "judge")
    state_llm = build_llm(args, "state_updater")
    evaluator_llm = None if args.skip_evaluation else build_llm(args, "evaluator")
    graph = build_conversation_graph(
        agent_llm=agent_llm,
        user_llm=user_llm,
        judge_llm=judge_llm,
        state_llm=state_llm,
    )

    run_id = make_run_id(assets.scene_asset.scene_id, Path(args.output))
    case_cards = assets.case_cards.cases[: args.limit] if args.limit else assets.case_cards.cases
    results = []
    output_dir = Path(args.output) / run_id
    with trace_span(
        "cli.run_evaluation",
        attributes={
            "dialogue_eval.command": "run",
            "dialogue_eval.run_id": run_id,
            "dialogue_eval.scene_id": assets.scene_asset.scene_id,
            "dialogue_eval.case_count": len(case_cards),
        },
        input_data={
            "assets": args.assets,
            "limit": args.limit,
            "skip_evaluation": args.skip_evaluation,
        },
        session_id=run_id,
    ) as run_span:
        for index, case_card in enumerate(case_cards, start=1):
            print(f"正在运行 case {index}/{len(case_cards)}：{case_card.case_id}", flush=True)
            with trace_span(
                "case.run",
                attributes={
                    "dialogue_eval.run_id": run_id,
                    "dialogue_eval.case_id": case_card.case_id,
                    "dialogue_eval.scene_id": case_card.scene_id,
                    "dialogue_eval.case_index": index,
                },
                input_data=case_card,
                session_id=run_id,
                metadata={"case_id": case_card.case_id, "scene_id": case_card.scene_id},
            ) as case_span:
                result = graph.invoke(
                    {
                        "run_id": run_id,
                        "scene_asset": assets.scene_asset,
                        "coverage_plan": assets.coverage_plan,
                        "user_profiles": assets.user_profiles,
                        "case_card": case_card,
                        "business_config": business_config,
                    },
                    {"recursion_limit": case_card.stop_policy.max_turns * 6 + 10},
                )
                conversation_result = result["conversation_result"]
                case_span.set_output(
                    {
                        "coverage_success": conversation_result.coverage_success,
                        "turn_count": len(conversation_result.turns),
                        "missing_targets": conversation_result.missing_targets,
                    }
                )
            results.append(result["conversation_result"])
            export_run_reports(results, output_dir)

        export_run_reports(results, output_dir)
        evaluation_count = 0
        if evaluator_llm is not None:
            evaluations = evaluate_results(
                evaluator_llm=evaluator_llm,
                assets=assets,
                results=results,
                business_config=business_config,
            )
            evaluation_count = len(evaluations)
            export_evaluation_reports(
                evaluations,
                output_dir,
                conversations=results,
                coverage_plan=assets.coverage_plan,
                scoring_rubric=assets.scoring_rubric,
            )
        export_llm_call_records(
            get_call_records([agent_llm, user_llm, judge_llm, state_llm, evaluator_llm]),
            output_dir,
        )
        run_span.set_output(
            {
                "run_id": run_id,
                "cases_run": len(results),
                "cases_evaluated": evaluation_count,
                "output_dir": str(output_dir),
            }
        )
    print(f"已运行 {len(results)} 个 case。")
    print(f"报告目录：{output_dir.resolve()}")


def evaluate_command(args: argparse.Namespace) -> None:
    assets = load_generated_assets(args.assets)
    business_config = (
        BusinessConfig.model_validate(read_structured_file(args.business_config))
        if args.business_config
        else BusinessConfig()
    )
    run_dir = Path(args.run_dir)
    results = load_conversation_results(run_dir / "conversation_log.jsonl")
    evaluator_llm = build_llm(args, "evaluator")
    with trace_span(
        "cli.evaluate_run",
        attributes={
            "dialogue_eval.command": "evaluate",
            "dialogue_eval.run_dir": str(run_dir),
            "dialogue_eval.case_count": len(results),
        },
        input_data={"assets": args.assets, "run_dir": args.run_dir},
        session_id=run_dir.name,
    ) as span:
        evaluations = evaluate_results(
            evaluator_llm=evaluator_llm,
            assets=assets,
            results=results,
            business_config=business_config,
        )
        export_evaluation_reports(
            evaluations,
            run_dir,
            conversations=results,
            coverage_plan=assets.coverage_plan,
            scoring_rubric=assets.scoring_rubric,
        )
        export_llm_call_records(get_call_records([evaluator_llm]), run_dir)
        span.set_output({"cases_evaluated": len(evaluations), "run_dir": str(run_dir)})
    print(f"已评估 {len(evaluations)} 个 case。")
    print(f"报告目录：{run_dir.resolve()}")


def evaluate_results(
    *,
    evaluator_llm,
    assets,
    results: list[ConversationResult],
    business_config: BusinessConfig,
    experiment_id: str = "",
    asset_version_id: str = "",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
):
    eval_standard_path = assets.scene_asset.source_eval_standard_path
    eval_standard_text = (
        read_text(eval_standard_path)
        if eval_standard_path and Path(eval_standard_path).is_file()
        else ""
    )
    graph = build_evaluation_graph(evaluator_llm=evaluator_llm)
    evaluations = []
    for index, result in enumerate(results, start=1):
        if cancel_check:
            cancel_check()
        if progress_callback:
            progress_callback(
                {
                    "phase": "scoring",
                    "status": "case_start",
                    "case_id": result.case_id,
                    "case_index": index,
                    "case_count": len(results),
                }
            )
        print(f"正在评估 case {index}/{len(results)}：{result.case_id}", flush=True)
        with trace_span(
            "case.evaluate",
            attributes={
                "dialogue_eval.experiment_id": experiment_id,
                "dialogue_eval.run_id": result.run_id,
                "dialogue_eval.asset_version_id": asset_version_id,
                "dialogue_eval.case_id": result.case_id,
                "dialogue_eval.scene_id": result.scene_id,
                "dialogue_eval.case_index": index,
            },
            input_data=result,
            session_id=result.run_id,
            metadata={
                "experiment_id": experiment_id,
                "asset_version_id": asset_version_id,
                "run_id": result.run_id,
                "case_id": result.case_id,
                "scene_id": result.scene_id,
            },
        ) as span:
            evaluated = graph.invoke(
                {
                    "run_id": result.run_id,
                    "scene_asset": assets.scene_asset,
                    "coverage_plan": assets.coverage_plan,
                    "scoring_rubric": assets.scoring_rubric,
                    "conversation_result": result,
                    "eval_standard_text": eval_standard_text,
                    "business_config": business_config,
                },
                {"recursion_limit": 20},
            )
            case_evaluation = evaluated["case_evaluation"]
            span.set_output(
                {
                    "total_score": case_evaluation.total_score,
                    "passed": case_evaluation.passed,
                    "veto_triggered": case_evaluation.veto_triggered,
                }
            )
        if cancel_check:
            cancel_check()
        evaluations.append(evaluated["case_evaluation"])
        if progress_callback:
            progress_callback(
                {
                    "phase": "scoring",
                    "status": "case_complete",
                    "case_id": result.case_id,
                    "case_index": index,
                    "case_count": len(results),
                }
            )
    return evaluations


def load_conversation_results(path: Path) -> list[ConversationResult]:
    return [
        ConversationResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def get_call_records(clients) -> list:
    records = []
    for client in clients:
        if client is None:
            continue
        records.extend(getattr(client, "call_records", []))
    return records


def make_run_id(scene_id: str, output_root: Path) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_scene_id = safe_path_part(scene_id) or "scene"
    base = f"run_{timestamp}_{safe_scene_id}"
    candidate = base
    index = 2
    while (output_root / candidate).exists():
        candidate = f"{base}_{index:02d}"
        index += 1
    return candidate


def safe_path_part(value: str) -> str:
    chars = []
    for char in value:
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_")


def build_llm(args: argparse.Namespace, role: str):
    if args.fake_llm:
        return FakeLLMClient()
    config = ModelConfig.model_validate(read_structured_file(args.model_config))
    return OpenAICompatibleClient.from_config(config, role)


if __name__ == "__main__":
    main()
