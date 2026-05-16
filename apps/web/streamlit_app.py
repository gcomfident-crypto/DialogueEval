from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="DialogueEval",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("DialogueEval")
    st.caption("用户模拟器资产生成、对话仿真、量化评测与报告查看")

    page = st.sidebar.radio(
        "页面",
        ["Dashboard", "生成资产", "运行评测", "报告", "模型调用"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.text_input("API Base URL", value=API_BASE_URL, key="api_base_url")

    if page == "Dashboard":
        render_dashboard()
    elif page == "生成资产":
        render_asset_generation()
    elif page == "运行评测":
        render_run_evaluation()
    elif page == "报告":
        render_reports()
    elif page == "模型调用":
        render_llm_calls()


def render_dashboard() -> None:
    health = safe_get("/health")
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    runs = safe_get("/runs", default={"runs": []}).get("runs", [])
    latest_run = runs[0] if runs else {}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("API", health.get("status", "unavailable") if health else "unavailable")
    col2.metric("场景资产", len(assets))
    col3.metric("运行记录", len(runs))
    col4.metric("最近平均分", value_or_dash(latest_run.get("average_score")))

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("已有场景")
        if assets:
            st.dataframe(
                _select_columns(
                    pd.DataFrame(assets),
                    [
                        "scene_id",
                        "scene_name",
                        "case_count",
                        "coverage_label_count",
                        "profile_count",
                        "asset_schema",
                        "valid",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有生成过场景资产。")

    with right:
        st.subheader("最近运行")
        if runs:
            st.dataframe(
                _select_columns(
                    pd.DataFrame(runs),
                    [
                        "run_id",
                        "case_count",
                        "coverage_success_count",
                        "evaluation_count",
                        "passed_count",
                        "average_score",
                        "risk_count",
                    ],
                ).head(8),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有运行记录。")


def render_asset_generation() -> None:
    st.subheader("生成场景资产")
    uploaded = st.file_uploader(
        "任务模板文件",
        type=["md", "markdown", "xlsx", "xlsm", "xltx", "xltm"],
    )
    if uploaded is not None:
        st.info(f"已选择：{uploaded.name}")

    col1, col2 = st.columns(2)
    with col1:
        business_config_path = st.text_input("业务配置路径", value="")
        generation_policy_path = st.text_input(
            "生成策略路径",
            value="configs/generation_policy.yaml",
        )
        output_root = st.text_input("资产输出目录", value="outputs/assets")
    with col2:
        model_config_path = st.text_input("模型配置路径", value="configs/model_config.yaml")
        fake_llm = st.checkbox("使用 fake LLM", value=False)

    if st.button("生成场景资产", type="primary"):
        if uploaded is None:
            st.error("请先上传任务模板文件。")
            return
        uploaded_info = upload_file(uploaded)
        if not uploaded_info:
            return

        payload: dict[str, Any] = {
            "eval_standard_file_path": uploaded_info["path"],
            "business_config_path": business_config_path or None,
            "generation_policy_path": generation_policy_path,
            "model_config_path": model_config_path,
            "output_root": output_root,
            "fake_llm": fake_llm,
        }

        with st.spinner("正在生成资产..."):
            result = safe_post("/assets/generate", payload)
        if result:
            st.success(f"生成完成：{result.get('count', 0)} 个场景资产")
            st.json(result)

    render_asset_viewer()


def render_run_evaluation() -> None:
    st.subheader("运行评测")
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    valid_assets = [item for item in assets if item.get("valid")]
    scene_ids = [item["scene_id"] for item in valid_assets]

    if not scene_ids:
        st.warning("没有可运行的场景资产。")
        return

    col1, col2 = st.columns(2)
    with col1:
        scene_id = st.selectbox("场景资产", scene_ids)
        limit = st.number_input("case 数量，0 表示全量", min_value=0, value=0, step=1)
        business_config_path = st.text_input("业务配置路径", value="")
    with col2:
        model_config_path = st.text_input("模型配置路径", value="configs/model_config.yaml")
        output_root = st.text_input("运行输出目录", value="outputs/runs")
        skip_evaluation = st.checkbox("只跑对话，不生成评分报告", value=False)
        fake_llm = st.checkbox("使用 fake LLM", value=False)

    if st.button("开始运行", type="primary"):
        payload = {
            "scene_id": scene_id,
            "business_config_path": business_config_path or None,
            "model_config_path": model_config_path,
            "output_root": output_root,
            "limit": int(limit) or None,
            "skip_evaluation": skip_evaluation,
            "fake_llm": fake_llm,
        }
        with st.spinner("正在运行对话仿真与评测..."):
            result = safe_post("/runs", payload)
        if result:
            st.success(f"运行完成：{result.get('run_id')}")
            st.json(result)


def render_reports() -> None:
    st.subheader("报告")
    runs = safe_get("/runs", default={"runs": []}).get("runs", [])
    if not runs:
        st.warning("还没有运行记录。")
        return

    run_id = st.selectbox("运行记录", [item["run_id"] for item in runs])
    selected = next((item for item in runs if item["run_id"] == run_id), {})
    st.caption(selected.get("display_path", ""))

    tab_total, tab_coverage, tab_cases, tab_raw = st.tabs(
        ["总评分报告", "覆盖汇总", "Case 子报告", "原始文件"]
    )
    with tab_total:
        render_markdown_report(run_id, "evaluation_report.md")
    with tab_coverage:
        render_markdown_report(run_id, "summary_report.md")
    with tab_cases:
        case_ids = safe_get(f"/runs/{run_id}/case_reports", default={"case_reports": []}).get(
            "case_reports",
            [],
        )
        if case_ids:
            case_id = st.selectbox("case", case_ids)
            text = safe_get_text(f"/runs/{run_id}/case_reports/{case_id}")
            if text:
                st.markdown(text)
        else:
            st.info("该运行还没有 case 子报告。")
    with tab_raw:
        file_name = st.selectbox(
            "文件",
            [
                "conversation_log.jsonl",
                "case_evaluation.jsonl",
                "coverage_report.csv",
                "evaluation_report.csv",
                "llm_calls.jsonl",
            ],
        )
        text = safe_get_text(f"/runs/{run_id}/reports/{file_name}")
        if text:
            st.code(text, language="json" if file_name.endswith(".jsonl") else "text")


def render_llm_calls() -> None:
    st.subheader("模型调用")
    runs = safe_get("/runs", default={"runs": []}).get("runs", [])
    if not runs:
        st.warning("还没有运行记录。")
        return

    run_id = st.selectbox("运行记录", [item["run_id"] for item in runs])
    text = safe_get_text(f"/runs/{run_id}/reports/llm_calls.jsonl")
    rows = parse_jsonl(text)
    if not rows:
        st.info("该运行没有模型调用记录。")
        return

    frame = pd.DataFrame(rows)
    columns = [
        "started_at",
        "task_name",
        "role",
        "model",
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "success",
        "error",
    ]
    st.dataframe(_select_columns(frame, columns), use_container_width=True)


def render_asset_viewer() -> None:
    st.divider()
    st.subheader("资产查看")
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    valid_assets = [item for item in assets if item.get("valid")]
    if not valid_assets:
        st.info("生成后可在这里查看 scene_asset、coverage_plan、user_profiles、case_cards 和 scoring_rubric。")
        return

    scene_id = st.selectbox("场景", [item["scene_id"] for item in valid_assets])
    file_name = st.selectbox(
        "资产文件",
        [
            "scene_asset.yaml",
            "coverage_plan.yaml",
            "user_profiles.yaml",
            "case_cards.yaml",
            "scoring_rubric.yaml",
            "materialized_eval_standard.md",
            "variable_assignments.yaml",
            "asset_generation_report.md",
        ],
    )
    text = safe_get_text(f"/assets/{scene_id}/files/{file_name}")
    if text:
        if file_name.endswith(".md"):
            st.markdown(text)
        else:
            st.code(text, language="json")


def render_markdown_report(run_id: str, filename: str) -> None:
    text = safe_get_text(f"/runs/{run_id}/reports/{filename}")
    if text:
        st.markdown(text)
    else:
        st.info(f"未找到 {filename}。")


def upload_file(uploaded_file) -> dict[str, Any] | None:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
    return safe_post("/files/upload", files=files)


def safe_get(path: str, default: Any | None = None) -> Any:
    try:
        response = requests.get(api_url(path), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        if default is not None:
            return default
        st.error(f"API 请求失败：{exc}")
        return {}


def safe_get_text(path: str) -> str:
    try:
        response = requests.get(api_url(path), timeout=10)
        response.raise_for_status()
        return response.text
    except Exception:
        return ""


def safe_post(path: str, payload: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> Any:
    try:
        if files:
            response = requests.post(api_url(path), files=files, timeout=120)
        else:
            response = requests.post(api_url(path), json=payload or {}, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        st.error(f"API 返回错误：{detail or exc}")
        return None
    except Exception as exc:
        st.error(f"API 请求失败：{exc}")
        return None


def api_url(path: str) -> str:
    base = st.session_state.get("api_base_url", API_BASE_URL).rstrip("/")
    return f"{base}{path}"


def parse_jsonl(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def value_or_dash(value: Any) -> Any:
    return "-" if value is None else value


def _select_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    available = [column for column in columns if column in frame.columns]
    return frame[available] if available else frame


if __name__ == "__main__":
    main()
