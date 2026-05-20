from __future__ import annotations

from dialogue_simulator.schemas import CoveragePlan, SceneAsset, ScoringRubric


def validate_scoring_rubric(
    *,
    scoring_rubric: ScoringRubric,
    coverage_plan: CoveragePlan,
    scene_asset: SceneAsset,
) -> list[str]:
    errors: list[str] = []
    if abs(scoring_rubric.total_score - 100.0) > 0.01:
        errors.append(f"total_score must be 100, got {scoring_rubric.total_score:g}")

    dimension_total = sum(float(item.weight) for item in scoring_rubric.dimensions)
    if abs(dimension_total - scoring_rubric.total_score) > 0.01:
        errors.append(
            "dimension weights must sum to total_score, "
            f"got {dimension_total:g}/{scoring_rubric.total_score:g}"
        )

    check_label_ids: set[str] = set()
    for dimension in scoring_rubric.dimensions:
        if not dimension.check_items:
            errors.append(f"dimension {dimension.dimension_id} has no check_items")
            continue
        check_total = sum(float(item.points) for item in dimension.check_items)
        if abs(check_total - dimension.weight) > 0.01:
            errors.append(
                f"check_items in {dimension.dimension_id} must sum to dimension weight, "
                f"got {check_total:g}/{dimension.weight:g}"
            )
        for check_item in dimension.check_items:
            check_label_ids.update(check_item.covered_labels)

    p0_labels = {
        item.label
        for item in coverage_plan.coverage_labels
        if item.priority == "P0"
    }
    missing_p0 = sorted(p0_labels - check_label_ids)
    if missing_p0:
        errors.append("P0 coverage labels not mapped to check_items: " + ", ".join(missing_p0))

    risk_ids = {item.rule_id for item in scoring_rubric.risk_rules}
    veto_ids = {item.rule_id for item in scoring_rubric.veto_rules}
    overlap = sorted(risk_ids & veto_ids)
    if overlap:
        errors.append("risk_rules and veto_rules must not share rule_id: " + ", ".join(overlap))

    mapped_rule_ids = risk_ids | veto_ids
    missing_compliance = [
        item.id
        for item in scene_asset.compliance_rules
        if item.id and item.id not in mapped_rule_ids
    ]
    if missing_compliance:
        errors.append(
            "compliance rules not mapped to risk_rules or veto_rules: "
            + ", ".join(sorted(missing_compliance))
        )
    return errors


def assert_valid_scoring_rubric(
    *,
    scoring_rubric: ScoringRubric,
    coverage_plan: CoveragePlan,
    scene_asset: SceneAsset,
) -> None:
    errors = validate_scoring_rubric(
        scoring_rubric=scoring_rubric,
        coverage_plan=coverage_plan,
        scene_asset=scene_asset,
    )
    if errors:
        raise ValueError("invalid scoring_rubric: " + "；".join(errors))
