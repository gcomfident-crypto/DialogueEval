from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dialogue_simulator.schemas import (
    CaseEvaluationResult,
    ConversationResult,
    GeneratedAssets,
)


@dataclass
class PhoenixDatasetPublishResult:
    name: str
    dataset_type: str
    status: str
    example_count: int
    base_url: str
    dataset_id: str = ""
    version_id: str = ""
    error: str = ""
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dataset_type": self.dataset_type,
            "status": self.status,
            "example_count": self.example_count,
            "base_url": self.base_url,
            "dataset_id": self.dataset_id,
            "version_id": self.version_id,
            "error": self.error,
            "dry_run": self.dry_run,
        }


def publish_case_seed_dataset(
    *,
    assets: GeneratedAssets,
    asset_dir: str | Path,
    asset_version_id: str,
    dataset_name: str | None = None,
    base_url: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    examples = build_case_seed_examples(
        assets=assets,
        asset_dir=asset_dir,
        asset_version_id=asset_version_id,
        limit=limit,
    )
    name = dataset_name or default_case_seed_dataset_name(assets.scene_asset.scene_id)
    description = (
        "DialogueEval case seed 输入集。每条 example 是一次可复现实验输入，"
        "不包含客服输出和最终评分。"
    )
    return _publish_examples(
        name=name,
        dataset_type="case_seed",
        examples=examples,
        description=description,
        base_url=base_url,
        dry_run=dry_run,
    ).as_dict()


def publish_generated_dialogue_dataset(
    *,
    assets: GeneratedAssets,
    asset_dir: str | Path,
    asset_version_id: str,
    run_dir: str | Path,
    run_id: str,
    experiment_id: str,
    conversations: list[ConversationResult],
    evaluations: list[CaseEvaluationResult] | None = None,
    dataset_name: str | None = None,
    base_url: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    examples = build_generated_dialogue_examples(
        assets=assets,
        asset_dir=asset_dir,
        asset_version_id=asset_version_id,
        run_dir=run_dir,
        run_id=run_id,
        experiment_id=experiment_id,
        conversations=conversations,
        evaluations=evaluations or [],
    )
    name = dataset_name or default_generated_dialogue_dataset_name(assets.scene_asset.scene_id)
    description = (
        "DialogueEval 生成对话归档集。每条 example 保留本次 experiment 的输入、"
        "对话输出和评分输出，用于人工标注、judge 校准和结果复盘。"
    )
    return _publish_examples(
        name=name,
        dataset_type="generated_dialogue",
        examples=examples,
        description=description,
        base_url=base_url,
        dry_run=dry_run,
    ).as_dict()


def build_case_seed_examples(
    *,
    assets: GeneratedAssets,
    asset_dir: str | Path,
    asset_version_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    profile_by_id = {
        item.profile_id: item.model_dump(mode="json")
        for item in assets.user_profiles.profiles
    }
    coverage_by_label = {
        item.label: item.model_dump(mode="json")
        for item in assets.coverage_plan.coverage_labels
    }
    matrix_by_id = {
        item.matrix_id: item.model_dump(mode="json")
        for item in (assets.coverage_matrix.rows if assets.coverage_matrix else [])
    }
    selected_cases = assets.case_cards.cases[:limit] if limit else assets.case_cards.cases
    examples: list[dict[str, Any]] = []
    for case_card in selected_cases:
        metadata = _case_metadata(
            assets=assets,
            asset_version_id=asset_version_id,
            case_id=case_card.case_id,
            priority=case_card.priority,
            matrix_id=case_card.matrix_id,
            profile_id=case_card.profile_id,
            dataset_type="case_seed",
        )
        examples.append(
            {
                "input": {
                    "asset_ref": _asset_reference(
                        assets=assets,
                        asset_dir=asset_dir,
                        asset_version_id=asset_version_id,
                    ),
                    "task_definition": _task_definition(assets),
                    "case_card": case_card.model_dump(mode="json"),
                    "user_profile": profile_by_id.get(case_card.profile_id, {}),
                    "coverage_targets": [
                        coverage_by_label.get(target, {"label": target})
                        for target in case_card.coverage_targets
                    ],
                    "coverage_matrix_row": matrix_by_id.get(case_card.matrix_id, {}),
                    "scoring_ref": _scoring_reference(assets),
                },
                "output": {},
                "metadata": metadata,
            }
        )
    return examples


def build_generated_dialogue_examples(
    *,
    assets: GeneratedAssets,
    asset_dir: str | Path,
    asset_version_id: str,
    run_dir: str | Path,
    run_id: str,
    experiment_id: str,
    conversations: list[ConversationResult],
    evaluations: list[CaseEvaluationResult],
) -> list[dict[str, Any]]:
    case_seed_by_id = {
        str(example["metadata"].get("case_id")): example
        for example in build_case_seed_examples(
            assets=assets,
            asset_dir=asset_dir,
            asset_version_id=asset_version_id,
        )
    }
    evaluation_by_case = {item.case_id: item for item in evaluations}
    examples: list[dict[str, Any]] = []
    for conversation in conversations:
        seed = case_seed_by_id.get(conversation.case_id, {})
        seed_input = seed.get("input", {})
        evaluation = evaluation_by_case.get(conversation.case_id)
        output: dict[str, Any] = {
            "conversation": conversation.model_dump(mode="json"),
            "summary": {
                "coverage_success": conversation.coverage_success,
                "triggered_targets": conversation.triggered_targets,
                "missing_targets": conversation.missing_targets,
                "risk_flags": [item.model_dump(mode="json") for item in conversation.risk_flags],
                "turn_count": len(conversation.turns),
                "end_reason": conversation.end_reason,
            },
        }
        if evaluation is not None:
            output["evaluation"] = evaluation.model_dump(mode="json")
            output["summary"].update(
                {
                    "total_score": evaluation.total_score,
                    "passed": evaluation.passed,
                    "veto_triggered": evaluation.veto_triggered,
                    "risk_deduction_total": evaluation.risk_deduction_total,
                }
            )
        metadata = {
            **dict(seed.get("metadata") or {}),
            "dialogueeval_dataset_type": "generated_dialogue",
            "run_id": run_id,
            "experiment_id": experiment_id,
            "run_dir": str(Path(run_dir)),
        }
        examples.append(
            {
                "input": seed_input,
                "output": output,
                "metadata": metadata,
            }
        )
    return examples


def default_case_seed_dataset_name(scene_id: str) -> str:
    return f"dialogueeval_case_seeds_{_safe_dataset_suffix(scene_id)}"


def default_generated_dialogue_dataset_name(scene_id: str) -> str:
    return f"dialogueeval_generated_dialogues_{_safe_dataset_suffix(scene_id)}"


def _publish_examples(
    *,
    name: str,
    dataset_type: str,
    examples: list[dict[str, Any]],
    description: str,
    base_url: str | None,
    dry_run: bool,
) -> PhoenixDatasetPublishResult:
    resolved_base_url = (base_url or os.getenv("PHOENIX_BASE_URL") or "http://127.0.0.1:6006").rstrip("/")
    if dry_run:
        return PhoenixDatasetPublishResult(
            name=name,
            dataset_type=dataset_type,
            status="dry_run",
            example_count=len(examples),
            base_url=resolved_base_url,
            dry_run=True,
        )
    if not examples:
        return PhoenixDatasetPublishResult(
            name=name,
            dataset_type=dataset_type,
            status="skipped",
            example_count=0,
            base_url=resolved_base_url,
            error="No examples to publish.",
        )

    client = _phoenix_client(base_url=resolved_base_url)
    try:
        dataset = client.datasets.add_examples_to_dataset(
            dataset=name,
            examples=examples,
            timeout=60,
        )
        status = "version_added"
    except Exception as add_exc:
        try:
            dataset = client.datasets.create_dataset(
                name=name,
                examples=examples,
                dataset_description=description,
                timeout=60,
            )
            status = "created"
        except Exception as create_exc:
            raise RuntimeError(
                f"Failed to publish Phoenix dataset {name}: "
                f"add_examples_to_dataset failed with {add_exc}; "
                f"create_dataset failed with {create_exc}"
            ) from create_exc

    dataset_fields = _dataset_fields(dataset)
    return PhoenixDatasetPublishResult(
        name=name,
        dataset_type=dataset_type,
        status=status,
        example_count=len(examples),
        base_url=resolved_base_url,
        dataset_id=str(dataset_fields.get("id") or dataset_fields.get("dataset_id") or ""),
        version_id=str(dataset_fields.get("version_id") or dataset_fields.get("latest_version_id") or ""),
    )


def _phoenix_client(*, base_url: str):
    try:
        from phoenix.client import Client
    except Exception as exc:
        raise RuntimeError(
            "arize-phoenix-client is required for Phoenix dataset publishing. "
            "Install it with `pip install arize-phoenix-client`."
        ) from exc
    return Client(base_url=base_url)


def _asset_reference(
    *,
    assets: GeneratedAssets,
    asset_dir: str | Path,
    asset_version_id: str,
) -> dict[str, Any]:
    return {
        "scene_id": assets.scene_asset.scene_id,
        "scene_name": assets.scene_asset.scene_name,
        "asset_version_id": asset_version_id,
        "asset_dir": str(Path(asset_dir)),
        "source_eval_standard_path": assets.scene_asset.source_eval_standard_path,
        "input_hash": assets.scene_asset.generation_metadata.input_hash,
        "asset_version": assets.scene_asset.generation_metadata.asset_version,
    }


def _task_definition(assets: GeneratedAssets) -> dict[str, Any]:
    return {
        "business_goal": assets.scene_asset.business_goal,
        "agent_role": assets.scene_asset.agent_role,
        "user_role": assets.scene_asset.user_role,
        "success_definition": assets.scene_asset.success_definition,
        "agent_instruction": assets.scene_asset.agent_instruction.model_dump(mode="json"),
        "knowledge_items": [item.model_dump(mode="json") for item in assets.scene_asset.knowledge_items],
        "compliance_rules": [item.model_dump(mode="json") for item in assets.scene_asset.compliance_rules],
    }


def _scoring_reference(assets: GeneratedAssets) -> dict[str, Any]:
    return {
        "total_score": assets.scoring_rubric.total_score,
        "pass_threshold": assets.scoring_rubric.pass_threshold,
        "dimension_ids": [item.dimension_id for item in assets.scoring_rubric.dimensions],
        "veto_rule_ids": [item.rule_id for item in assets.scoring_rubric.veto_rules],
        "risk_rule_ids": [item.rule_id for item in assets.scoring_rubric.risk_rules],
    }


def _case_metadata(
    *,
    assets: GeneratedAssets,
    asset_version_id: str,
    case_id: str,
    priority: str,
    matrix_id: str,
    profile_id: str,
    dataset_type: str,
) -> dict[str, Any]:
    return {
        "dialogueeval_dataset_type": dataset_type,
        "scene_id": assets.scene_asset.scene_id,
        "scene_name": assets.scene_asset.scene_name,
        "asset_version_id": asset_version_id,
        "case_id": case_id,
        "priority": priority,
        "matrix_id": matrix_id,
        "profile_id": profile_id,
        "source_eval_standard_path": assets.scene_asset.source_eval_standard_path,
        "input_hash": assets.scene_asset.generation_metadata.input_hash,
    }


def _dataset_fields(dataset: Any) -> dict[str, Any]:
    if isinstance(dataset, dict):
        return dataset
    if hasattr(dataset, "model_dump"):
        try:
            value = dataset.model_dump()
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    fields: dict[str, Any] = {}
    for key in ("id", "dataset_id", "name", "version_id", "latest_version_id"):
        value = getattr(dataset, key, "")
        if value:
            fields[key] = value
    return fields


def _safe_dataset_suffix(value: str) -> str:
    chars = []
    for char in value.strip():
        if char.isalnum() or char in {"_", "-"}:
            chars.append(char)
        elif char.isspace():
            chars.append("_")
    suffix = "".join(chars).strip("_-")
    return suffix or "scene"
