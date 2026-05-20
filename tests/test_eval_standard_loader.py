from pathlib import Path

from openpyxl import Workbook

from apps.api.service import GenerateAssetsRequest, TaskRunConfig, _resolve_eval_standard_paths, _task_config_by_path
from dialogue_simulator.eval_standard_loader import extract_markdown_from_excel


def test_extract_markdown_from_excel_second_column_start_second_row(tmp_path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "id"
    worksheet["B1"] = "评测标准"
    worksheet["A2"] = "scene_1"
    worksheet["B2"] = "# 场景1评测标准\n\n## 1. 场景定位"
    worksheet["A3"] = "scene_2"
    worksheet["B3"] = "# 场景2评测标准\n\n## 1. 场景定位"
    excel_path = tmp_path / "standards.xlsx"
    workbook.save(excel_path)

    output_dir = tmp_path / "extracted"
    extracted = extract_markdown_from_excel(excel_path, output_dir)

    assert len(extracted) == 2
    assert extracted[0].source_row == 2
    assert extracted[0].source_column == 2
    assert Path(extracted[0].output_path).read_text(encoding="utf-8").startswith("# 场景1")
    assert Path(extracted[1].output_path).read_text(encoding="utf-8").startswith("# 场景2")


def test_resolve_eval_standard_paths_filters_selected_excel_rows(tmp_path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["B2"] = "# 场景1评测标准\n\n## 任务"
    worksheet["B3"] = "# 场景2评测标准\n\n## 任务"
    excel_path = tmp_path / "standards.xlsx"
    workbook.save(excel_path)

    output_dir = tmp_path / "extracted"
    selected_path = output_dir / "eval_standard_row_003.md"
    paths, items = _resolve_eval_standard_paths(
        GenerateAssetsRequest(
            eval_standard_file_path=str(excel_path),
            extracted_output_dir=str(output_dir),
            selected_eval_standard_paths=[str(selected_path)],
        )
    )

    assert paths == [selected_path]
    assert items[0]["source_row"] == 3


def test_task_config_by_path_keeps_per_task_overrides(tmp_path: Path) -> None:
    eval_standard_path = tmp_path / "task.md"
    request = GenerateAssetsRequest(
        eval_standard_path=str(eval_standard_path),
        task_configs=[
            TaskRunConfig(
                eval_standard_path=str(eval_standard_path),
                asset_output_root="outputs/assets/custom_task",
                run_output_root="outputs/runs/custom_task",
                target_case_count=100,
                limit=0,
            )
        ],
    )

    configs = _task_config_by_path(request)
    config = configs[str(eval_standard_path)]

    assert config.asset_output_root == "outputs/assets/custom_task"
    assert config.run_output_root == "outputs/runs/custom_task"
    assert config.target_case_count == 100
    assert config.limit == 0
