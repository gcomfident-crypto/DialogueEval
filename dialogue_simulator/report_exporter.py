from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from dialogue_simulator.schemas import CaseEvaluationResult, ConversationResult, LLMCallRecord


def export_run_reports(results: list[ConversationResult], output_dir: str | Path) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    write_jsonl(results, path / "conversation_log.jsonl")
    write_state_trace_jsonl(results, path / "simulation_state_trace.jsonl")
    write_csv(results, path / "coverage_report.csv")
    write_summary(results, path / "summary_report.md")


def export_evaluation_reports(
    evaluations: list[CaseEvaluationResult],
    output_dir: str | Path,
    conversations: list[ConversationResult] | None = None,
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    conversation_map = {
        conversation.case_id: conversation for conversation in conversations or []
    }
    write_case_evaluation_jsonl(evaluations, path / "case_evaluation.jsonl")
    write_evaluation_csv(evaluations, path / "evaluation_report.csv")
    write_evaluation_summary(evaluations, path / "evaluation_report.md")
    case_dir = path / "case_reports"
    case_dir.mkdir(parents=True, exist_ok=True)
    for evaluation in evaluations:
        write_case_report(
            evaluation,
            case_dir / f"{evaluation.case_id}.md",
            conversation_map.get(evaluation.case_id),
        )


def export_llm_call_records(
    records: list[LLMCallRecord],
    output_dir: str | Path,
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    with (path / "llm_calls.jsonl").open("w", encoding="utf-8") as file:
        for record in records:
            file.write(record.model_dump_json() + "\n")


def export_case_artifact_bundles(
    *,
    conversations: list[ConversationResult],
    output_dir: str | Path,
    case_cards: list[Any] | None = None,
    evaluations: list[CaseEvaluationResult] | None = None,
) -> None:
    path = Path(output_dir)
    case_root = path / "cases"
    case_root.mkdir(parents=True, exist_ok=True)
    case_card_map = {_case_id(item): item for item in case_cards or []}
    evaluation_map = {item.case_id: item for item in evaluations or []}
    for conversation in conversations:
        case_dir = case_root / conversation.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        case_card = case_card_map.get(conversation.case_id)
        evaluation = evaluation_map.get(conversation.case_id)
        if case_card is not None:
            _write_json(case_dir / "case_card.json", _model_dump(case_card))
        _write_json(case_dir / "conversation.json", conversation.model_dump(mode="json"))
        _write_conversation_markdown(conversation, case_dir / "conversation.md")
        _write_state_trace(conversation, case_dir / "state_trace.jsonl")
        if evaluation is not None:
            _write_json(case_dir / "scoring.json", evaluation.model_dump(mode="json"))
            write_case_report(evaluation, case_dir / "case_report.md", conversation)


def write_jsonl(results: list[ConversationResult], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(result.model_dump_json() + "\n")


def write_state_trace_jsonl(results: list[ConversationResult], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for result in results:
            for transition in result.state_trace:
                payload = {
                    "run_id": result.run_id,
                    "case_id": result.case_id,
                    "scene_id": result.scene_id,
                    **transition.model_dump(mode="json"),
                }
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_case_evaluation_jsonl(
    evaluations: list[CaseEvaluationResult],
    path: Path,
) -> None:
    with path.open("w", encoding="utf-8") as file:
        for evaluation in evaluations:
            file.write(evaluation.model_dump_json() + "\n")


def write_csv(results: list[ConversationResult], path: Path) -> None:
    fieldnames = [
        "run_id",
        "case_id",
        "scene_id",
        "priority",
        "planned_targets",
        "triggered_targets",
        "missing_targets",
        "coverage_success",
        "turns_count",
        "end_reason",
        "state_events",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "run_id": result.run_id,
                    "case_id": result.case_id,
                    "scene_id": result.scene_id,
                    "priority": result.priority,
                    "planned_targets": ";".join(result.planned_targets),
                    "triggered_targets": ";".join(result.triggered_targets),
                    "missing_targets": ";".join(result.missing_targets),
                    "coverage_success": str(result.coverage_success).lower(),
                    "turns_count": len(result.turns),
                    "end_reason": result.end_reason,
                    "state_events": ";".join(
                        event
                        for transition in result.state_trace
                        for event in transition.update.new_state_events
                    ),
                }
            )


def write_evaluation_csv(evaluations: list[CaseEvaluationResult], path: Path) -> None:
    fieldnames = [
        "run_id",
        "case_id",
        "scene_id",
        "priority",
        "raw_score",
        "risk_deduction_total",
        "total_score",
        "pass_threshold",
        "passed",
        "veto_triggered",
        "coverage_success",
        "missing_targets",
        "dimension_scores",
        "risk_deductions",
        "final_comment",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in evaluations:
            writer.writerow(
                {
                    "run_id": item.run_id,
                    "case_id": item.case_id,
                    "scene_id": item.scene_id,
                    "priority": item.priority,
                    "raw_score": item.raw_score,
                    "risk_deduction_total": item.risk_deduction_total,
                    "total_score": item.total_score,
                    "pass_threshold": item.pass_threshold,
                    "passed": str(item.passed).lower(),
                    "veto_triggered": str(item.veto_triggered).lower(),
                    "coverage_success": str(item.coverage_success).lower(),
                    "missing_targets": ";".join(item.missing_targets),
                    "dimension_scores": ";".join(
                        f"{score.name}:{score.score}/{score.weight}"
                        for score in item.dimension_scores
                    ),
                    "risk_deductions": ";".join(
                        f"{risk.rule_id}:{risk.deduction}"
                        for risk in item.risk_deductions
                    ),
                    "final_comment": item.final_comment,
                }
            )


def write_summary(results: list[ConversationResult], path: Path) -> None:
    scene_stats = defaultdict(lambda: {"cases": 0, "success": 0, "planned": 0, "hit": 0})
    for result in results:
        stats = scene_stats[result.scene_id]
        stats["cases"] += 1
        stats["success"] += int(result.coverage_success)
        stats["planned"] += len(result.planned_targets)
        stats["hit"] += len(result.triggered_targets)

    p0_results = [result for result in results if result.priority == "P0"]
    p0_success = sum(1 for result in p0_results if result.coverage_success)
    missing = [result for result in results if result.missing_targets]
    risk_results = [result for result in results if result.risk_flags]
    state_event_counts: dict[str, int] = defaultdict(int)
    for result in results:
        seen_in_case = {
            event
            for transition in result.state_trace
            for event in transition.update.new_state_events
        }
        for event in seen_in_case:
            state_event_counts[event] += 1

    lines = [
        "# 对话仿真汇总报告",
        "",
        f"- 总 case 数：{len(results)}",
        f"- 成功完成对话数：{sum(1 for item in results if item.coverage_success)}",
        f"- P0 场景通过率：{_ratio(p0_success, len(p0_results))}",
        "",
        "## 每个 scene 的覆盖率",
        "",
        "| scene_id | case 数 | 通过 case 数 | 目标覆盖率 |",
        "|---|---:|---:|---:|",
    ]

    for scene_id in sorted(scene_stats):
        stats = scene_stats[scene_id]
        lines.append(
            f"| {scene_id} | {stats['cases']} | {stats['success']} | "
            f"{_ratio(stats['hit'], stats['planned'])} |"
        )

    lines.extend(["", "## 未触发 coverage_targets 列表", ""])
    if missing:
        lines.extend(["| case_id | missing_targets |", "|---|---|"])
        for result in missing:
            lines.append(f"| {result.case_id} | {', '.join(result.missing_targets)} |")
    else:
        lines.append("- 无")

    lines.extend(["", "## 风险标记列表", ""])
    if risk_results:
        lines.extend(["| case_id | risk_flags |", "|---|---|"])
        for result in risk_results:
            flags = [f"{flag.rule_id}:{flag.severity}" for flag in result.risk_flags]
            lines.append(f"| {result.case_id} | {', '.join(flags)} |")
    else:
        lines.append("- 无")

    lines.extend(["", "## 动态用户状态事件", ""])
    if state_event_counts:
        lines.extend(["| state_event | case_count |", "|---|---:|"])
        for event, count in sorted(state_event_counts.items()):
            lines.append(f"| {event} | {count} |")
    else:
        lines.append("- 无")

    lines.extend(["", "## 需要补测的 case_id", ""])
    if missing:
        for result in missing:
            lines.append(f"- {result.case_id}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 资产来源与模型配置", ""])
    if results:
        lines.append(f"- run_id：{results[0].run_id}")
    else:
        lines.append("- 无运行结果")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evaluation_summary(evaluations: list[CaseEvaluationResult], path: Path) -> None:
    passed = sum(1 for item in evaluations if item.passed)
    p0_items = [item for item in evaluations if item.priority == "P0"]
    p0_passed = sum(1 for item in p0_items if item.passed)
    veto_count = sum(1 for item in evaluations if item.veto_triggered)
    risk_count = sum(len(item.risk_deductions) for item in evaluations)
    average_score = _average([item.total_score for item in evaluations])
    p0_average_score = _average([item.total_score for item in p0_items])
    dimension_stats = _dimension_stats(evaluations)

    lines = [
        "# 对话模型评测总报告",
        "",
        "## 1. 总览",
        "",
        f"- 总 case 数：{len(evaluations)}",
        f"- 通过 case 数：{passed}",
        f"- 通过率：{_ratio(passed, len(evaluations))}",
        f"- 平均分：{average_score:.2f}",
        f"- P0 平均分：{p0_average_score:.2f}",
        f"- P0 通过率：{_ratio(p0_passed, len(p0_items))}",
        f"- 一票否决 case 数：{veto_count}",
        f"- 风险项数量：{risk_count}",
        "",
        "## 2. 分数分布",
        "",
        "| 分数段 | case 数 |",
        "|---|---:|",
    ]

    for bucket, count in _score_buckets(evaluations).items():
        lines.append(f"| {bucket} | {count} |")

    lines.extend(
        [
            "",
            "## 3. 维度得分",
            "",
            "| 维度 | 权重 | 平均得分 | 得分率 | 主要失分原因 |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for dimension_id in sorted(dimension_stats):
        stat = dimension_stats[dimension_id]
        lines.append(
            f"| {stat['name']} | {stat['weight']:.1f} | {stat['avg_score']:.2f} | "
            f"{_ratio_float(stat['avg_score'], stat['weight'])} | {stat['missing']} |"
        )

    lines.extend(
        [
            "",
            "## 4. Case 明细",
            "",
            "| case_id | 总分 | 是否通过 | 一票否决 | 缺失覆盖项 | 主要结论 |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for item in evaluations:
        lines.append(
            f"| {item.case_id} | {item.total_score:.2f} | {_yes_no(item.passed)} | "
            f"{_yes_no(item.veto_triggered)} | {', '.join(item.missing_targets) or '无'} | "
            f"{_escape_table(item.final_comment)} |"
        )

    lines.extend(
        [
            "",
            "## 5. 未覆盖项与证据",
            "",
            "| case_id | missing_target | 缺失原因 |",
            "|---|---|---|",
        ]
    )
    missing_rows = 0
    for item in evaluations:
        missing_reason = _missing_reason(item)
        for target in item.missing_targets:
            missing_rows += 1
            lines.append(f"| {item.case_id} | {target} | {_escape_table(missing_reason)} |")
    if missing_rows == 0:
        lines.append("| 无 | 无 | 无 |")

    lines.extend(
        [
            "",
            "## 6. 风险项",
            "",
            "| case_id | risk_rule | severity | deduction | evidence |",
            "|---|---|---|---:|---|",
        ]
    )
    risk_rows = 0
    for item in evaluations:
        for risk in item.risk_deductions:
            risk_rows += 1
            lines.append(
                f"| {item.case_id} | {risk.rule_id} | {risk.severity} | "
                f"{risk.deduction:.2f} | {_escape_table(_evidence_text(risk.evidence))} |"
            )
    if risk_rows == 0:
        lines.append("| 无 | 无 | 无 | 0 | 无 |")

    lines.extend(["", "## 7. 改进建议", ""])
    failed = [item for item in evaluations if not item.passed]
    if failed:
        lines.append(f"- 优先复查未通过的 {len(failed)} 个 case：{', '.join(item.case_id for item in failed)}。")
    weak_dimensions = [
        stat["name"]
        for stat in dimension_stats.values()
        if stat["weight"] > 0 and stat["avg_score"] / stat["weight"] < 0.8
    ]
    if weak_dimensions:
        lines.append(f"- 重点优化低得分维度：{', '.join(weak_dimensions)}。")
    if veto_count:
        lines.append("- 存在一票否决项，应优先排查对应对话证据。")
    if not failed and not weak_dimensions and not veto_count:
        lines.append("- 当前评测结果无明显短板。")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_case_report(
    evaluation: CaseEvaluationResult,
    path: Path,
    conversation: ConversationResult | None = None,
) -> None:
    lines = [
        f"# Case 评测子报告：{evaluation.case_id}",
        "",
        "## 1. 结论",
        "",
        f"- scene_id：{evaluation.scene_id}",
        f"- priority：{evaluation.priority}",
        f"- 总分：{evaluation.total_score:.2f}",
        f"- 原始维度分：{evaluation.raw_score:.2f}",
        f"- 风险扣分：{evaluation.risk_deduction_total:.2f}",
        f"- 合格线：{evaluation.pass_threshold:.2f}",
        f"- 是否通过：{_yes_no(evaluation.passed)}",
        f"- 是否触发一票否决：{_yes_no(evaluation.veto_triggered)}",
        f"- 覆盖是否成功：{_yes_no(evaluation.coverage_success)}",
        f"- 缺失覆盖项：{', '.join(evaluation.missing_targets) or '无'}",
        "",
        "## 2. 维度评分",
        "",
        "| 维度 | 权重 | 得分 | 原因 | 缺失点 |",
        "|---|---:|---:|---|---|",
    ]
    for score in evaluation.dimension_scores:
        lines.append(
            f"| {score.name} | {score.weight:.1f} | {score.score:.2f} | "
            f"{_escape_table(score.reason)} | {', '.join(score.missing_points) or '无'} |"
        )

    lines.extend(["", "## 3. 原始对话记录", ""])
    if conversation and conversation.turns:
        lines.extend(
            [
                "| 轮次 | 角色 | 内容 | 意图/情绪 |",
                "|---:|---|---|---|",
            ]
        )
        for index, turn in enumerate(conversation.turns):
            meta_parts = []
            if turn.intent:
                meta_parts.append(f"intent: {turn.intent}")
            if turn.emotion:
                meta_parts.append(f"emotion: {turn.emotion}")
            if turn.patience is not None:
                meta_parts.append(f"patience: {turn.patience}")
            if turn.risk_flags:
                meta_parts.append(f"risk: {', '.join(turn.risk_flags)}")
            role = "客服" if turn.role == "agent" else "用户"
            lines.append(
                f"| {index} | {role} | {_escape_table(turn.text)} | "
                f"{_escape_table('; '.join(meta_parts) or '无')} |"
            )
    else:
        lines.append("- 未找到原始对话记录")

    lines.extend(["", "## 4. 证据引用", ""])
    wrote_evidence = False
    for score in evaluation.dimension_scores:
        if not score.evidence:
            continue
        wrote_evidence = True
        lines.append(f"### {score.name}")
        for evidence in score.evidence:
            lines.append(
                f"- 第 {evidence.turn_index} 轮，{evidence.speaker}："
                f"“{evidence.quote}”"
                f"；{evidence.explanation}"
            )
        lines.append("")
    if not wrote_evidence:
        lines.append("- 无明确证据引用")

    lines.extend(["", "## 5. 一票否决", ""])
    if evaluation.veto_items:
        for item in evaluation.veto_items:
            lines.append(f"- {item.rule_id}（{item.severity}）：{item.description}")
            evidence = _evidence_text(item.evidence)
            if evidence:
                lines.append(f"  证据：{evidence}")
    else:
        lines.append("- 未触发")

    lines.extend(["", "## 6. 风险扣分", ""])
    if evaluation.risk_deductions:
        for risk in evaluation.risk_deductions:
            lines.append(
                f"- {risk.rule_id}（{risk.severity}，扣 {risk.deduction:.2f}）："
                f"{risk.description}"
            )
            evidence = _evidence_text(risk.evidence)
            if evidence:
                lines.append(f"  证据：{evidence}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 7. 总评", "", evaluation.final_comment or "无"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _case_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("case_id") or "")
    return str(getattr(item, "case_id", "") or "")


def _model_dump(item: Any) -> Any:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    return item


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_conversation_markdown(conversation: ConversationResult, path: Path) -> None:
    lines = [
        f"# 对话记录：{conversation.case_id}",
        "",
        f"- run_id：{conversation.run_id}",
        f"- scene_id：{conversation.scene_id}",
        f"- priority：{conversation.priority}",
        f"- 覆盖是否成功：{_yes_no(conversation.coverage_success)}",
        f"- 缺失覆盖项：{', '.join(conversation.missing_targets) or '无'}",
        f"- 结束原因：{conversation.end_reason}",
        "",
        "## 对话",
        "",
    ]
    if not conversation.turns:
        lines.append("- 无对话")
    for index, turn in enumerate(conversation.turns, start=1):
        role = "客服" if turn.role == "agent" else "用户"
        lines.append(f"**{index}. {role}**")
        lines.append("")
        lines.append(turn.text)
        meta_parts = []
        if turn.intent:
            meta_parts.append(f"intent={turn.intent}")
        if turn.emotion:
            meta_parts.append(f"emotion={turn.emotion}")
        if turn.patience is not None:
            meta_parts.append(f"patience={turn.patience}")
        if turn.risk_flags:
            meta_parts.append(f"risk={', '.join(turn.risk_flags)}")
        if meta_parts:
            lines.append("")
            lines.append(f"> {'; '.join(meta_parts)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_state_trace(conversation: ConversationResult, path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for transition in conversation.state_trace:
            payload = {
                "run_id": conversation.run_id,
                "case_id": conversation.case_id,
                "scene_id": conversation.scene_id,
                **transition.model_dump(mode="json"),
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0%"
    return f"{numerator / denominator:.1%}"


def _ratio_float(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        return "0.0%"
    return f"{numerator / denominator:.1%}"


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _evidence_text(evidence_items) -> str:
    parts = []
    for item in evidence_items:
        parts.append(f"第{item.turn_index}轮{item.speaker}: {item.quote}")
    return "；".join(parts)


def _missing_reason(evaluation: CaseEvaluationResult) -> str:
    missing_points = []
    for score in evaluation.dimension_scores:
        missing_points.extend(score.missing_points)
    if missing_points:
        return "；".join(missing_points[:3])
    return evaluation.final_comment


def _score_buckets(evaluations: list[CaseEvaluationResult]) -> dict[str, int]:
    buckets = {"90-100": 0, "80-89": 0, "60-79": 0, "0-59": 0}
    for item in evaluations:
        score = item.total_score
        if score >= 90:
            buckets["90-100"] += 1
        elif score >= 80:
            buckets["80-89"] += 1
        elif score >= 60:
            buckets["60-79"] += 1
        else:
            buckets["0-59"] += 1
    return buckets


def _dimension_stats(evaluations: list[CaseEvaluationResult]) -> dict[str, dict[str, object]]:
    collected: dict[str, dict[str, object]] = {}
    for evaluation in evaluations:
        for score in evaluation.dimension_scores:
            stat = collected.setdefault(
                score.dimension_id,
                {
                    "name": score.name,
                    "weight": score.weight,
                    "scores": [],
                    "missing_points": [],
                },
            )
            stat["scores"].append(score.score)
            stat["missing_points"].extend(score.missing_points)

    output = {}
    for dimension_id, stat in collected.items():
        missing_points = stat["missing_points"]
        output[dimension_id] = {
            "name": stat["name"],
            "weight": float(stat["weight"]),
            "avg_score": _average(stat["scores"]),
            "missing": "；".join(missing_points[:3]) if missing_points else "无",
        }
    return output
