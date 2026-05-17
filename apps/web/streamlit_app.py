from __future__ import annotations

import json
import os
import html
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PHOENIX_UI_URL = os.getenv("PHOENIX_UI_URL", "http://127.0.0.1:6006").rstrip("/")

st.set_page_config(
    page_title="DialogueEval",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --de-surface: #ffffff;
            --de-border: #d9e2ec;
            --de-muted: #5f6f80;
            --de-strong: #12263a;
            --de-accent: #2563eb;
            --de-success: #16834a;
            --de-warning: #b7791f;
            --de-danger: #c2410c;
        }
        .stApp {
            background: #f6f8fb;
            color: var(--de-strong);
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--de-border);
        }
        div[data-testid="stMetric"] {
            background: var(--de-surface);
            border: 1px solid var(--de-border);
            border-radius: 8px;
            padding: 14px 16px;
        }
        div[data-testid="stMetric"] label {
            color: var(--de-muted);
        }
        .de-title {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0;
            margin: 0 0 4px 0;
        }
        .de-subtitle {
            color: var(--de-muted);
            margin-bottom: 18px;
        }
        .de-panel {
            background: var(--de-surface);
            border: 1px solid var(--de-border);
            border-radius: 8px;
            padding: 18px;
            margin: 10px 0 16px 0;
        }
        .de-section-title {
            font-size: 17px;
            font-weight: 650;
            margin-bottom: 10px;
        }
        .de-muted {
            color: var(--de-muted);
        }
        .de-chip {
            display: inline-block;
            border: 1px solid var(--de-border);
            border-radius: 999px;
            padding: 2px 9px;
            font-size: 12px;
            background: #f8fafc;
            color: var(--de-muted);
            margin-right: 6px;
        }
        .de-chip-success {
            border-color: #b7e4cc;
            color: var(--de-success);
            background: #eefaf3;
        }
        .de-chip-warning {
            border-color: #f4d68b;
            color: var(--de-warning);
            background: #fff8e6;
        }
        .de-chip-danger {
            border-color: #f4b7a4;
            color: var(--de-danger);
            background: #fff3ee;
        }
        .de-turn {
            border: 1px solid var(--de-border);
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0;
            background: #ffffff;
        }
        .de-turn-agent {
            border-left: 4px solid #2563eb;
        }
        .de-turn-user {
            border-left: 4px solid #16a34a;
        }
        .de-turn-role {
            font-size: 12px;
            font-weight: 650;
            color: var(--de-muted);
            margin-bottom: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='de-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='de-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def status_chip(label: str, tone: str = "") -> str:
    class_name = "de-chip"
    if tone:
        class_name += f" de-chip-{tone}"
    return f"<span class='{class_name}'>{label}</span>"


def main() -> None:
    apply_theme()

    page = st.sidebar.radio(
        "DialogueEval",
        ["工作台", "新建评测", "报告中心", "场景资产", "实验库", "系统设置"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.text_input("API Base URL", value=API_BASE_URL, key="api_base_url")
    st.sidebar.link_button("Trace 调试", PHOENIX_UI_URL)

    if page == "工作台":
        render_dashboard()
    elif page == "新建评测":
        render_new_evaluation()
    elif page == "报告中心":
        render_reports()
    elif page == "场景资产":
        render_asset_center()
    elif page == "实验库":
        render_registry()
    elif page == "系统设置":
        render_system_settings()


def render_dashboard() -> None:
    page_header("评测工作台", "集中查看最近运行、风险状态和系统健康度。")
    health = safe_get("/health")
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    runs = safe_get("/runs", default={"runs": []}).get("runs", [])
    latest_run = runs[0] if runs else {}

    tracing = (health or {}).get("tracing", {})

    registry = (health or {}).get("registry", {})

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("服务", health.get("status", "unavailable") if health else "unavailable")
    col2.metric("场景资产", len(assets))
    col3.metric("运行记录", len(runs))
    col4.metric("最近平均分", value_or_dash(latest_run.get("average_score")))
    col5.metric("沉淀实验", registry.get("experiments", 0))
    col6.metric("Trace", "on" if tracing.get("configured") else "off")

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("<div class='de-section-title'>最近评测</div>", unsafe_allow_html=True)
        if runs:
            frame = pd.DataFrame(runs).head(8)
            frame["通过率"] = frame.apply(_run_pass_rate, axis=1)
            st.dataframe(
                _select_columns(
                    frame,
                    [
                        "run_id",
                        "case_count",
                        "evaluation_count",
                        "passed_count",
                        "通过率",
                        "average_score",
                        "risk_count",
                        "veto_count",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有运行记录。")

    with right:
        st.markdown("<div class='de-section-title'>资产概览</div>", unsafe_allow_html=True)
        if assets:
            st.dataframe(
                _select_columns(
                    pd.DataFrame(assets).head(8),
                    ["scene_name", "scene_id", "case_count", "coverage_label_count", "valid"],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有场景资产。")

    if latest_run:
        st.markdown("<div class='de-section-title'>最近一次结果</div>", unsafe_allow_html=True)
        chips = [
            status_chip(f"run: {latest_run.get('run_id', '-')}", ""),
            status_chip(f"平均分 {value_or_dash(latest_run.get('average_score'))}", _score_tone(latest_run.get("average_score"))),
            status_chip(f"风险 {latest_run.get('risk_count', 0)}", "danger" if latest_run.get("risk_count") else "success"),
            status_chip(f"一票否决 {latest_run.get('veto_count', 0)}", "danger" if latest_run.get("veto_count") else "success"),
        ]
        st.markdown("".join(chips), unsafe_allow_html=True)


def render_new_evaluation() -> None:
    page_header("新建评测", "上传任务文件，生成或复用场景资产，然后直接运行评测。")

    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    valid_assets = [item for item in assets if item.get("valid")]
    generated_assets = st.session_state.get("last_generated_assets", [])

    step1, step2, step3 = st.tabs(["1. 任务输入", "2. 场景资产", "3. 运行评测"])
    with step1:
        uploaded = st.file_uploader(
            "任务文件",
            type=["md", "markdown", "csv", "xlsx", "xlsm", "xltx", "xltm"],
        )
        if uploaded is not None:
            st.caption(f"已选择：{uploaded.name}")

        with st.expander("高级配置", expanded=False):
            left, right = st.columns(2)
            with left:
                business_config_path = st.text_input("业务配置路径", value="", key="new_business_config")
                generation_policy_path = st.text_input(
                    "生成策略路径",
                    value="configs/generation_policy.yaml",
                    key="new_generation_policy",
                )
                output_root = st.text_input("资产输出目录", value="outputs/assets", key="new_asset_output")
            with right:
                model_config_path = st.text_input("模型配置路径", value="configs/model_config.yaml", key="new_model_config")
                fake_llm = st.checkbox("使用 fake LLM", value=False, key="new_fake_asset")

        if st.button("生成场景资产", type="primary", use_container_width=True):
            if uploaded is None:
                st.error("请先上传任务文件。")
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

            with st.spinner("正在生成或复用场景资产..."):
                result = safe_post("/assets/generate", payload)
            if result:
                st.session_state["last_generated_assets"] = result.get("assets", [])
                st.success(f"完成：{result.get('count', 0)} 个场景资产")
                st.dataframe(
                    _asset_display_frame(result.get("assets", [])),
                    use_container_width=True,
                    hide_index=True,
                )

    with step2:
        display_assets = generated_assets or valid_assets
        if display_assets:
            st.dataframe(_asset_display_frame(display_assets), use_container_width=True, hide_index=True)
            selected = st.selectbox(
                "选择要运行的场景资产",
                [item["scene_id"] for item in display_assets if item.get("valid", True)],
                key="new_selected_asset",
            )
            st.session_state["selected_scene_id"] = selected
        else:
            st.info("还没有可运行的场景资产。")

    with step3:
        scene_ids = [item["scene_id"] for item in valid_assets]
        default_scene = st.session_state.get("selected_scene_id")
        default_index = scene_ids.index(default_scene) if default_scene in scene_ids else 0
        if not scene_ids:
            st.warning("请先生成场景资产。")
            return

        left, right = st.columns(2)
        with left:
            scene_id = st.selectbox("场景资产", scene_ids, index=default_index)
            limit = st.number_input("case 数量，0 表示全量", min_value=0, value=0, step=1)
            run_business_config_path = st.text_input("业务配置路径", value="", key="run_business_config")
        with right:
            run_model_config_path = st.text_input("模型配置路径", value="configs/model_config.yaml", key="run_model_config")
            output_root = st.text_input("运行输出目录", value="outputs/runs", key="run_output")
            skip_evaluation = st.checkbox("只跑对话，不生成评分报告", value=False)
            fake_llm = st.checkbox("使用 fake LLM", value=False, key="run_fake_llm")

        if st.button("开始评测", type="primary", use_container_width=True):
            payload = {
                "scene_id": scene_id,
                "business_config_path": run_business_config_path or None,
                "model_config_path": run_model_config_path,
                "output_root": output_root,
                "limit": int(limit) or None,
                "skip_evaluation": skip_evaluation,
                "fake_llm": fake_llm,
            }
            with st.spinner("正在运行对话仿真与评分..."):
                result = safe_post("/runs", payload)
            if result:
                st.session_state["last_run_id"] = result.get("run_id")
                st.success(f"评测完成：{result.get('run_id')}")
                show_run_summary(result)


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
    page_header("报告中心", "从总览进入 case 明细，直接查看原始对话、评分证据和风险扣分。")
    runs = safe_get("/runs", default={"runs": []}).get("runs", [])
    if not runs:
        st.warning("还没有运行记录。")
        return

    default_run = st.session_state.get("last_run_id")
    run_ids = [item["run_id"] for item in runs]
    default_index = run_ids.index(default_run) if default_run in run_ids else 0
    run_id = st.selectbox("运行记录", run_ids, index=default_index)
    selected = next((item for item in runs if item["run_id"] == run_id), {})
    show_run_summary(selected)

    evaluations = parse_jsonl(safe_get_text(f"/runs/{run_id}/reports/case_evaluation.jsonl"))
    conversations = parse_jsonl(safe_get_text(f"/runs/{run_id}/reports/conversation_log.jsonl"))
    conversation_map = {item.get("case_id"): item for item in conversations}

    tab_overview, tab_cases, tab_report, tab_raw = st.tabs(
        ["结果总览", "Case 明细", "Markdown 报告", "原始文件"]
    )
    with tab_overview:
        if evaluations:
            frame = pd.DataFrame(evaluations)
            st.dataframe(
                _select_columns(
                    frame,
                    [
                        "case_id",
                        "priority",
                        "total_score",
                        "pass_threshold",
                        "passed",
                        "veto_triggered",
                        "coverage_success",
                        "missing_targets",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
            render_missing_targets_summary(evaluations)
        else:
            st.info("该运行没有评分结果。")

    with tab_cases:
        case_ids = [item.get("case_id") for item in evaluations] or [
            item.get("case_id") for item in conversations
        ]
        case_ids = [case_id for case_id in case_ids if case_id]
        if case_ids:
            case_id = st.selectbox("case", case_ids)
            evaluation = next((item for item in evaluations if item.get("case_id") == case_id), {})
            conversation = conversation_map.get(case_id, {})
            render_case_detail(case_id, evaluation, conversation)
        else:
            st.info("该运行没有 case 记录。")
    with tab_report:
        report_file = st.radio(
            "报告",
            ["evaluation_report.md", "summary_report.md"],
            horizontal=True,
            label_visibility="collapsed",
        )
        render_markdown_report(run_id, report_file)
    with tab_raw:
        file_name = st.selectbox(
            "文件",
            [
                "conversation_log.jsonl",
                "simulation_state_trace.jsonl",
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
    st.subheader("模型调用记录")
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
        "message_count",
        "prompt_chars",
        "completion_chars",
        "prompt_hash",
        "completion_hash",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "success",
        "error",
    ]
    st.dataframe(_select_columns(frame, columns), use_container_width=True)


def render_asset_center() -> None:
    page_header("场景资产", "查看模型生成的场景说明、评测检查点、用户画像、测试用例和评分规则。")
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    valid_assets = [item for item in assets if item.get("valid")]
    if valid_assets:
        st.dataframe(_asset_display_frame(valid_assets), use_container_width=True, hide_index=True)
    else:
        st.info("还没有场景资产。")
    render_asset_viewer()


def render_registry() -> None:
    page_header("实验库", "沉淀输入数据、资产版本、实验运行和 case 结果，用于复现与对比。")
    status = safe_get("/registry/status", default={})
    if status:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Datasets", status.get("datasets", 0))
        col2.metric("Task 指令", status.get("task_instructions", 0))
        col3.metric("资产版本", status.get("asset_versions", 0))
        col4.metric("Experiments", status.get("experiments", 0))
        col5.metric("Case Runs", status.get("case_runs", 0))
        st.caption(status.get("path", ""))

    if st.button("扫描已有 outputs 并回填实验库"):
        result = safe_post("/registry/index-existing", {})
        if result:
            st.success("回填完成")
            st.json(result)

    tab_datasets, tab_experiments = st.tabs(["Datasets", "Experiments"])
    with tab_datasets:
        datasets = safe_get("/registry/datasets", default={"datasets": []}).get("datasets", [])
        if datasets:
            st.dataframe(
                _select_columns(
                    pd.DataFrame(datasets),
                    [
                        "dataset_id",
                        "source_type",
                        "source_path",
                        "source_hash",
                        "created_at",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有沉淀 dataset。")
    with tab_experiments:
        experiments = safe_get("/registry/experiments", default={"experiments": []}).get(
            "experiments",
            [],
        )
        if experiments:
            st.dataframe(
                _select_columns(
                    pd.DataFrame(experiments),
                    [
                        "experiment_id",
                        "run_id",
                        "scene_id",
                        "asset_version_id",
                        "status",
                        "started_at",
                        "completed_at",
                        "run_dir",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("还没有沉淀 experiment。")


def render_prompts() -> None:
    st.subheader("Prompt 管理")
    status = safe_get("/prompts/status", default={})
    if status:
        col1, col2, col3 = st.columns(3)
        col1.metric("Provider", status.get("provider") or "local")
        col2.metric("Phoenix", "on" if status.get("enabled") else "off")
        col3.metric("Prompt 数量", status.get("prompt_count", 0))
        st.caption(status.get("phoenix_base_url", ""))

    prompts = status.get("prompts", []) if status else []
    if prompts:
        st.dataframe(
            _select_columns(pd.DataFrame(prompts), ["name", "role", "description", "variables"]),
            use_container_width=True,
            hide_index=True,
        )

    model_name = st.text_input("同步记录模型名", value="deepseek-chat")
    dry_run = st.checkbox("只预览，不写入 Phoenix", value=False)
    if st.button("同步默认提示词到 Phoenix", type="primary"):
        result = safe_post(
            "/prompts/sync",
            {
                "model_name": model_name,
                "dry_run": dry_run,
            },
        )
        if result:
            st.success(f"同步完成：{result.get('count', 0)} 个提示词")
            st.dataframe(pd.DataFrame(result.get("results", [])), use_container_width=True, hide_index=True)


def render_system_settings() -> None:
    page_header("系统设置", "查看 Prompt、模型调用和服务状态；业务使用时通常不需要进入。")
    tab_prompts, tab_calls, tab_health = st.tabs(["Prompt 管理", "模型调用", "服务状态"])
    with tab_prompts:
        render_prompts()
    with tab_calls:
        render_llm_calls()
    with tab_health:
        health = safe_get("/health", default={})
        st.json(health)


def render_asset_viewer() -> None:
    assets = safe_get("/assets", default={"assets": []}).get("assets", [])
    valid_assets = [item for item in assets if item.get("valid")]
    if not valid_assets:
        return

    st.markdown("<div class='de-section-title'>资产文件</div>", unsafe_allow_html=True)
    scene_id = st.selectbox("场景", [item["scene_id"] for item in valid_assets])
    file_name = st.selectbox(
        "文件",
        [
            "scene_asset.yaml",
            "coverage_plan.yaml",
            "coverage_taxonomy.yaml",
            "coverage_matrix.yaml",
            "case_generation_plan.yaml",
            "user_profiles.yaml",
            "case_cards.yaml",
            "scoring_rubric.yaml",
            "materialized_eval_standard.md",
            "variable_assignments.yaml",
            "asset_generation_report.md",
            "coverage_gap_report.md",
        ],
    )
    text = safe_get_text(f"/assets/{scene_id}/files/{file_name}")
    if text:
        if file_name.endswith(".md"):
            st.markdown(text)
        else:
            st.code(text, language="json")


def show_run_summary(run: dict[str, Any]) -> None:
    if not run:
        return
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Case 数", run.get("case_count", 0))
    col2.metric("已评分", run.get("evaluation_count", 0))
    col3.metric("通过数", run.get("passed_count", 0))
    col4.metric("平均分", value_or_dash(run.get("average_score")))
    col5.metric("风险", run.get("risk_count", 0))
    chips = [
        status_chip(run.get("run_id", "-")),
        status_chip(f"一票否决 {run.get('veto_count', 0)}", "danger" if run.get("veto_count") else "success"),
        status_chip(run.get("display_path", "")),
    ]
    st.markdown("".join(chips), unsafe_allow_html=True)


def render_missing_targets_summary(evaluations: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for item in evaluations:
        for target in item.get("missing_targets") or []:
            counts[str(target)] = counts.get(str(target), 0) + 1
    if not counts:
        st.success("没有 missing target。")
        return
    rows = [
        {"missing_target": target, "case_count": count}
        for target, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]
    st.markdown("<div class='de-section-title'>高频缺失项</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows).head(12), use_container_width=True, hide_index=True)


def render_case_detail(
    case_id: str,
    evaluation: dict[str, Any],
    conversation: dict[str, Any],
) -> None:
    if evaluation:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总分", value_or_dash(evaluation.get("total_score")))
        col2.metric("合格线", value_or_dash(evaluation.get("pass_threshold")))
        col3.metric("通过", "是" if evaluation.get("passed") else "否")
        col4.metric("风险扣分", value_or_dash(evaluation.get("risk_deduction_total")))

        st.markdown(
            "".join(
                [
                    status_chip(case_id),
                    status_chip("通过" if evaluation.get("passed") else "未通过", "success" if evaluation.get("passed") else "danger"),
                    status_chip("一票否决" if evaluation.get("veto_triggered") else "无一票否决", "danger" if evaluation.get("veto_triggered") else "success"),
                ]
            ),
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("<div class='de-section-title'>原始对话</div>", unsafe_allow_html=True)
        turns = conversation.get("turns") or []
        if turns:
            for index, turn in enumerate(turns):
                role = turn.get("role", "")
                role_name = "客服" if role == "agent" else "用户"
                class_name = "de-turn-agent" if role == "agent" else "de-turn-user"
                text = html.escape(str(turn.get("text", "")))
                st.markdown(
                    f"""
                    <div class="de-turn {class_name}">
                        <div class="de-turn-role">{index}. {role_name}</div>
                        <div>{text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("没有对话记录。")

    with right:
        st.markdown("<div class='de-section-title'>评分证据</div>", unsafe_allow_html=True)
        scores = evaluation.get("dimension_scores") or []
        if scores:
            score_rows = [
                {
                    "维度": item.get("name"),
                    "得分": item.get("score"),
                    "权重": item.get("weight"),
                    "原因": item.get("reason"),
                    "缺失点": "; ".join(item.get("missing_points") or []),
                }
                for item in scores
            ]
            st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)
        else:
            st.info("没有评分维度。")

        risks = evaluation.get("risk_deductions") or []
        if risks:
            st.markdown("<div class='de-section-title'>风险扣分</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(risks), use_container_width=True, hide_index=True)


def _asset_display_frame(assets: list[dict[str, Any]]) -> pd.DataFrame:
    if not assets:
        return pd.DataFrame()
    frame = pd.DataFrame(assets)
    return _select_columns(
        frame,
        [
            "scene_name",
            "scene_id",
            "case_count",
            "coverage_label_count",
            "profile_count",
            "scoring_dimension_count",
            "pass_threshold",
            "asset_version_id",
            "valid",
        ],
    )


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
            response = requests.post(api_url(path), files=files, timeout=600)
        else:
            response = requests.post(api_url(path), json=payload or {}, timeout=600)
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


def _run_pass_rate(row: pd.Series) -> str:
    total = row.get("evaluation_count") or row.get("case_count") or 0
    passed = row.get("passed_count") or 0
    try:
        total_value = int(total)
        passed_value = int(passed)
    except (TypeError, ValueError):
        return "-"
    if total_value <= 0:
        return "-"
    return f"{passed_value / total_value:.0%}"


def _score_tone(score: Any) -> str:
    if not isinstance(score, (int, float)):
        return ""
    if score >= 80:
        return "success"
    if score >= 60:
        return "warning"
    return "danger"


def _select_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    available = [column for column in columns if column in frame.columns]
    return frame[available] if available else frame


if __name__ == "__main__":
    main()
