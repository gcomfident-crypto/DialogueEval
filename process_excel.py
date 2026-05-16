import os
import pandas as pd


def process_excel_to_markdown(excel_path: str, base_output_dir: str = "Resource") -> None:
    """
    读取 Excel 文件，将每一行任务提取成 Markdown 文件。

    Args:
        excel_path: Excel 文件的路径。
        base_output_dir: Markdown 文件的基础输出目录。
    """
    output_dir = os.path.join(base_output_dir, "tasks")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # 读取 Excel 文件，假设第一行是表头
        df = pd.read_excel(excel_path)
    except FileNotFoundError:
        print(f"错误：未找到文件 '{excel_path}'。")
        return
    except Exception as e:
        print(f"读取 Excel 文件时发生错误：{e}")
        return

    task_column = "任务指令示例"
    if task_column not in df.columns:
        print(f"错误：未找到列 '{task_column}'。")
        return

    for index, row in df.iterrows():
        task_value = row.get(task_column)
        if pd.isna(task_value) or str(task_value).strip() == "":
            print(f"跳过任务内容为空的行：第 {index + 2} 行。")
            continue

        task_content = ""
        for col_name, cell_value in row.items():
            if pd.notna(cell_value) and str(cell_value).strip() != "":
                task_content += f"**{col_name}**: {cell_value}\n\n"

        file_name = f"Task_{index + 1}.md"
        output_file_path = os.path.join(output_dir, file_name)

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(task_content)
        print(f"已生成文件：{output_file_path}")

if __name__ == "__main__":
    excel_file = "/Users/zzx/workspace/DialogueEval/命题二：外呼任务对话模型指令示例.xlsx"
    process_excel_to_markdown(excel_file)
