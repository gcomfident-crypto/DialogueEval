"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ClipboardCheck,
  ClipboardList,
  Copy,
  Database,
  Download,
  FileText,
  Gauge,
  History,
  Layers3,
  Loader2,
  MessageSquareText,
  PlayCircle,
  RefreshCw,
  Settings,
  Sparkles,
  Trash2,
  UploadCloud,
  Workflow,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";

type PageKey = "workbench" | "new" | "reports" | "validity" | "annotations" | "admin";
type JsonObject = Record<string, any>;
const sidebarStorageKey = "dialogue-eval-sidebar-collapsed";
const legacyTaskInputStorageKey = "dialogue-eval-task-input";

type TaskConfigState = {
  assetOutput?: string;
  runOutput?: string;
  limit?: string;
};

type TaskInputState = {
  fileName?: string;
  uploadedFile?: JsonObject | null;
  taskPreview?: JsonObject;
  selectedTaskKeys?: string[];
  taskConfigs?: Record<string, TaskConfigState>;
};

const navItems: Array<{ key: PageKey; label: string; icon: ReactNode }> = [
  { key: "workbench", label: "工作台", icon: <Gauge size={18} /> },
  { key: "new", label: "新建评测", icon: <Sparkles size={18} /> },
  { key: "reports", label: "评测报告", icon: <BarChart3 size={18} /> },
  { key: "validity", label: "Case 质检", icon: <ClipboardList size={18} /> },
  { key: "annotations", label: "人工校准", icon: <ClipboardCheck size={18} /> },
  { key: "admin", label: "系统管理", icon: <Settings size={18} /> }
];

const assetFiles = [
  ["scene_asset.yaml", "场景说明"],
  ["coverage_plan.yaml", "评测检查点"],
  ["coverage_taxonomy.yaml", "覆盖分类"],
  ["coverage_matrix.yaml", "覆盖矩阵"],
  ["case_generation_plan.yaml", "Case 生成计划"],
  ["user_profiles.yaml", "用户画像"],
  ["case_cards.yaml", "测试用例"],
  ["scoring_rubric.yaml", "评分规则"],
  ["materialized_eval_standard.md", "实例化任务标准"],
  ["variable_assignments.yaml", "变量替换记录"],
  ["asset_generation_report.md", "资产生成报告"],
  ["coverage_gap_report.md", "覆盖缺口报告"]
];

const rawRunFiles = [
  ["conversation_log.jsonl", "对话记录"],
  ["simulation_state_trace.jsonl", "用户状态轨迹"],
  ["case_evaluation.jsonl", "评分结果"],
  ["coverage_report.csv", "覆盖汇总 CSV"],
  ["evaluation_report.csv", "评分汇总 CSV"],
  ["llm_calls.jsonl", "模型调用"]
];

export default function Home() {
  const [page, setPage] = useState<PageKey>("workbench");
  const [health, setHealth] = useState<JsonObject>({});
  const [assets, setAssets] = useState<JsonObject[]>([]);
  const [runs, setRuns] = useState<JsonObject[]>([]);
  const [registryStatus, setRegistryStatus] = useState<JsonObject>({});
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [taskInputState, setTaskInputState] = useState<TaskInputState>({});
  const [evaluationProgress, setEvaluationProgress] = useState<JsonObject | null>(null);
  const [reportRunId, setReportRunId] = useState("");
  const [reportListResetToken, setReportListResetToken] = useState(0);
  const phoenixUrl = process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006";
  const evaluationRunning = Boolean(evaluationProgress?.job_id && ["queued", "running", "cancelling"].includes(String(evaluationProgress.status || "")));

  async function refresh(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? false;
    if (showLoading) {
      setLoading(true);
    }
    try {
      const [healthData, assetData, runData, registryData] = await Promise.all([
        apiJson("/health"),
        apiJson("/assets"),
        apiJson("/runs"),
        apiJson("/registry/status")
      ]);
      setHealth(healthData);
      setAssets(assetData.assets || []);
      setRuns(runData.runs || []);
      setRegistryStatus(registryData || {});
      setNotice("");
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    refresh({ showLoading: true });
    const interval = window.setInterval(() => refresh(), 30000);
    const syncOnFocus = () => refresh();
    const syncOnVisible = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };
    window.addEventListener("focus", syncOnFocus);
    document.addEventListener("visibilitychange", syncOnVisible);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", syncOnFocus);
      document.removeEventListener("visibilitychange", syncOnVisible);
    };
  }, []);

  useEffect(() => {
    try {
      setSidebarCollapsed(window.localStorage.getItem(sidebarStorageKey) === "true");
      window.localStorage.removeItem(legacyTaskInputStorageKey);
    } catch {
      setSidebarCollapsed(false);
    }
  }, []);

  useEffect(() => {
    const jobId = evaluationProgress?.job_id;
    const status = String(evaluationProgress?.status || "");
    if (!jobId || !["queued", "running", "cancelling"].includes(status)) return;

    let cancelled = false;
    let timer: number | undefined;
    async function pollJob() {
      try {
        const job = await apiJson(`/evaluations/jobs/${jobId}`);
        if (cancelled) return;
        setEvaluationProgress(job);
        if (job.status === "completed") {
          await refresh();
          return;
        }
        if (job.status === "failed") return;
        timer = window.setTimeout(pollJob, 1200);
      } catch (error) {
        if (cancelled) return;
        setEvaluationProgress((current) => ({
          ...(current || { job_id: jobId }),
          status: "failed",
          stage: "进度同步失败",
          message: errorMessage(error),
          error: errorMessage(error)
        }));
      }
    }
    timer = window.setTimeout(pollJob, 1200);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [evaluationProgress?.job_id, evaluationProgress?.status]);

  function toggleSidebar() {
    setSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(sidebarStorageKey, String(next));
      } catch {
        // Local storage can be unavailable in private or restricted browser contexts.
      }
      return next;
    });
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          <span className="sidebar-toggle-icon">
            <ChevronLeft size={18} />
          </span>
        </button>
        <div className="brand">
          <div className="brand-lockup">
            <img className="brand-mark" src="/logo-mark.svg" alt="" />
            <div className="brand-text">
              <div className="brand-title">DialogueEval</div>
              <div className="brand-subtitle">指令遵循评测系统</div>
            </div>
          </div>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`nav-item ${page === item.key ? "active" : ""}`}
              onClick={() => {
                if (item.key === "reports") {
                  setReportRunId("");
                  setReportListResetToken((current) => current + 1);
                }
                setPage(item.key);
              }}
              title={item.label}
            >
              {item.icon}
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <a className="button sidebar-action" href={phoenixUrl} target="_blank" rel="noreferrer" title="Trace 调试">
            <Workflow size={16} />
            <span className="sidebar-action-label">Trace 调试</span>
          </a>
        </div>
      </aside>

      <main className="main">
        {notice ? <div className="message error">{notice}</div> : null}
        {loading ? (
          <div className="message">
            <Loader2 size={16} /> 正在加载数据...
          </div>
        ) : null}
        {page === "workbench" ? (
          <Workbench
            health={health}
            assets={assets}
            runs={runs}
            registryStatus={registryStatus}
            onOpenReport={(runId) => {
              setReportRunId(runId);
              setPage("reports");
            }}
          />
        ) : null}
        {page === "new" ? (
          <NewEvaluation
            onDone={refresh}
            taskInputState={taskInputState}
            setTaskInputState={setTaskInputState}
            evaluationProgress={evaluationProgress}
            setEvaluationProgress={setEvaluationProgress}
            evaluationRunning={evaluationRunning}
            onOpenReport={(runId) => {
              setReportRunId(runId);
              setPage("reports");
            }}
          />
        ) : null}
        {page === "reports" ? <Reports runs={runs} initialRunId={reportRunId} resetToken={reportListResetToken} onDeleted={refresh} /> : null}
        {page === "validity" ? <CaseValidityWorkbench runs={runs} /> : null}
        {page === "annotations" ? <AnnotationWorkbench runs={runs} /> : null}
        {page === "admin" ? (
          <SystemManagement
            assets={assets}
            runs={runs}
            registryStatus={registryStatus}
            health={health}
            onRefresh={refresh}
          />
        ) : null}
      </main>
    </div>
  );
}

function Workbench({
  health,
  assets,
  runs,
  registryStatus,
  onOpenReport
}: {
  health: JsonObject;
  assets: JsonObject[];
  runs: JsonObject[];
  registryStatus: JsonObject;
  onOpenReport: (runId: string) => void;
}) {
  const latestRun = runs[0] || {};
  const latestPassRate = passRate(latestRun);
  return (
    <>
      <div className="metric-grid">
        <Metric label="服务状态" value={health.status || "unknown"} />
        <Metric label="测试设计" value={assets.length} />
        <Metric label="运行记录" value={runs.length} />
        <Metric label="最近平均分" value={display(latestRun.average_score)} tone={scoreTone(latestRun.average_score)} />
        <Metric label="最近通过率" value={latestPassRate} />
        <Metric label="沉淀实验" value={registryStatus.experiments || 0} />
      </div>

      <div className="grid">
        <section className="panel new-evaluation-panel">
          <PanelHeader
            title="最近评测"
            icon={<History size={18} />}
          />
          {runs.length ? (
            <RunList runs={runs.slice(0, 8)} onOpen={onOpenReport} compact />
          ) : (
            <Empty text="还没有运行记录。可以从新建评测开始。" />
          )}
        </section>
      </div>
    </>
  );
}

function NewEvaluation({
  onDone,
  taskInputState,
  setTaskInputState,
  evaluationProgress,
  setEvaluationProgress,
  evaluationRunning,
  onOpenReport
}: {
  onDone: () => Promise<void>;
  taskInputState: TaskInputState;
  setTaskInputState: (state: TaskInputState) => void;
  evaluationProgress: JsonObject | null;
  setEvaluationProgress: (state: JsonObject | null) => void;
  evaluationRunning: boolean;
  onOpenReport: (runId: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [businessConfig, setBusinessConfig] = useState("");
  const [generationPolicy, setGenerationPolicy] = useState("configs/generation_policy.yaml");
  const [modelConfig, setModelConfig] = useState("configs/model_config.yaml");
  const [assetOutput, setAssetOutput] = useState("outputs/assets");
  const [runOutput, setRunOutput] = useState("outputs/runs");
  const [fakeLLM, setFakeLLM] = useState(false);
  const [skipEvaluation, setSkipEvaluation] = useState(false);
  const [publishCaseSeeds, setPublishCaseSeeds] = useState(true);
  const [publishGeneratedDialogues, setPublishGeneratedDialogues] = useState(true);
  const [limit, setLimit] = useState("0");
  const [conversationConcurrency, setConversationConcurrency] = useState("1");
  const [generatedAssets, setGeneratedAssets] = useState<JsonObject[]>([]);
  const [generatedRuns, setGeneratedRuns] = useState<JsonObject[]>([]);
  const [busy, setBusy] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState("");
  const uploadedFile = taskInputState.uploadedFile || null;
  const taskPreview = taskInputState.taskPreview || {};
  const taskItems = taskPreview.items || [];
  const taskEntries = taskItems.map((item: JsonObject, index: number) => ({ item, index, key: taskInstructionKey(item, index) }));
  const selectedTaskKeys = taskInputState.selectedTaskKeys || [];
  const taskConfigs = taskInputState.taskConfigs || {};
  const selectedTaskEntries = taskEntries.filter((entry: JsonObject) => selectedTaskKeys.includes(entry.key));
  const selectedTaskItems = selectedTaskEntries.map((entry: JsonObject) => entry.item);
  const selectedEvalStandardPaths = selectedTaskItems.map((item: JsonObject) => item.output_path).filter(Boolean);
  const selectedEvalStandardPayload = taskItems.length ? selectedEvalStandardPaths : null;
  const taskConfigPayload = selectedTaskEntries
    .map((entry: JsonObject) => taskRunConfigPayload(entry.item, entry.index, taskConfigs))
    .filter(Boolean);
  const selectedFileName = file?.name || taskInputState.fileName || "";
  const hasTaskInput = Boolean(file || uploadedFile);
  const taskSelectionError = taskItems.length > 0 && selectedTaskItems.length === 0 ? "请至少选择一条任务指令。" : "";
  const normalizedLimit = limit.trim();
  const caseLimitValid = normalizedLimit.length > 0 && Array.from(normalizedLimit).every((char) => char >= "0" && char <= "9");
  const caseLimitValue = caseLimitValid ? Number(normalizedLimit) : 0;
  const caseLimitError = caseLimitValid ? "" : "请输入非负整数，只能包含数字。";
  const normalizedConcurrency = conversationConcurrency.trim();
  const conversationConcurrencyValid = normalizedConcurrency.length > 0 && Array.from(normalizedConcurrency).every((char) => char >= "0" && char <= "9");
  const conversationConcurrencyValue = conversationConcurrencyValid ? Number(normalizedConcurrency) : 1;
  const conversationConcurrencyError = !conversationConcurrencyValid || conversationConcurrencyValue < 1 || conversationConcurrencyValue > 10
    ? "请输入 1-10 之间的并发数。"
    : "";
  const taskConfigError = selectedTaskEntries
    .map((entry: JsonObject) => taskConfigValidationError(taskConfigs[entry.key]))
    .find(Boolean) || "";
  const completedEvaluationResult = evaluationProgress?.status === "completed" ? (evaluationProgress.result || {}) : {};
  const visibleGeneratedAssets = generatedAssets.length ? generatedAssets : (completedEvaluationResult.assets || []);
  const visibleGeneratedRuns = generatedRuns.length ? generatedRuns : (completedEvaluationResult.runs || []);
  const evaluationCompleted = evaluationProgress?.status === "completed";

  function updateSelectedTaskKeys(nextKeys: string[]) {
    setTaskInputState({
      ...taskInputState,
      selectedTaskKeys: nextKeys
    });
  }

  function updateTaskConfig(taskKey: string, patch: TaskConfigState) {
    setTaskInputState({
      ...taskInputState,
      taskConfigs: {
        ...(taskInputState.taskConfigs || {}),
        [taskKey]: {
          ...(taskInputState.taskConfigs || {})[taskKey],
          ...patch
        }
      }
    });
  }

  async function ensureUploadedFile() {
    if (uploadedFile) return uploadedFile;
    if (!file) throw new Error("请先上传 Markdown、CSV 或 Excel 任务文件。");
    const uploaded = await uploadFile(file);
    setTaskInputState({
      ...taskInputState,
      fileName: file.name,
      uploadedFile: uploaded
    });
    return uploaded;
  }

  async function handleTaskFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (evaluationRunning) {
      setMessage("评测运行中，完成后再更换任务文件。");
      event.target.value = "";
      return;
    }
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setTaskInputState({});
    setGeneratedAssets([]);
    setGeneratedRuns([]);
    setEvaluationProgress(null);
    if (!selected) return;

    setAnalyzing(true);
    setMessage("");
    try {
      const uploaded = await uploadFile(selected);
      if (isTabularFile(selected.name)) {
        const result = await apiJson("/eval-standards/extract", {
          method: "POST",
          headers: jsonHeaders(),
          body: JSON.stringify({
            excel_path: uploaded.path,
            output_dir: "outputs/extracted_eval_standards",
            excel_column: 2,
            excel_start_row: 2
          })
        });
        const items = result.items || [];
        setTaskInputState({
          fileName: selected.name,
          uploadedFile: uploaded,
          taskPreview: {
            count: result.count || 0,
            items,
            source_type: selected.name.toLowerCase().endsWith(".csv") ? "CSV" : "Excel"
          },
          selectedTaskKeys: items.map((item: JsonObject, index: number) => taskInstructionKey(item, index))
        });
      } else {
        const text = await selected.text();
        const item = {
          title: selected.name,
          task_summary: summarizeTaskInstruction(text, selected.name),
          content: text,
          preview: compactPreview(text),
          output_path: uploaded.path
        };
        setTaskInputState({
          fileName: selected.name,
          uploadedFile: uploaded,
          taskPreview: {
            count: text.trim() ? 1 : 0,
            items: [item],
            source_type: "Markdown"
          },
          selectedTaskKeys: [taskInstructionKey(item, 0)]
        });
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAnalyzing(false);
    }
  }

  async function startEvaluation() {
    if (evaluationRunning) {
      setMessage("当前已有评测在运行，请等待完成。");
      return;
    }
    if (!hasTaskInput) {
      setMessage("请先上传 Markdown、CSV 或 Excel 任务文件。");
      return;
    }
    if (caseLimitError || conversationConcurrencyError || taskConfigError) {
      setMessage(caseLimitError || conversationConcurrencyError || taskConfigError);
      return;
    }
    if (taskSelectionError) {
      setMessage(taskSelectionError);
      return;
    }
    setBusy("evaluation");
    setMessage("");
    setEvaluationProgress(null);
    try {
      const uploaded = await ensureUploadedFile();
      const job = await apiJson("/evaluations/jobs", {
        method: "POST",
        body: JSON.stringify({
          eval_standard_file_path: uploaded.path,
          business_config_path: businessConfig || null,
          generation_policy_path: generationPolicy,
          model_config_path: modelConfig,
          asset_output_root: assetOutput,
          run_output_root: runOutput,
          selected_eval_standard_paths: selectedEvalStandardPayload,
          task_configs: taskConfigPayload,
          target_case_count: caseLimitValue > 0 ? caseLimitValue : null,
          limit: caseLimitValue > 0 ? caseLimitValue : null,
          conversation_concurrency: conversationConcurrencyValue,
          skip_evaluation: skipEvaluation,
          publish_case_seed_dataset: publishCaseSeeds,
          publish_generated_dialogue_dataset: publishGeneratedDialogues,
          fake_llm: fakeLLM
        }),
        headers: jsonHeaders()
      });
      setEvaluationProgress(job);
      setMessage("评测已开始，页面会持续更新执行进度。");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function generateAssetsOnly() {
    if (evaluationRunning) {
      setMessage("评测运行中，完成后再生成中间资产。");
      return;
    }
    if (!hasTaskInput) {
      setMessage("请先上传 Markdown、CSV 或 Excel 任务文件。");
      return;
    }
    if (taskSelectionError) {
      setMessage(taskSelectionError);
      return;
    }
    setBusy("asset");
    setMessage("");
    setEvaluationProgress(null);
    try {
      const uploaded = await ensureUploadedFile();
      const result = await apiJson("/assets/generate", {
        method: "POST",
        body: JSON.stringify({
          eval_standard_file_path: uploaded.path,
          business_config_path: businessConfig || null,
          generation_policy_path: generationPolicy,
          model_config_path: modelConfig,
          output_root: assetOutput,
          selected_eval_standard_paths: selectedEvalStandardPayload,
          task_configs: taskConfigPayload,
          target_case_count: caseLimitValue > 0 ? caseLimitValue : null,
          publish_case_seed_dataset: publishCaseSeeds,
          fake_llm: fakeLLM
        }),
        headers: jsonHeaders()
      });
      setGeneratedAssets(result.assets || []);
      setMessage(`已生成 ${result.count || 0} 个中间资产，可用于覆盖设计审计。`);
      await onDone();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function cancelEvaluation() {
    const jobId = evaluationProgress?.job_id;
    if (!jobId) return;
    setBusy("cancel");
    setMessage("");
    try {
      const job = await apiJson(`/evaluations/jobs/${jobId}/cancel`, {
        method: "POST"
      });
      setEvaluationProgress(job);
      setMessage("已提交取消请求，后台会在当前模型调用结束后停止。");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  function resetForNextEvaluation() {
    setFile(null);
    setTaskInputState({});
    setGeneratedAssets([]);
    setGeneratedRuns([]);
    setEvaluationProgress(null);
    setMessage("");
  }

  return (
    <>
      <div className="steps">
        <Step index={1} title="任务输入" note={selectedFileName || "Markdown / CSV / Excel"} active={!hasTaskInput} complete={hasTaskInput} />
        <Step
          index={2}
          title="测试设计"
          note={visibleGeneratedAssets.length ? `${visibleGeneratedAssets.length} 个中间资产` : "覆盖矩阵与 case card"}
          active={hasTaskInput && !visibleGeneratedAssets.length}
          complete={!!visibleGeneratedAssets.length}
        />
        <Step
          index={3}
          title="对话与报告"
          note={visibleGeneratedRuns.length ? `${visibleGeneratedRuns.length} 个报告` : "客服-用户对话"}
          active={!!visibleGeneratedAssets.length && !visibleGeneratedRuns.length}
          complete={!!visibleGeneratedRuns.length}
        />
      </div>

      {message ? <div className="message">{message}</div> : null}
      {evaluationProgress ? (
        <EvaluationProgress
          job={evaluationProgress}
          onOpenReport={onOpenReport}
          onStartOver={resetForNextEvaluation}
          onCancel={cancelEvaluation}
          cancelBusy={busy === "cancel"}
        />
      ) : null}

      <div className="new-evaluation-form">
        <section className="panel">
          <PanelHeader title="任务输入" icon={<UploadCloud size={18} />} />
          <label className={`file-drop ${evaluationRunning ? "disabled" : ""}`}>
            <UploadCloud size={28} />
            <strong>{selectedFileName || "选择任务文件"}</strong>
            <span className="panel-caption">支持 .md, .csv, .xlsx</span>
            <input
              hidden
              type="file"
              accept=".md,.markdown,.csv,.xlsx,.xlsm,.xltx,.xltm"
              onChange={handleTaskFileChange}
              disabled={evaluationRunning}
            />
          </label>
          <TaskInstructionPreview
            preview={taskPreview}
            analyzing={analyzing}
            selectedKeys={selectedTaskKeys}
            onSelectionChange={updateSelectedTaskKeys}
          />
          {taskSelectionError ? <div className="field-error task-selection-error">{taskSelectionError}</div> : null}

          <div className="actions" style={{ marginTop: 16 }}>
            <button
              className="button primary button-large"
              onClick={startEvaluation}
              disabled={busy === "evaluation" || evaluationRunning || analyzing || !hasTaskInput || Boolean(caseLimitError || conversationConcurrencyError || taskConfigError || taskSelectionError)}
            >
              {busy === "evaluation" || evaluationRunning ? <Loader2 size={16} /> : <PlayCircle size={16} />}
              {evaluationRunning ? "评测运行中" : evaluationCompleted ? "再次运行" : "开始完整评测"}
            </button>
            <button className="button" onClick={generateAssetsOnly} disabled={busy === "asset" || evaluationRunning || analyzing || !hasTaskInput || Boolean(taskConfigError || taskSelectionError)}>
              {busy === "asset" ? <Loader2 size={16} /> : <Boxes size={16} />}
              仅生成中间资产
            </button>
          </div>
        </section>

        <section className="panel">
          <PanelHeader title="运行配置" icon={<Settings size={18} />} />
          <div className="form-grid single">
            <Field label="case 数量">
              <input
                className={`input ${caseLimitError ? "invalid" : ""}`}
                inputMode="numeric"
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
                placeholder="0"
              />
              {caseLimitError ? <small className="field-error">{caseLimitError}</small> : <small>输入 100 会生成并运行 100 个 case；0 表示按生成策略默认值。</small>}
            </Field>
            <Field label="对话并发数">
              <input
                className={`input ${conversationConcurrencyError ? "invalid" : ""}`}
                inputMode="numeric"
                value={conversationConcurrency}
                onChange={(event) => setConversationConcurrency(event.target.value)}
                placeholder="1"
              />
              {conversationConcurrencyError ? <small className="field-error">{conversationConcurrencyError}</small> : <small>建议 1-5；设为 5 会同时生成 5 条对话，过高可能触发模型限流。</small>}
            </Field>
          </div>
          <div className="config-toggles">
            <label className="chip">
              <input type="checkbox" checked={skipEvaluation} onChange={(event) => setSkipEvaluation(event.target.checked)} />
              只跑对话，不生成评分
            </label>
            <label className="chip">
              <input type="checkbox" checked={fakeLLM} onChange={(event) => setFakeLLM(event.target.checked)} />
              使用 fake LLM
            </label>
          </div>
          <div className="dataset-options">
            <div className="task-config-head">
              <strong>Phoenix Dataset</strong>
              <span>输入集用于复现实验，对话归档用于标注和 judge 校准</span>
            </div>
            <label className="dataset-option">
              <input type="checkbox" checked={publishCaseSeeds} onChange={(event) => setPublishCaseSeeds(event.target.checked)} />
              <span>
                <strong>发布 case seed 输入集</strong>
                <small>只保存 case card、用户画像、覆盖目标和资产版本，不保存客服输出。</small>
              </span>
            </label>
            <label className="dataset-option">
              <input type="checkbox" checked={publishGeneratedDialogues} onChange={(event) => setPublishGeneratedDialogues(event.target.checked)} />
              <span>
                <strong>归档生成对话</strong>
                <small>评测完成后把完整对话和评分结果另存为 Phoenix Dataset 版本。</small>
              </span>
            </label>
          </div>
          <TaskRunConfigList
            items={taskItems}
            selectedKeys={selectedTaskKeys}
            configs={taskConfigs}
            defaultAssetOutput={assetOutput}
            defaultRunOutput={runOutput}
            defaultLimit={limit}
            onChange={updateTaskConfig}
          />
          {taskConfigError ? <div className="field-error task-selection-error">{taskConfigError}</div> : null}
          <details className="advanced-config">
            <summary>开发者配置</summary>
            <div className="form-grid">
              <Field label="业务配置路径">
                <input className="input" value={businessConfig} onChange={(event) => setBusinessConfig(event.target.value)} placeholder="可选" />
              </Field>
              <Field label="生成策略路径">
                <input className="input" value={generationPolicy} onChange={(event) => setGenerationPolicy(event.target.value)} />
              </Field>
              <Field label="模型配置路径">
                <input className="input" value={modelConfig} onChange={(event) => setModelConfig(event.target.value)} />
              </Field>
              <Field label="资产输出目录">
                <input className="input" value={assetOutput} onChange={(event) => setAssetOutput(event.target.value)} />
              </Field>
              <Field label="运行输出目录">
                <input className="input" value={runOutput} onChange={(event) => setRunOutput(event.target.value)} />
              </Field>
            </div>
          </details>
        </section>
      </div>
    </>
  );
}

function TaskRunConfigList({
  items,
  selectedKeys,
  configs,
  defaultAssetOutput,
  defaultRunOutput,
  defaultLimit,
  onChange
}: {
  items: JsonObject[];
  selectedKeys: string[];
  configs: Record<string, TaskConfigState>;
  defaultAssetOutput: string;
  defaultRunOutput: string;
  defaultLimit: string;
  onChange: (taskKey: string, patch: TaskConfigState) => void;
}) {
  const selectedItems = items
    .map((item, index) => ({ item, index, key: taskInstructionKey(item, index) }))
    .filter((entry) => selectedKeys.includes(entry.key));
  if (!selectedItems.length) return null;
  return (
    <div className="task-config-list">
      <div className="task-config-head">
        <strong>按任务配置</strong>
        <span>留空则继承上方默认值</span>
      </div>
      {selectedItems.map(({ item, index, key }) => {
        const config = configs[key] || {};
        const error = taskConfigValidationError(config);
        return (
          <div className="task-config-card" key={key}>
            <div className="task-config-title">
              <span>第{index + 1}条</span>
              <strong>{oneLineTaskSummary(item, index)}</strong>
            </div>
            <div className="form-grid single">
              <Field label="case 数量">
                <input
                  className={`input ${error ? "invalid" : ""}`}
                  inputMode="numeric"
                  value={config.limit || ""}
                  onChange={(event) => onChange(key, { limit: event.target.value })}
                  placeholder={defaultLimit || "0"}
                />
                {error ? <small className="field-error">{error}</small> : <small>输入后会同时控制该任务的生成 case 数和运行 case 数；留空继承默认值。</small>}
              </Field>
              <Field label="资产输出目录">
                <input
                  className="input"
                  value={config.assetOutput || ""}
                  onChange={(event) => onChange(key, { assetOutput: event.target.value })}
                  placeholder={defaultAssetOutput}
                />
              </Field>
              <Field label="报告输出目录">
                <input
                  className="input"
                  value={config.runOutput || ""}
                  onChange={(event) => onChange(key, { runOutput: event.target.value })}
                  placeholder={defaultRunOutput}
                />
              </Field>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Reports({
  runs,
  initialRunId = "",
  resetToken = 0,
  onDeleted
}: {
  runs: JsonObject[];
  initialRunId?: string;
  resetToken?: number;
  onDeleted: () => Promise<void>;
}) {
  const [selectedRun, setSelectedRun] = useState("");
  const [evaluations, setEvaluations] = useState<JsonObject[]>([]);
  const [conversations, setConversations] = useState<JsonObject[]>([]);
  const [selectedCase, setSelectedCase] = useState("");
  const [reportTab, setReportTab] = useState("overview");
  const [rawFile, setRawFile] = useState("conversation_log.jsonl");
  const [rawText, setRawText] = useState("");
  const [summaryText, setSummaryText] = useState("");
  const [scoreText, setScoreText] = useState("");
  const [markdownView, setMarkdownView] = useState("score");
  const [message, setMessage] = useState("");
  const [deleteConfirmRunId, setDeleteConfirmRunId] = useState("");
  const [deletingRunId, setDeletingRunId] = useState("");
  const appliedInitialRunId = useRef("");
  const appliedResetToken = useRef(resetToken);

  useEffect(() => {
    if (
      initialRunId &&
      appliedInitialRunId.current !== initialRunId &&
      runs.some((item) => item.run_id === initialRunId)
    ) {
      appliedInitialRunId.current = initialRunId;
      setSelectedRun(initialRunId);
    }
  }, [initialRunId, runs]);

  useEffect(() => {
    if (resetToken === appliedResetToken.current) return;
    appliedResetToken.current = resetToken;
    backToRuns();
  }, [resetToken]);

  useEffect(() => {
    if (!selectedRun) return;
    async function loadRun() {
      try {
        const [evalText, convText, summary, scoreReport] = await Promise.all([
          apiText(`/runs/${selectedRun}/reports/case_evaluation.jsonl`),
          apiText(`/runs/${selectedRun}/reports/conversation_log.jsonl`),
          apiText(`/runs/${selectedRun}/reports/summary_report.md`),
          apiText(`/runs/${selectedRun}/reports/evaluation_report.md`)
        ]);
        const nextEvaluations = parseJsonl(evalText);
        const nextConversations = parseJsonl(convText);
        setEvaluations(nextEvaluations);
        setConversations(nextConversations);
        setSummaryText(summary);
        setScoreText(scoreReport);
        const firstCase = nextEvaluations[0]?.case_id || nextConversations[0]?.case_id || "";
        setSelectedCase(firstCase);
        setMessage("");
      } catch (error) {
        setEvaluations([]);
        setConversations([]);
        setSummaryText("");
        setScoreText("");
        setMessage(errorMessage(error));
      }
    }
    loadRun();
  }, [selectedRun]);

  useEffect(() => {
    if (!selectedRun) return;
    apiText(`/runs/${selectedRun}/reports/${rawFile}`).then(setRawText).catch(() => setRawText(""));
  }, [selectedRun, rawFile]);

  const run = runs.find((item) => item.run_id === selectedRun) || {};
  const caseIds = (evaluations.length ? evaluations : conversations).map((item) => item.case_id).filter(Boolean);
  const evaluation = evaluations.find((item) => item.case_id === selectedCase) || {};
  const conversation = conversations.find((item) => item.case_id === selectedCase) || {};

  function openRun(runId: string) {
    setSelectedRun(runId);
    setReportTab("overview");
    setMessage("");
    setDeleteConfirmRunId("");
  }

  function backToRuns() {
    setSelectedRun("");
    setEvaluations([]);
    setConversations([]);
    setSelectedCase("");
    setSummaryText("");
    setScoreText("");
    setRawText("");
    setMessage("");
    setDeleteConfirmRunId("");
  }

  async function deleteRun(runId: string) {
    if (!runId) return;
    if (deleteConfirmRunId !== runId) {
      setDeleteConfirmRunId(runId);
      setMessage("请再次点击确认删除。删除后会移除报告文件、人工标注和本地 registry 记录。");
      return;
    }
    setDeletingRunId(runId);
    setMessage("");
    try {
      await apiJson(`/runs/${runId}`, { method: "DELETE" });
      if (selectedRun === runId) {
        backToRuns();
      }
      await onDeleted();
      setDeleteConfirmRunId("");
      setMessage("评测记录已删除。Phoenix Trace 不会在此操作中删除。");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setDeletingRunId("");
    }
  }

  return (
    <>
      <PageHeader
        actions={
          selectedRun ? (
            <button className="button" onClick={backToRuns}>
              返回运行列表
            </button>
          ) : null
        }
      />
      {message ? <div className="message">{message}</div> : null}

      {!runs.length ? (
        <Empty text="还没有运行记录。" />
      ) : !selectedRun ? (
        <section className="panel">
          <PanelHeader title="评测运行列表" icon={<BarChart3 size={18} />} />
          <RunList
            runs={runs}
            onOpen={openRun}
            onDelete={deleteRun}
            deleteConfirmRunId={deleteConfirmRunId}
            deletingRunId={deletingRunId}
          />
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="run-detail-head">
              <div>
                <div className="eyebrow">评测记录</div>
                <h2>{runLabel(run) || selectedRun}</h2>
                <p className="panel-caption">{run.run_display_time || "-"}</p>
              </div>
              <div className="toolbar">
                <a className="button" href={process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006"} target="_blank" rel="noreferrer">
                  <Workflow size={16} />
                  打开 Phoenix
                </a>
                <button
                  className={`button danger ${deleteConfirmRunId === selectedRun ? "confirm" : ""}`}
                  onClick={() => deleteRun(selectedRun)}
                  disabled={deletingRunId === selectedRun}
                >
                  {deletingRunId === selectedRun ? <Loader2 size={16} /> : <Trash2 size={16} />}
                  {deleteConfirmRunId === selectedRun ? "确认删除" : "删除记录"}
                </button>
              </div>
            </div>
          </section>

          <RunMetrics run={run} />

          <div className="tabs">
            {[
              ["overview", "结果总览"],
              ["cases", "Case 明细"],
              ["markdown", "Markdown 报告"],
              ["raw", "原始文件"]
            ].map(([key, label]) => (
              <button key={key} className={`tab ${reportTab === key ? "active" : ""}`} onClick={() => setReportTab(key)}>
                {label}
              </button>
            ))}
          </div>

          {reportTab === "overview" ? (
            <>
              <RunConclusion run={run} evaluations={evaluations} />
              <div className="grid two">
                <section className="panel">
                  <PanelHeader title="Case 评分" icon={<ClipboardList size={18} />} />
                  {evaluations.length ? <CaseScoreTable evaluations={evaluations} onSelect={setSelectedCase} /> : <Empty text="没有评分结果。" />}
                </section>
                <section className="panel">
                  <PanelHeader title="高频未覆盖检查点" icon={<AlertTriangle size={18} />} />
                  <MissingTargets evaluations={evaluations} />
                </section>
              </div>
            </>
          ) : null}

          {reportTab === "cases" ? (
            <div className="report-cases-layout">
              <section className="panel case-rail-panel">
                <PanelHeader title="Case 列表" icon={<MessageSquareText size={18} />} />
                <div className="case-list">
                  {caseIds.map((caseId) => {
                    const item = evaluations.find((row) => row.case_id === caseId) || {};
                    return (
                      <button
                        key={caseId}
                        className={`case-row ${selectedCase === caseId ? "active" : ""}`}
                        onClick={() => setSelectedCase(caseId)}
                      >
                        <div className="case-row-top">
                          <strong>{caseId}</strong>
                          <ScoreChip score={item.total_score} passed={item.passed} />
                        </div>
                        <div className="actions">
                          <Chip tone={(item.missing_targets || []).length ? "amber" : "green"}>
                            缺失 {(item.missing_targets || []).length}
                          </Chip>
                          <Chip tone={(item.risk_deductions || []).length ? "red" : "green"}>
                            风险 {(item.risk_deductions || []).length}
                          </Chip>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>
              <CaseDetail evaluation={evaluation} conversation={conversation} />
            </div>
          ) : null}

          {reportTab === "markdown" ? (
            <MarkdownReportViewer
              selectedRun={selectedRun}
              view={markdownView}
              onViewChange={setMarkdownView}
              scoreText={scoreText}
              summaryText={summaryText}
            />
          ) : null}

          {reportTab === "raw" ? (
            <RawFileViewer rawFile={rawFile} rawText={rawText} onRawFileChange={setRawFile} />
          ) : null}
        </>
      )}
    </>
  );
}

function RunConclusion({ run, evaluations }: { run: JsonObject; evaluations: JsonObject[] }) {
  const totalCases = Number(run.case_count || 0);
  const coverageSuccess = Number(run.coverage_success_count || 0);
  const evaluatedCases = Number(run.evaluation_count || evaluations.length || 0);
  const passedCases = Number(run.passed_count || 0);
  const passThreshold = firstNumeric(evaluations.map((item) => item.pass_threshold)) ?? 80;
  const scoringComplete = evaluatedCases > 0 && passedCases === evaluatedCases;
  const coverageComplete = totalCases > 0 && coverageSuccess === totalCases;
  const needsReview = !coverageComplete || Number(run.veto_count || 0) > 0 || Number(run.risk_count || 0) > 0;
  const conclusion = scoringComplete && coverageComplete && !needsReview
    ? { label: "评测通过", tone: "green", note: "评分和覆盖均达到当前规则要求。" }
    : scoringComplete && !coverageComplete
      ? { label: "评分通过 覆盖不足", tone: "amber", note: "模型得分达标，但仍有检查点未被对话覆盖，建议补测或人工复核。" }
      : { label: "建议复核", tone: "red", note: "存在未通过 case、覆盖缺口、风险项或一票否决，需要查看证据后处理。" };
  return (
    <section className="panel conclusion-panel">
      <PanelHeader title="综合结论" icon={<ClipboardCheck size={18} />} />
      <div className="conclusion-layout">
        <div className={`conclusion-badge ${conclusion.tone}`}>
          {conclusion.label}
        </div>
        <div className="conclusion-copy">
          <p>{conclusion.note}</p>
          <div className="actions">
            <Chip tone={scoringComplete ? "green" : "red"}>
              评分 {passedCases}/{evaluatedCases || 0} 通过，合格线 {display(passThreshold)}
            </Chip>
            <Chip tone={coverageComplete ? "green" : "amber"}>
              覆盖 {coverageSuccess}/{totalCases || 0} 完成
            </Chip>
            <Chip tone={Number(run.risk_count || 0) ? "red" : "green"}>
              风险 {run.risk_count || 0}
            </Chip>
            <Chip tone={Number(run.veto_count || 0) ? "red" : "green"}>
              一票否决 {run.veto_count || 0}
            </Chip>
          </div>
        </div>
      </div>
    </section>
  );
}

function ReportMarkdownPanel({
  title,
  icon,
  content,
  downloadPath
}: {
  title: string;
  icon: ReactNode;
  content: string;
  downloadPath: string;
}) {
  return (
    <section className="panel">
      <PanelHeader
        title={title}
        icon={icon}
        actions={
          <div className="toolbar">
            <button className="button ghost" onClick={() => copyText(content)} disabled={!content}>
              <Copy size={15} />
              复制
            </button>
            <a className="button ghost" href={downloadPath} download>
              <Download size={15} />
              下载
            </a>
          </div>
        }
      />
      <div className="report-markdown">
        {content ? <MarkdownContent content={content} /> : <Empty text="暂无报告。" />}
      </div>
    </section>
  );
}

function MarkdownReportViewer({
  selectedRun,
  view,
  onViewChange,
  scoreText,
  summaryText
}: {
  selectedRun: string;
  view: string;
  onViewChange: (value: string) => void;
  scoreText: string;
  summaryText: string;
}) {
  const options = [
    {
      key: "score",
      label: "总评分报告",
      icon: <FileText size={18} />,
      content: scoreText,
      downloadPath: `/api/backend/runs/${selectedRun}/reports/evaluation_report.md`
    },
    {
      key: "summary",
      label: "覆盖报告",
      icon: <Activity size={18} />,
      content: summaryText,
      downloadPath: `/api/backend/runs/${selectedRun}/reports/summary_report.md`
    }
  ];
  const current = options.find((item) => item.key === view) || options[0];
  return (
    <div className="report-reader">
      <div className="report-switcher" role="tablist" aria-label="报告类型">
        {options.map((item) => (
          <button
            key={item.key}
            className={`report-switcher-button ${current.key === item.key ? "active" : ""}`}
            onClick={() => onViewChange(item.key)}
            type="button"
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </div>
      <ReportMarkdownPanel
        title={current.label}
        icon={current.icon}
        content={current.content}
        downloadPath={current.downloadPath}
      />
    </div>
  );
}

function RawFileViewer({
  rawFile,
  rawText,
  onRawFileChange
}: {
  rawFile: string;
  rawText: string;
  onRawFileChange: (value: string) => void;
}) {
  const rows = useMemo(() => parseJsonl(rawText), [rawText]);
  const lineCount = splitLines(rawText).filter((line) => line.trim()).length;
  return (
    <section className="panel">
      <PanelHeader
        title="原始文件"
        icon={<FileText size={18} />}
        actions={
          <button className="button ghost" onClick={() => copyText(rawText)} disabled={!rawText}>
            <Copy size={15} />
            复制原文
          </button>
        }
      />
      <div className="raw-toolbar">
        <select className="select" value={rawFile} onChange={(event) => onRawFileChange(event.target.value)}>
          {rawRunFiles.map(([file, label]) => (
            <option key={file} value={file}>
              {label}
            </option>
          ))}
        </select>
        <Chip>{lineCount} 行</Chip>
        {rows.length ? <Chip tone="green">已识别 {rows.length} 条 JSONL</Chip> : <Chip tone="amber">文本文件</Chip>}
      </div>
      {rows.length ? (
        <div className="raw-summary-list">
          {rows.slice(0, 8).map((row, index) => (
            <details key={row.case_id || row.call_id || index} className="raw-summary-item">
              <summary>
                <span>{rawRecordTitle(row, index)}</span>
                {row.success === false ? <Chip tone="red">失败</Chip> : row.success === true ? <Chip tone="green">成功</Chip> : null}
              </summary>
              <pre className="code compact">{JSON.stringify(row, null, 2)}</pre>
            </details>
          ))}
          {rows.length > 8 ? <div className="panel-caption">仅预览前 8 条，完整内容可复制原文查看。</div> : null}
        </div>
      ) : (
        <pre className="code">{rawText || "暂无原始文件内容。"}</pre>
      )}
    </section>
  );
}

function RunList({
  runs,
  onOpen,
  onDelete,
  deleteConfirmRunId = "",
  deletingRunId = "",
  compact = false
}: {
  runs: JsonObject[];
  onOpen: (runId: string) => void;
  onDelete?: (runId: string) => void;
  deleteConfirmRunId?: string;
  deletingRunId?: string;
  compact?: boolean;
}) {
  return (
    <div className="run-list-table">
      <table>
        <thead>
          <tr>
            <th>评测名称</th>
            <th>发起时间</th>
            <th>Case</th>
            <th>已评分</th>
            <th>通过</th>
            <th>平均分</th>
            {!compact ? <th>风险</th> : null}
            {!compact ? <th>一票否决</th> : null}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id} className="clickable-row" onClick={() => onOpen(run.run_id)}>
              <td>
                <strong title={String(run.run_id || "")}>{runLabel(run)}</strong>
              </td>
              <td>{run.run_display_time || "-"}</td>
              <td>{run.case_count || 0}</td>
              <td>{run.evaluation_count || 0}</td>
              <td>{run.passed_count || 0}</td>
              <td>
                <span className={scoreTone(run.average_score) ? `text-${scoreTone(run.average_score)}` : ""}>
                  {display(run.average_score)}
                </span>
              </td>
              {!compact ? <td>{run.risk_count || 0}</td> : null}
              {!compact ? <td>{run.veto_count || 0}</td> : null}
              <td>
                <div className="row-actions">
                  <button className="button ghost" onClick={(event) => {
                    event.stopPropagation();
                    onOpen(run.run_id);
                  }}>
                    查看详情
                  </button>
                  {onDelete ? (
                    <button
                      className={`button ghost danger ${deleteConfirmRunId === run.run_id ? "confirm" : ""}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(run.run_id);
                      }}
                      disabled={deletingRunId === run.run_id}
                    >
                      {deletingRunId === run.run_id ? <Loader2 size={14} /> : <Trash2 size={14} />}
                      {deleteConfirmRunId === run.run_id ? "确认删除" : "删除"}
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssetsCenter({ assets, embedded = false }: { assets: JsonObject[]; embedded?: boolean }) {
  const validAssets = assets.filter((item) => item.valid);
  const [sceneId, setSceneId] = useState(validAssets[0]?.scene_id || "");
  const [fileName, setFileName] = useState("scene_asset.yaml");
  const [content, setContent] = useState("");

  useEffect(() => {
    if (!sceneId && validAssets[0]?.scene_id) setSceneId(validAssets[0].scene_id);
  }, [validAssets, sceneId]);

  useEffect(() => {
    if (!sceneId) return;
    apiText(`/assets/${sceneId}/files/${fileName}`).then(setContent).catch(() => setContent(""));
  }, [sceneId, fileName]);

  return (
    <>
      <section className="panel">
        <PanelHeader title="测试设计资产" icon={<Layers3 size={18} />} />
        {validAssets.length ? <AssetsTable assets={validAssets} /> : <Empty text="还没有可用资产。" />}
      </section>

      {validAssets.length ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <PanelHeader title="设计文件" icon={<FileText size={18} />} />
          <div className="form-grid" style={{ marginBottom: 14 }}>
            <Field label="场景">
              <select className="select" value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
                {validAssets.map((asset) => (
                  <option key={asset.scene_id} value={asset.scene_id}>
                    {asset.scene_name || asset.scene_id}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="文件">
              <select className="select" value={fileName} onChange={(event) => setFileName(event.target.value)}>
                {assetFiles.map(([file, label]) => (
                  <option key={file} value={file}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <pre className={fileName.endsWith(".md") ? "markdown" : "code"}>{content}</pre>
        </section>
      ) : null}
    </>
  );
}

function CaseValidityWorkbench({ runs }: { runs: JsonObject[] }) {
  const [selectedRun, setSelectedRun] = useState(runs[0]?.run_id || "");
  const [data, setData] = useState<JsonObject>({});
  const [caseIndex, setCaseIndex] = useState(0);
  const [form, setForm] = useState<JsonObject>({});
  const [formDirty, setFormDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!selectedRun && runs[0]?.run_id) setSelectedRun(runs[0].run_id);
  }, [runs, selectedRun]);

  useEffect(() => {
    if (!selectedRun) return;
    loadValidityRun(selectedRun);
  }, [selectedRun]);

  useEffect(() => {
    resetValidityForm();
  }, [data.run_id, caseIndex]);

  async function loadValidityRun(runId: string) {
    try {
      const next = await apiJson(`/case-validity/runs/${runId}`);
      setData(next);
      setCaseIndex(0);
      setMessage("");
    } catch (error) {
      setData({});
      setMessage(errorMessage(error));
    }
  }

  function cases() {
    return data.cases || [];
  }

  function currentCase() {
    return cases()[caseIndex] || {};
  }

  function resetValidityForm() {
    const current = currentCase();
    const review = current.validity_review || {};
    setForm({
      annotator_id: review.annotator_id || "human_01",
      case_validity: review.case_validity || "unreviewed",
      validity_checks: review.validity_checks || defaultValidityChecks(current),
      validity_notes: review.validity_notes || ""
    });
    setFormDirty(false);
  }

  const current = currentCase();
  const totalCases = cases().length;
  const reviewedCount = Number(data.reviewed_count || 0);
  const validityHints = current.validity_hints || {};

  useEffect(() => {
    if (!formDirty || !selectedRun || !current.case_id || !form.annotator_id) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      saveValidityReview({ silent: true }).catch(() => undefined);
    }, 700);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, [form, formDirty, selectedRun, current.case_id]);

  function updateForm(patch: JsonObject) {
    setForm((currentForm) => ({ ...currentForm, ...patch }));
    setFormDirty(true);
  }

  function updateValidityCheck(checkId: string, patch: JsonObject) {
    setFormDirty(true);
    setForm((currentForm) => {
      const next = (currentForm.validity_checks || []).map((item: JsonObject) => item.check_id === checkId ? { ...item, ...patch } : item);
      return { ...currentForm, validity_checks: next };
    });
  }

  function applyValiditySuggestions() {
    const suggested = suggestedValidityReview(current);
    setFormDirty(true);
    setForm((currentForm) => ({
      ...currentForm,
      case_validity: suggested.case_validity,
      validity_checks: (currentForm.validity_checks || defaultValidityChecks(current)).map((item: JsonObject) => ({
        ...item,
        status: suggested.checks[item.check_id] || item.status,
        evidence: item.evidence || validityHintText(item.check_id, current)
      }))
    }));
  }

  async function saveValidityReview(options: { goNext?: boolean; silent?: boolean } = {}) {
    const { goNext = false, silent = false } = options;
    if (!selectedRun || !current.case_id) return;
    if (!silent) setSaving(true);
    if (!silent) setMessage("");
    try {
      const saved = await apiJson(`/case-validity/runs/${selectedRun}/cases/${current.case_id}`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(form)
      });
      setData((currentData) => {
        const nextCases = (currentData.cases || []).map((item: JsonObject) => item.case_id === current.case_id ? { ...item, validity_review: saved } : item);
        const reviewed = nextCases.filter((item: JsonObject) => item.validity_review?.review_complete).length;
        return { ...currentData, cases: nextCases, reviewed_count: reviewed };
      });
      setFormDirty(false);
      if (!silent) setMessage(saved.review_complete ? `已保存 ${current.case_id} 的 Case 质检。` : `已保存 ${current.case_id} 草稿。`);
      if (goNext && caseIndex < totalCases - 1) setCaseIndex(caseIndex + 1);
    } catch (error) {
      if (!silent) setMessage(errorMessage(error));
    } finally {
      if (!silent) setSaving(false);
    }
  }

  function firstIncompleteValidityItem() {
    if (!form.case_validity || form.case_validity === "unreviewed") {
      return { id: "validity-overall", label: "Case 有效性总判定" };
    }
    const validity = (form.validity_checks || []).find((item: JsonObject) => !item.status || item.status === "unreviewed");
    if (validity) return { id: `validity-${validity.check_id}`, label: validity.label || "Case 有效性检查" };
    return null;
  }

  function focusValidityItem(itemId: string) {
    const element = itemRefs.current[itemId];
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function goToPreviousCase() {
    if (formDirty) await saveValidityReview({ silent: true });
    if (caseIndex > 0) setCaseIndex(caseIndex - 1);
  }

  async function selectCase(nextIndex: number) {
    if (nextIndex === caseIndex) return;
    if (formDirty) await saveValidityReview({ silent: true });
    setCaseIndex(nextIndex);
    setMessage("");
  }

  async function goToNextCase() {
    const incomplete = firstIncompleteValidityItem();
    if (incomplete) {
      setMessage(`还有未完成的质检项：${incomplete.label}`);
      focusValidityItem(incomplete.id);
      return;
    }
    await saveValidityReview({ goNext: caseIndex < totalCases - 1 });
  }

  return (
    <div className="annotation-page">
      <section className="annotation-topbar">
        <div className="annotation-control-row">
          <Field label="运行记录">
            <select className="select" value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>{annotationRunLabel(run)}</option>
              ))}
            </select>
          </Field>
          <Field label="质检进度">
            <div className="annotation-progress">
              <Progress value={reviewedCount} max={totalCases || 1} />
              <span>{reviewedCount}/{totalCases || 0}</span>
            </div>
          </Field>
          <Field label="当前 Case">
            <select className="select" value={caseIndex} onChange={(event) => selectCase(Number(event.target.value))}>
              {cases().map((item: JsonObject, index: number) => (
                <option key={item.case_id} value={index}>
                  {index + 1}. {item.case_id}{item.validity_review?.review_complete ? " - 已质检" : ""}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </section>

      {message ? <div className="message">{message}</div> : null}

      {!runs.length ? (
        <Empty text="还没有运行记录，先运行一次评测。" />
      ) : !current.case_id ? (
        <Empty text="当前运行没有可质检的 case。" />
      ) : (
        <div className="annotation-layout">
          <section className="panel annotation-left">
            <PanelHeader title="对话与测试设计" icon={<MessageSquareText size={18} />} />
            <div className="conversation annotation-conversation">
              {(current.turns || []).map((turn: JsonObject, index: number) => (
                <div key={`${turn.role}-${index}`} className={`turn ${turn.role === "agent" ? "agent" : "user"}`}>
                  <div className="turn-meta">
                    <span>第 {index} 轮 · {turn.role === "agent" ? "客服" : "用户"}</span>
                  </div>
                  <div className="turn-text">{turn.text}</div>
                </div>
              ))}
            </div>
            <div className="target-list">
              <div className="target-card">
                <div className="case-row-top">
                  <strong>{current.case_name || current.case_id}</strong>
                  <Chip tone={current.priority === "P0" ? "red" : "amber"}>{current.priority || "P?"}</Chip>
                </div>
                <p>planned targets：{(current.planned_targets || []).join("、") || "无"}</p>
                <small>结束原因：{current.end_reason || "无"}；轮次：{current.turns_count || (current.turns || []).length}</small>
              </div>
              <div className="target-card">
                <strong>用户隐藏目标</strong>
                <p>{validityHints.private_goal || "无"}</p>
                <small>未知事实：{(validityHints.unknown_facts || []).join("、") || "无"}</small>
              </div>
            </div>
          </section>

          <section className="panel annotation-right">
            <PanelHeader title="Case 有效性质检" icon={<ClipboardList size={18} />} />
            <div className="metric-grid annotation-score-grid">
              <Metric label="总 Case" value={totalCases} />
              <Metric label="已质检" value={reviewedCount} tone={reviewedCount === totalCases ? "green" : "amber"} />
              <Metric label="当前判定" value={caseValidityLabel(form.case_validity)} tone={validityStatusTone(form.case_validity)} />
              <Metric label="高价值目标" value={`${validityHints.high_value_target_count ?? 0}/${validityHints.target_count ?? 0}`} tone={validityHints.low_value_only_targets ? "red" : "green"} />
            </div>

            <Field label="质检人">
              <input className="input" value={form.annotator_id || ""} onChange={(event) => updateForm({ annotator_id: event.target.value })} />
            </Field>

            <div
              ref={(element) => { itemRefs.current["validity-overall"] = element; }}
              className="validity-panel"
            >
              <div className="validity-hints">
                <Chip tone={validityHints.last_user_has_question ? "red" : "green"}>
                  {validityHints.last_user_has_question ? "最后用户仍在提问" : "最后用户无明显追问"}
                </Chip>
                <Chip tone={validityHints.low_value_only_targets ? "red" : validityHints.high_value_target_count ? "green" : "amber"}>
                  高价值目标 {validityHints.high_value_target_count ?? 0}/{validityHints.target_count ?? 0}
                </Chip>
                <Chip tone={validityHints.premature_coverage_complete ? "red" : validityHints.coverage_complete_stop ? "amber" : "green"}>
                  {validityHints.end_reason || "无结束原因"}
                </Chip>
                {validityHints.max_turns_stop ? <Chip tone="amber">max_turns 硬停</Chip> : null}
              </div>
              <div className="form-grid compact validity-overall-grid">
                <Field label="总判定">
                  <select className="select" value={form.case_validity || "unreviewed"} onChange={(event) => updateForm({ case_validity: event.target.value })}>
                    {caseValidityOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label="系统提示">
                  <button className="button" type="button" onClick={applyValiditySuggestions}>应用建议</button>
                </Field>
              </div>
              <div className="validity-context">
                <span>成功结束条件：{validityHints.stop_success_end || "无"}</span>
                <span>强制结束条件：{validityHints.stop_forced_end || "无"}</span>
              </div>
              <Field label="有效性备注">
                <textarea className="textarea" value={form.validity_notes || ""} onChange={(event) => updateForm({ validity_notes: event.target.value })} />
              </Field>
            </div>

            <div className="check-list validity-check-list">
              {(form.validity_checks || []).map((check: JsonObject) => {
                const itemId = `validity-${check.check_id}`;
                return (
                  <div
                    key={check.check_id}
                    ref={(element) => { itemRefs.current[itemId] = element; }}
                    className="target-card validity-card"
                  >
                    <div className="case-row-top">
                      <strong>{check.label || check.check_id}</strong>
                      <Chip tone={validityStatusTone(check.status)}>{validityCheckStatusLabel(check.status)}</Chip>
                    </div>
                    <p>{check.description || validityCheckDescription(check.check_id)}</p>
                    <small>{validityHintText(check.check_id, current)}</small>
                    <div className="form-grid compact annotation-fact-grid">
                      <Field label="人工判断">
                        <select className="select" value={check.status || "unreviewed"} onChange={(event) => updateValidityCheck(check.check_id, { status: event.target.value })}>
                          {validityCheckStatusOptions.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="证据轮次">
                        <input className="input" type="number" min={0} value={check.turn_index ?? ""} onChange={(event) => updateValidityCheck(check.check_id, { turn_index: event.target.value === "" ? null : Number(event.target.value) })} />
                      </Field>
                      <Field label="判断依据">
                        <textarea className="textarea" value={check.evidence || ""} onChange={(event) => updateValidityCheck(check.check_id, { evidence: event.target.value })} />
                      </Field>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="actions annotation-actions">
              <button className="button" disabled={caseIndex <= 0 || saving} onClick={goToPreviousCase}>上一条</button>
              <button className="button primary" disabled={saving} onClick={goToNextCase}>
                {caseIndex >= totalCases - 1 ? "完成质检" : "保存并下一条"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function AnnotationWorkbench({ runs }: { runs: JsonObject[] }) {
  const [selectedRun, setSelectedRun] = useState(runs[0]?.run_id || "");
  const [data, setData] = useState<JsonObject>({});
  const [caseIndex, setCaseIndex] = useState(0);
  const [form, setForm] = useState<JsonObject>({});
  const [formDirty, setFormDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [flashItemId, setFlashItemId] = useState("");
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!selectedRun && runs[0]?.run_id) setSelectedRun(runs[0].run_id);
  }, [runs, selectedRun]);

  useEffect(() => {
    if (!selectedRun) return;
    loadAnnotationRun(selectedRun);
  }, [selectedRun]);

  useEffect(() => {
    resetAnnotationForm();
  }, [data.run_id, caseIndex]);

  async function loadAnnotationRun(runId: string) {
    try {
      const next = await apiJson(`/annotations/runs/${runId}`);
      setData(next);
      setCaseIndex(0);
      setMessage("");
    } catch (error) {
      setData({});
      setMessage(errorMessage(error));
    }
  }

  function resetAnnotationForm() {
    const current = currentCase();
    const annotation = current.annotation || {};
    const rubric = data.scoring_rubric || {};
    setForm({
      annotator_id: annotation.annotator_id || "human_01",
      covered_targets: annotation.covered_targets || [],
      target_checks: annotation.target_checks || defaultTargetChecks(current, annotation.covered_targets || []),
      dimension_checks: annotation.dimension_checks || defaultDimensionChecks(data.dimension_check_templates || [], rubric),
      risk_flags: annotation.risk_flags || [],
      veto_items: annotation.veto_items || [],
      notes: annotation.notes || ""
    });
    setFormDirty(false);
    setFlashItemId("");
  }

  function cases() {
    return data.cases || [];
  }

  function currentCase() {
    return cases()[caseIndex] || {};
  }

  const current = currentCase();
  const totalCases = cases().length;
  const annotatedCount = Number(data.annotated_count || 0);
  const computed = annotationTotals(form, data.scoring_rubric || {});
  const selectedVeto = new Set<string>((form.veto_items || []).map((item: JsonObject) => String(item.rule_id)));
  const riskByRule = new Map<string, JsonObject>((form.risk_flags || []).map((item: JsonObject) => [String(item.rule_id), item]));
  const targetDefinitionByLabel = new Map<string, JsonObject>(
    (current.target_definitions || []).map((target: JsonObject) => [String(target.label), target])
  );

  useEffect(() => {
    if (!formDirty || !selectedRun || !current.case_id || !form.annotator_id) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      saveAnnotation({ silent: true }).catch(() => undefined);
    }, 700);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, [form, formDirty, selectedRun, current.case_id]);

  function updateForm(patch: JsonObject) {
    setForm((currentForm) => ({ ...currentForm, ...patch }));
    setFormDirty(true);
  }

  function updateTargetCheck(index: number, patch: JsonObject) {
    setFormDirty(true);
    setForm((currentForm) => {
      const next = [...(currentForm.target_checks || [])];
      next[index] = { ...next[index], ...patch };
      return { ...currentForm, target_checks: next };
    });
  }

  function updateDimensionCheck(checkId: string, patch: JsonObject) {
    setFormDirty(true);
    setForm((currentForm) => {
      const next = (currentForm.dimension_checks || []).map((item: JsonObject) => item.check_id === checkId ? { ...item, ...patch } : item);
      return { ...currentForm, dimension_checks: next };
    });
  }

  function toggleRisk(rule: JsonObject, checked: boolean) {
    setFormDirty(true);
    setForm((currentForm) => {
      const existing = currentForm.risk_flags || [];
      if (!checked) {
        return { ...currentForm, risk_flags: existing.filter((item: JsonObject) => item.rule_id !== rule.rule_id) };
      }
      if (existing.some((item: JsonObject) => item.rule_id === rule.rule_id)) return currentForm;
      return {
        ...currentForm,
        risk_flags: [
          ...existing,
          {
            rule_id: rule.rule_id,
            description: rule.description || "",
            severity: rule.severity || "",
            deduction: Number(rule.default_deduction || 0),
            evidence: ""
          }
        ]
      };
    });
  }

  function updateRisk(ruleId: string, patch: JsonObject) {
    setFormDirty(true);
    setForm((currentForm) => ({
      ...currentForm,
      risk_flags: (currentForm.risk_flags || []).map((item: JsonObject) => item.rule_id === ruleId ? { ...item, ...patch } : item)
    }));
  }

  function toggleVeto(rule: JsonObject, checked: boolean) {
    setFormDirty(true);
    setForm((currentForm) => {
      const existing = currentForm.veto_items || [];
      if (!checked) {
        return { ...currentForm, veto_items: existing.filter((item: JsonObject) => item.rule_id !== rule.rule_id) };
      }
      if (existing.some((item: JsonObject) => item.rule_id === rule.rule_id)) return currentForm;
      return {
        ...currentForm,
        veto_items: [
          ...existing,
          {
            rule_id: rule.rule_id,
            description: rule.description || "",
            severity: rule.severity || "critical",
            evidence: ""
          }
        ]
      };
    });
  }

  function updateVeto(ruleId: string, patch: JsonObject) {
    setFormDirty(true);
    setForm((currentForm) => ({
      ...currentForm,
      veto_items: (currentForm.veto_items || []).map((item: JsonObject) => item.rule_id === ruleId ? { ...item, ...patch } : item)
    }));
  }

  async function saveAnnotation(options: { goNext?: boolean; silent?: boolean } = {}) {
    const { goNext = false, silent = false } = options;
    if (!selectedRun || !current.case_id) return;
    if (!silent) setSaving(true);
    if (!silent) setMessage("");
    try {
      const saved = await apiJson(`/annotations/runs/${selectedRun}/cases/${current.case_id}`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(form)
      });
      setData((currentData) => {
        const nextCases = (currentData.cases || []).map((item: JsonObject) => item.case_id === current.case_id ? { ...item, annotation: saved } : item);
        return {
          ...currentData,
          cases: nextCases,
          annotated_count: nextCases.filter((item: JsonObject) => annotationIsComplete(item.annotation)).length
        };
      });
      setFormDirty(false);
      if (!silent) {
        setMessage(
          saved.review_complete
            ? `已保存 ${current.case_id}，人工总分 ${saved.human_score}。`
            : `已保存 ${current.case_id} 草稿，完成全部事实核查后生成正式总分。`
        );
      }
      if (goNext && caseIndex < totalCases - 1) setCaseIndex(caseIndex + 1);
    } catch (error) {
      if (!silent) setMessage(errorMessage(error));
    } finally {
      if (!silent) setSaving(false);
    }
  }

  function firstIncompleteItem() {
    const target = (form.target_checks || []).find((item: JsonObject) => !item.status || item.status === "unreviewed");
    if (target) {
      return {
        id: `target-${target.target}`,
        label: targetDefinitionByLabel.get(String(target.target))?.name || target.target || "覆盖事实"
      };
    }
    const dimension = (form.dimension_checks || []).find((item: JsonObject) => !item.status || item.status === "unreviewed");
    if (dimension) {
      return {
        id: `dimension-${dimension.check_id}`,
        label: dimension.description || dimension.dimension_name || "维度扣分事实"
      };
    }
    return null;
  }

  function focusAnnotationItem(itemId: string) {
    const element = itemRefs.current[itemId];
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashItemId(itemId);
    window.setTimeout(() => setFlashItemId((currentId) => currentId === itemId ? "" : currentId), 1600);
  }

  async function goToPreviousCase() {
    if (formDirty) await saveAnnotation({ silent: true });
    if (caseIndex > 0) setCaseIndex(caseIndex - 1);
  }

  async function selectCase(nextIndex: number) {
    if (nextIndex === caseIndex) return;
    if (formDirty) await saveAnnotation({ silent: true });
    setCaseIndex(nextIndex);
    setMessage("");
  }

  async function goToNextCase() {
    const incomplete = firstIncompleteItem();
    if (incomplete) {
      setMessage(`还有未完成的表单项：${incomplete.label}`);
      focusAnnotationItem(incomplete.id);
      return;
    }
    await saveAnnotation({ goNext: caseIndex < totalCases - 1 });
  }

  return (
    <div className="annotation-page">
      <section className="annotation-topbar">
        <div className="annotation-control-row">
          <Field label="运行记录">
            <select className="select" value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>{annotationRunLabel(run)}</option>
              ))}
            </select>
          </Field>
          <Field label="标注进度">
            <div className="annotation-progress">
              <Progress value={annotatedCount} max={totalCases || 1} />
              <span>{annotatedCount}/{totalCases || 0}</span>
            </div>
          </Field>
          <Field label="当前 Case">
            <select className="select" value={caseIndex} onChange={(event) => selectCase(Number(event.target.value))}>
              {cases().map((item: JsonObject, index: number) => (
                <option key={item.case_id} value={index}>
                  {index + 1}. {item.case_id}{annotationIsComplete(item.annotation) ? " - 已标注" : ""}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </section>

      {message ? <div className="message">{message}</div> : null}

      {!runs.length ? (
        <Empty text="还没有运行记录，先运行一次评测。" />
      ) : !current.case_id ? (
        <Empty text="当前运行没有可标注的 case。" />
      ) : (
        <div className="annotation-layout">
          <section className="panel annotation-left">
            <h3>对话记录</h3>
            <div className="conversation annotation-conversation">
              {(current.turns || []).map((turn: JsonObject, index: number) => (
                <div key={`${turn.role}-${index}`} className={`turn ${turn.role === "agent" ? "agent" : "user"}`}>
                  <div className="turn-meta">
                    <span>第 {index} 轮 · {turn.role === "agent" ? "客服" : "用户"}</span>
                  </div>
                  <div className="turn-text">{turn.text}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="panel annotation-right">
            <PanelHeader title="标注表单" icon={<ClipboardCheck size={18} />} />
            <div className="metric-grid annotation-score-grid">
              <Metric label="正式总分" value={computed.reviewComplete ? computed.totalScore.toFixed(2) : "待核查"} tone={computed.reviewComplete ? scoreTone(computed.totalScore) : "amber"} />
              <Metric label="合格线" value={computed.passThreshold} />
              <Metric label="人工结论" value={computed.reviewComplete ? (computed.passed ? "通过" : "未通过") : "待核查"} tone={computed.reviewComplete ? (computed.passed ? "green" : "red") : "amber"} />
              <Metric label="已核查" value={`${computed.reviewedFacts}/${computed.totalFacts}`} tone={computed.reviewComplete ? "green" : "amber"} />
            </div>

            <Field label="标注人">
              <input className="input" value={form.annotator_id || ""} onChange={(event) => updateForm({ annotator_id: event.target.value })} />
            </Field>

            <h3>覆盖事实核查</h3>
            <div className="check-list">
              {(form.target_checks || []).map((check: JsonObject, index: number) => {
                const target = targetDefinitionByLabel.get(String(check.target)) || {};
                const itemId = `target-${check.target}`;
                return (
                  <div
                    key={check.target || index}
                    ref={(element) => { itemRefs.current[itemId] = element; }}
                    className={`target-card ${flashItemId === itemId ? "annotation-flash" : ""}`}
                  >
                    <div className="case-row-top">
                      <strong>{target.name || check.target}</strong>
                      <Chip tone={check.status === "satisfied" ? "green" : check.status === "partial" ? "amber" : check.status === "missing" ? "red" : ""}>
                        {targetStatusLabel(check.status)}
                      </Chip>
                    </div>
                    <p>{target.definition || target.evidence_required || check.target}</p>
                    {target.evidence_required ? <small>{target.evidence_required}</small> : null}
                    <div className="form-grid compact annotation-fact-grid">
                      <Field label="事实判定">
                        <select className="select" value={check.status || "unreviewed"} onChange={(event) => updateTargetCheck(index, { status: event.target.value })}>
                          {targetStatusOptions.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="证据轮次">
                        <input className="input" type="number" min={0} value={check.turn_index ?? ""} onChange={(event) => updateTargetCheck(index, { turn_index: event.target.value === "" ? null : Number(event.target.value) })} />
                      </Field>
                      <Field label="证据说明">
                        <textarea className="textarea" value={check.evidence || ""} onChange={(event) => updateTargetCheck(index, { evidence: event.target.value })} />
                      </Field>
                    </div>
                  </div>
                );
              })}
            </div>

            <h3>维度扣分事实</h3>
            <div className="grid">
              {(data.scoring_rubric?.dimensions || []).map((rubricDimension: JsonObject) => {
                const dimensionScore = computed.dimensionScores.find((item: JsonObject) => item.dimension_id === rubricDimension.dimension_id) || {};
                const checks = (form.dimension_checks || []).filter((item: JsonObject) => item.dimension_id === rubricDimension.dimension_id);
                const dimensionReviewComplete = checks.length > 0 && checks.every((item: JsonObject) => item.status && item.status !== "unreviewed");
                return (
                  <div key={rubricDimension.dimension_id} className="dimension-editor">
                    <div className="case-row-top">
                      <strong>{rubricDimension.name || rubricDimension.dimension_id}</strong>
                      <span>得分 {dimensionReviewComplete ? display(dimensionScore.score) : "待核查"}/{display(rubricDimension.weight)}</span>
                    </div>
                    {rubricDimension.description ? <p>{rubricDimension.description}</p> : null}
                    {rubricDimension.full_score_standard ? <small>满分标准：{rubricDimension.full_score_standard}</small> : null}
                    <div className="check-list">
                      {checks.map((check: JsonObject) => (
                        <div
                          key={check.check_id}
                          ref={(element) => { itemRefs.current[`dimension-${check.check_id}`] = element; }}
                          className={`rule-card ${flashItemId === `dimension-${check.check_id}` ? "annotation-flash" : ""}`}
                        >
                          <div className="case-row-top">
                            <strong>{check.description || check.check_id}</strong>
                            <Chip tone={check.status === "not_triggered" ? "green" : check.status === "partial" ? "amber" : check.status === "triggered" || check.status === "unreviewed" ? "red" : ""}>
                              {dimensionCheckStatusLabel(check.status)}
                            </Chip>
                          </div>
                          <small>该事实项触发时扣 {display(check.deduction)} 分；部分触发扣一半。</small>
                          <div className="form-grid compact annotation-fact-grid">
                            <Field label="事实判定">
                              <select className="select" value={check.status || "unreviewed"} onChange={(event) => updateDimensionCheck(check.check_id, { status: event.target.value })}>
                                {dimensionCheckStatusOptions.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </Field>
                            <Field label="证据轮次">
                              <input className="input" type="number" min={0} value={check.turn_index ?? ""} onChange={(event) => updateDimensionCheck(check.check_id, { turn_index: event.target.value === "" ? null : Number(event.target.value) })} />
                            </Field>
                            <Field label="证据说明">
                              <textarea className="textarea" value={check.evidence || ""} onChange={(event) => updateDimensionCheck(check.check_id, { evidence: event.target.value })} />
                            </Field>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <h3>风险扣分</h3>
            <RuleChecklist
              rules={data.scoring_rubric?.risk_rules || []}
              selected={riskByRule}
              onToggle={toggleRisk}
              onUpdate={updateRisk}
              type="risk"
            />

            <h3>一票否决</h3>
            <RuleChecklist
              rules={data.scoring_rubric?.veto_rules || []}
              selected={new Map<string, JsonObject>((form.veto_items || []).map((item: JsonObject) => [String(item.rule_id), item]))}
              selectedIds={selectedVeto}
              onToggle={toggleVeto}
              onUpdate={updateVeto}
              type="veto"
            />

            <Field label="备注">
              <textarea className="textarea" value={form.notes || ""} onChange={(event) => updateForm({ notes: event.target.value })} />
            </Field>

            <div className="actions annotation-actions">
              <button className="button" disabled={caseIndex <= 0 || saving} onClick={goToPreviousCase}>上一条</button>
              <button className="button primary" disabled={saving} onClick={goToNextCase}>
                {caseIndex >= totalCases - 1 ? "完成校验" : "下一条"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function RuleChecklist({
  rules,
  selected,
  selectedIds,
  onToggle,
  onUpdate,
  type
}: {
  rules: JsonObject[];
  selected: Map<any, any>;
  selectedIds?: Set<string>;
  onToggle: (rule: JsonObject, checked: boolean) => void;
  onUpdate: (ruleId: string, patch: JsonObject) => void;
  type: "risk" | "veto";
}) {
  if (!rules.length) return <Empty text={type === "risk" ? "当前评分规则没有风险扣分项。" : "当前评分规则没有一票否决项。"} />;
  return (
    <div className="check-list">
      {rules.map((rule) => {
        const checked = selectedIds ? selectedIds.has(rule.rule_id) : selected.has(rule.rule_id);
        const value = selected.get(rule.rule_id) || {};
        return (
          <div key={rule.rule_id} className="rule-card">
            <label className="check-row">
              <input type="checkbox" checked={checked} onChange={(event) => onToggle(rule, event.target.checked)} />
              <span>{rule.description || rule.rule_id}</span>
            </label>
            <small>{rule.evidence_required || rule.severity}</small>
            {checked ? (
              <div className="form-grid compact">
                {type === "risk" ? (
                  <Field label="扣分">
                    <input className="input" type="number" min={0} step={0.5} value={value.deduction || 0} onChange={(event) => onUpdate(rule.rule_id, { deduction: Number(event.target.value) })} />
                  </Field>
                ) : null}
                <Field label="证据轮次">
                  <input className="input" type="number" min={0} value={value.turn_index ?? ""} onChange={(event) => onUpdate(rule.rule_id, { turn_index: event.target.value === "" ? null : Number(event.target.value) })} />
                </Field>
                <Field label="证据说明">
                  <textarea className="textarea" value={value.evidence || ""} onChange={(event) => onUpdate(rule.rule_id, { evidence: event.target.value })} />
                </Field>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function SystemManagement({
  assets,
  runs,
  registryStatus,
  health,
  onRefresh
}: {
  assets: JsonObject[];
  runs: JsonObject[];
  registryStatus: JsonObject;
  health: JsonObject;
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState("assets");
  const tabs = [
    ["assets", "测试设计"],
    ["prompts", "Prompt 管理"],
    ["registry", "数据沉淀"],
    ["calls", "模型调用"],
    ["health", "服务状态"]
  ];
  return (
    <>
      <section className="admin-mode-note">
        <div>
          <strong>开发者与管理员工具</strong>
          <span>这里用于检查测试设计、Prompt、数据沉淀、模型调用和服务健康，普通评测流程优先使用新建评测与评测报告。</span>
        </div>
      </section>
      <div className="tabs">
        {tabs.map(([key, label]) => (
          <button key={key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>
            {label}
          </button>
      ))}
      </div>
      {tab === "assets" ? <AssetsCenter assets={assets} embedded /> : null}
      {tab === "prompts" ? <PromptSettings onRefresh={onRefresh} /> : null}
      {tab === "registry" ? <RegistryCenter status={registryStatus} onRefresh={onRefresh} embedded /> : null}
      {tab === "calls" ? <ModelCalls runs={runs} /> : null}
      {tab === "health" ? <ServiceStatus health={health} /> : null}
    </>
  );
}

function ServiceStatus({ health }: { health: JsonObject }) {
  const tracing = health.tracing || {};
  const registry = health.registry || {};
  return (
    <section className="panel">
      <PanelHeader title="服务状态" icon={<Activity size={18} />} />
      <div className="health-grid">
        <HealthCard title="API" status={health.status === "ok" ? "正常" : "异常"} tone={health.status === "ok" ? "green" : "red"} detail={health.project_root || "-"} />
        <HealthCard title="数据沉淀" status={`${registry.experiments || 0} 个实验`} tone="green" detail={`${registry.case_runs || 0} 个 case run`} />
        <HealthCard title="Trace" status={tracing.enabled ? "已开启" : "未开启"} tone={tracing.enabled ? "green" : "amber"} detail={tracing.endpoint || tracing.provider || "-"} />
        <HealthCard title="输出目录" status="可用" tone="green" detail={health.runs_root || health.assets_root || "-"} />
      </div>
      <details className="developer-raw">
        <summary>查看原始健康信息</summary>
        <pre className="code">{JSON.stringify(health, null, 2)}</pre>
      </details>
    </section>
  );
}

function HealthCard({ title, status, detail, tone }: { title: string; status: string; detail: string; tone: string }) {
  return (
    <div className="health-card">
      <div className="metric-label">{title}</div>
      <div className={`metric-value text-${tone}`}>{status}</div>
      <div className="mono-value" title={detail}>{detail}</div>
    </div>
  );
}

function RegistryCenter({ status, onRefresh, embedded = false }: { status: JsonObject; onRefresh: () => Promise<void>; embedded?: boolean }) {
  const [datasets, setDatasets] = useState<JsonObject[]>([]);
  const [experiments, setExperiments] = useState<JsonObject[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    const [datasetData, experimentData] = await Promise.all([
      apiJson("/registry/datasets"),
      apiJson("/registry/experiments")
    ]);
    setDatasets(datasetData.datasets || []);
    setExperiments(experimentData.experiments || []);
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)));
  }, []);

  async function indexExisting() {
    setMessage("");
    try {
      const result = await apiJson("/registry/index-existing", { method: "POST" });
      setMessage(`回填完成：${result.indexed_runs || 0} 个运行记录`);
      await load();
      await onRefresh();
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <>
      {!embedded ? (
        <PageHeader
          actions={
            <button className="button" onClick={indexExisting}>
              <RefreshCw size={16} />
              扫描已有 outputs
            </button>
          }
        />
      ) : (
        <div className="section-toolbar">
          <div>
            <h2>数据沉淀</h2>
          </div>
          <button className="button" onClick={indexExisting}>
            <RefreshCw size={16} />
            扫描已有 outputs
          </button>
        </div>
      )}
      {message ? <div className="message">{message}</div> : null}
      <div className="metric-grid">
        <Metric label="Datasets" value={status.datasets || 0} />
        <Metric label="任务指令" value={status.task_instructions || 0} />
        <Metric label="资产版本" value={status.asset_versions || 0} />
        <Metric label="实验" value={status.experiments || 0} />
        <Metric label="Case Runs" value={status.case_runs || 0} />
        <Metric label="LLM Calls" value={status.llm_calls || 0} />
      </div>
      <div className="grid two">
        <section className="panel">
          <PanelHeader title="Datasets" icon={<Database size={18} />} />
          <DataTable
            rows={datasets}
            columns={[
              ["dataset_id", "编号"],
              ["source_type", "类型"],
              ["source_path", "来源"],
              ["created_at", "创建时间"]
            ]}
          />
        </section>
        <section className="panel">
          <PanelHeader title="Experiments" icon={<Workflow size={18} />} />
          <DataTable
            rows={experiments}
            columns={[
              ["run_display_name", "实验"],
              ["scene_id", "场景"],
              ["status", "状态"],
              ["run_display_time", "发起时间"]
            ]}
          />
        </section>
      </div>
    </>
  );
}

function SystemSettings({ health, runs, onRefresh }: { health: JsonObject; runs: JsonObject[]; onRefresh: () => Promise<void> }) {
  const [tab, setTab] = useState("prompts");
  return (
    <>
      <div className="tabs">
        {[
          ["prompts", "Prompt 管理"],
          ["calls", "模型调用"],
          ["health", "服务状态"]
        ].map(([key, label]) => (
          <button key={key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "prompts" ? <PromptSettings onRefresh={onRefresh} /> : null}
      {tab === "calls" ? <ModelCalls runs={runs} /> : null}
      {tab === "health" ? (
        <section className="panel">
          <pre className="code">{JSON.stringify(health, null, 2)}</pre>
        </section>
      ) : null}
    </>
  );
}

function PromptSettings({ onRefresh }: { onRefresh: () => Promise<void> }) {
  const [status, setStatus] = useState<JsonObject>({});
  const [modelName, setModelName] = useState("deepseek-chat");
  const [dryRun, setDryRun] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setStatus(await apiJson("/prompts/status"));
  }

  useEffect(() => {
    load().catch((error) => setMessage(errorMessage(error)));
  }, []);

  async function syncPrompts() {
    try {
      const result = await apiJson("/prompts/sync", {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({ model_name: modelName, dry_run: dryRun })
      });
      setMessage(`同步完成：${result.count || 0} 个 Prompt`);
      await load();
      await onRefresh();
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <section className="panel">
      <PanelHeader title="Prompt 管理" icon={<ClipboardList size={18} />} />
      {message ? <div className="message">{message}</div> : null}
      <div className="metric-grid">
        <Metric label="Provider" value={status.provider || "local"} />
        <Metric label="Phoenix" value={status.enabled ? "on" : "off"} />
        <Metric label="Prompt 数" value={status.prompt_count || 0} />
        <Metric label="Cache" value={`${status.cache_seconds || 0}s`} />
        <Metric label="Strict" value={status.strict ? "on" : "off"} />
      </div>
      <div className="config-line">
        <span>Base URL</span>
        <code title={status.phoenix_base_url || "-"}>{status.phoenix_base_url || "-"}</code>
      </div>
      <div className="form-grid">
        <Field label="同步记录模型名">
          <input className="input" value={modelName} onChange={(event) => setModelName(event.target.value)} />
        </Field>
        <Field label="模式">
          <label className="chip">
            <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
            只预览，不写入 Phoenix
          </label>
        </Field>
      </div>
      <div className="actions" style={{ margin: "14px 0" }}>
        <button className="button primary" onClick={syncPrompts}>
          <RefreshCw size={16} />
          同步默认 Prompt
        </button>
      </div>
      <DataTable
        rows={status.prompts || []}
        columns={[
          ["name", "名称"],
          ["role", "角色"],
          ["description", "说明"],
          ["variables", "变量"]
        ]}
      />
    </section>
  );
}

function ModelCalls({ runs }: { runs: JsonObject[] }) {
  const [runId, setRunId] = useState(runs[0]?.run_id || "");
  const [calls, setCalls] = useState<JsonObject[]>([]);
  const successfulCalls = calls.filter((call) => call.success !== false).length;
  const failedCalls = calls.length - successfulCalls;
  const averageLatency = calls.length
    ? Math.round(calls.reduce((total, call) => total + Number(call.latency_ms || 0), 0) / calls.length)
    : 0;
  const totalTokens = calls.reduce((total, call) => total + Number(call.total_tokens || 0), 0);

  useEffect(() => {
    if (!runId && runs[0]?.run_id) setRunId(runs[0].run_id);
  }, [runs, runId]);

  useEffect(() => {
    if (!runId) return;
    apiText(`/runs/${runId}/reports/llm_calls.jsonl`)
      .then((text) => setCalls(parseJsonl(text)))
      .catch(() => setCalls([]));
  }, [runId]);

  return (
    <section className="panel">
      <PanelHeader title="模型调用" icon={<Activity size={18} />} />
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <select className="select" style={{ maxWidth: 420 }} value={runId} onChange={(event) => setRunId(event.target.value)}>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {runLabel(run)}
            </option>
          ))}
        </select>
      </div>
      <div className="metric-grid model-call-metrics">
        <Metric label="调用数" value={calls.length} />
        <Metric label="成功" value={successfulCalls} tone={failedCalls ? "amber" : "green"} />
        <Metric label="失败" value={failedCalls} tone={failedCalls ? "red" : "green"} />
        <Metric label="平均耗时" value={`${averageLatency}ms`} />
        <Metric label="Token" value={totalTokens || "-"} />
        <Metric label="模型数" value={new Set(calls.map((call) => call.model).filter(Boolean)).size || "-"} />
      </div>
      <DataTable
        rows={calls}
        columns={[
          ["started_at", "时间"],
          ["task_name", "任务"],
          ["role", "角色"],
          ["model", "模型"],
          ["latency_ms", "耗时"],
          ["prompt_chars", "输入字符"],
          ["completion_chars", "输出字符"],
          ["total_tokens", "Token"],
          ["estimated_cost", "成本"],
          ["success", "成功"],
          ["error", "错误"]
        ]}
      />
    </section>
  );
}

function CaseDetail({ evaluation, conversation }: { evaluation: JsonObject; conversation: JsonObject }) {
  const turns = conversation.turns || [];
  const scores = evaluation.dimension_scores || [];
  const missingTargets = evaluation.missing_targets || conversation.missing_targets || [];
  const riskDeductions = evaluation.risk_deductions || conversation.risk_flags || [];
  const vetoItems = evaluation.veto_items || [];
  const caseId = evaluation.case_id || conversation.case_id || "Case 详情";
  return (
    <section className="panel case-detail-panel">
      <PanelHeader
        title={caseId}
        icon={<MessageSquareText size={18} />}
        actions={
          <div className="toolbar">
            <ScoreChip score={evaluation.total_score} passed={evaluation.passed} />
            <Chip tone={(missingTargets || []).length ? "amber" : "green"}>缺失 {missingTargets.length}</Chip>
            <Chip tone={(riskDeductions || []).length ? "red" : "green"}>风险 {riskDeductions.length}</Chip>
          </div>
        }
      />
      <div className="metric-grid case-summary-grid">
        <Metric label="总分" value={display(evaluation.total_score)} tone={scoreTone(evaluation.total_score)} />
        <Metric label="合格线" value={display(evaluation.pass_threshold)} />
        <Metric label="通过" value={evaluation.passed ? "是" : "否"} tone={evaluation.passed ? "green" : "red"} />
        <Metric label="风险扣分" value={display(evaluation.risk_deduction_total)} />
      </div>
      <div className="evidence-chain">
        <EvidenceCard
          title="缺失检查点"
          items={missingTargets}
          emptyText="没有缺失检查点。"
          tone={missingTargets.length ? "amber" : "green"}
        />
        <EvidenceCard
          title="风险扣分"
          items={riskDeductions}
          emptyText="没有风险扣分。"
          tone={riskDeductions.length ? "red" : "green"}
        />
        <EvidenceCard
          title="一票否决"
          items={vetoItems}
          emptyText="没有一票否决。"
          tone={vetoItems.length ? "red" : "green"}
        />
      </div>
      <div className="case-detail-content">
        <section className="case-detail-block conversation-block">
          <div className="case-detail-block-head">
            <h3>原始对话</h3>
            <Chip>{turns.length} 轮</Chip>
          </div>
          <div className="conversation">
            {turns.length ? (
              turns.map((turn: JsonObject, index: number) => (
                <div key={`${turn.role}-${index}`} className={`turn ${turn.role === "agent" ? "agent" : "user"}`}>
                  <div className="turn-meta">
                    <span>{index}. {turn.role === "agent" ? "客服" : "用户"}</span>
                    {turn.intent ? <span>{turn.intent}</span> : null}
                    {turn.emotion ? <span>{turn.emotion}</span> : null}
                    {turn.patience !== null && turn.patience !== undefined ? <span>耐心 {turn.patience}</span> : null}
                  </div>
                  <div className="turn-text">{turn.text}</div>
                </div>
              ))
            ) : (
              <Empty text="没有对话记录。" />
            )}
          </div>
        </section>
        <section className="case-detail-block score-block">
          <div className="case-detail-block-head">
            <h3>评分维度</h3>
            <Chip>{scores.length} 项</Chip>
          </div>
          <div className="score-dimension-list">
            {scores.length ? (
              scores.map((score: JsonObject) => (
                <div key={score.dimension_id || score.name} className="dimension-score-card">
                  <div className="case-row-top">
                    <strong>{score.name}</strong>
                    <span>{score.score}/{score.weight}</span>
                  </div>
                  <Progress value={score.score} max={score.weight} />
                  <p className="panel-caption">{score.reason}</p>
                  {(score.missing_points || []).length ? (
                    <div className="actions">
                      {score.missing_points.map((item: string) => (
                        <Chip key={item} tone="amber">{item}</Chip>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <Empty text="没有评分维度。" />
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function EvidenceCard({
  title,
  items,
  emptyText,
  tone
}: {
  title: string;
  items: any[];
  emptyText: string;
  tone: string;
}) {
  return (
    <div className="evidence-card">
      <div className="case-row-top">
        <strong>{title}</strong>
        <Chip tone={tone}>{items.length}</Chip>
      </div>
      {items.length ? (
        <div className="evidence-list">
          {items.slice(0, 6).map((item, index) => (
            <div key={`${title}-${index}`} className="evidence-item">
              {typeof item === "string" ? item : item.description || item.rule_id || item.label || JSON.stringify(item)}
              {typeof item === "object" && item.evidence?.length ? (
                <small>{evidenceText(item.evidence)}</small>
              ) : null}
            </div>
          ))}
          {items.length > 6 ? <small>还有 {items.length - 6} 项未展示。</small> : null}
        </div>
      ) : (
        <p className="panel-caption">{emptyText}</p>
      )}
    </div>
  );
}

function RunMetrics({ run }: { run: JsonObject }) {
  return (
    <div className="metric-grid">
      <Metric label="Case 数" value={run.case_count || 0} />
      <Metric label="已评分" value={run.evaluation_count || 0} />
      <Metric label="通过数" value={run.passed_count || 0} />
      <Metric label="覆盖完成" value={`${run.coverage_success_count || 0}/${run.case_count || 0}`} tone={(run.coverage_success_count || 0) === (run.case_count || 0) ? "green" : "amber"} />
      <Metric label="平均分" value={display(run.average_score)} tone={scoreTone(run.average_score)} />
      <Metric label="风险数" value={run.risk_count || 0} tone={run.risk_count ? "red" : "green"} />
    </div>
  );
}

function CaseScoreTable({ evaluations, onSelect }: { evaluations: JsonObject[]; onSelect: (caseId: string) => void }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>优先级</th>
            <th>分数</th>
            <th>状态</th>
            <th>缺失项</th>
            <th>风险</th>
          </tr>
        </thead>
        <tbody>
          {evaluations.map((item) => (
            <tr key={item.case_id} onClick={() => onSelect(item.case_id)}>
              <td><button className="button ghost">{item.case_id}</button></td>
              <td>{item.priority}</td>
              <td><ScoreChip score={item.total_score} passed={item.passed} /></td>
              <td>{item.passed ? <Chip tone="green">通过</Chip> : <Chip tone="red">未通过</Chip>}</td>
              <td>{(item.missing_targets || []).length}</td>
              <td>{(item.risk_deductions || []).length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MissingTargets({ evaluations }: { evaluations: JsonObject[] }) {
  const rows = useMemo(() => {
    const counts = new Map<string, number>();
    evaluations.forEach((item) => {
      (item.missing_targets || []).forEach((target: string) => counts.set(target, (counts.get(target) || 0) + 1));
    });
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([target, count]) => ({ target, count }));
  }, [evaluations]);
  return rows.length ? (
    <DataTable rows={rows} columns={[["target", "检查点"], ["count", "Case 数"]]} />
  ) : (
    <Empty text="没有未覆盖检查点。" />
  );
}

function AssetsTable({ assets }: { assets: JsonObject[] }) {
  return (
    <DataTable
      rows={assets}
      columns={[
        ["scene_name", "场景"],
        ["scene_id", "标识"],
        ["case_count", "Case"],
        ["coverage_label_count", "检查点"],
        ["profile_count", "画像"],
        ["pass_threshold", "合格线"],
        ["asset_version_id", "资产版本"]
      ]}
    />
  );
}

function PageHeader({ actions }: { actions?: ReactNode }) {
  if (!actions) return null;
  return <header className="page-header">{actions ? <div className="toolbar">{actions}</div> : null}</header>;
}

function PanelHeader({ title, icon, actions }: { title: string; icon?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="panel-header">
      <div>
        <div className="panel-title">{title}</div>
      </div>
      {actions ? <div className="toolbar">{actions}</div> : icon ? <span className="chip">{icon}</span> : null}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ? `text-${tone}` : ""}`}>{value}</div>
    </div>
  );
}

function Step({ index, title, note, active, complete }: { index: number; title: string; note: string; active: boolean; complete: boolean }) {
  return (
    <div className={`step ${active ? "active" : ""} ${complete ? "complete" : ""}`}>
      <span className="step-index">{complete ? <CheckCircle2 size={15} /> : index}</span>
      <div className="step-title">{title}</div>
      <div className="step-note">{note}</div>
    </div>
  );
}

function EvaluationProgress({
  job,
  onOpenReport,
  onStartOver,
  onCancel,
  cancelBusy = false
}: {
  job: JsonObject;
  onOpenReport?: (runId: string) => void;
  onStartOver?: () => void;
  onCancel?: () => void;
  cancelBusy?: boolean;
}) {
  const steps = job.steps || [];
  const completedRuns = job.status === "completed" ? (job.result?.runs || []) : [];
  const completedRunId = completedRuns[0]?.run_id || "";
  const datasetResults = collectPhoenixDatasetResults(job.result || {});
  const status = String(job.status || "");
  const canCancel = Boolean(onCancel && ["queued", "running", "cancelling"].includes(status));
  const progressText = progressDetailText(job);
  const counters = progressCounters(job);
  return (
    <section className={`panel progress-panel ${job.status === "failed" ? "failed" : ""} ${job.status === "cancelled" || job.status === "cancelling" ? "cancelled" : ""}`}>
      <div className="progress-head">
        <div>
          <div className="panel-title">{job.stage || "正在评测"}</div>
          <div className="panel-caption">{job.message || "后台任务正在执行。"}</div>
        </div>
        <Chip tone={job.status === "completed" ? "green" : job.status === "failed" || job.status === "cancelled" ? "red" : job.status === "cancelling" ? "amber" : ""}>
          {job.status === "completed" ? "已完成" : job.status === "failed" ? "失败" : job.status === "cancelled" ? "已取消" : job.status === "cancelling" ? "正在取消" : "运行中"}
        </Chip>
      </div>
      <div className="progress-bar" aria-label="评测进度">
        <span style={{ width: `${Math.max(0, Math.min(100, Number(job.percent || 0)))}%` }} />
      </div>
      <div className="progress-meta">
        <span>{display(job.percent)}%</span>
        {progressText ? <span>{progressText}</span> : null}
        {job.details?.scene_name ? <span>场景 {job.details.scene_name}</span> : null}
        {job.details?.run_id ? <span>运行 {job.details.run_id}</span> : null}
        {job.details?.case_id ? <span>Case {job.details.case_id}</span> : null}
      </div>
      {counters.length ? (
        <div className="progress-counters">
          {counters.map((item) => (
            <div className="progress-counter" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              {item.note ? <small>{item.note}</small> : null}
            </div>
          ))}
        </div>
      ) : null}
      <div className="progress-steps">
        {steps.map((step: JsonObject) => (
          <div className={`progress-step ${step.status || "pending"}`} key={step.key}>
            <span className="progress-step-icon">
              {step.status === "completed" ? <CheckCircle2 size={15} /> : step.status === "in_progress" ? <Loader2 size={15} /> : step.status === "failed" || step.status === "cancelled" ? <XCircle size={15} /> : null}
            </span>
            <span>{step.label}</span>
          </div>
        ))}
      </div>
      {datasetResults.length ? (
        <div className="dataset-result-list">
          {datasetResults.map((item, index) => (
            <Chip key={`${item.dataset_type || "dataset"}-${index}`} tone={item.status === "error" ? "red" : "green"}>
              {item.dataset_type === "generated_dialogue" ? "对话归档" : "输入集"} {item.status || "-"} · {item.example_count || 0} 条
            </Chip>
          ))}
        </div>
      ) : null}
      {completedRunId && onOpenReport ? (
        <div className="progress-actions">
          <button className="button primary" onClick={() => onOpenReport(completedRunId)}>
            <BarChart3 size={16} />
            查看评测结果
          </button>
          {onStartOver ? (
            <button className="button" onClick={onStartOver}>
              新建下一次
            </button>
          ) : null}
          {completedRuns.length > 1 ? (
            <span className="panel-caption">本次生成 {completedRuns.length} 份报告，进入后可在报告中心切换查看。</span>
          ) : null}
        </div>
      ) : null}
      {canCancel ? (
        <div className="progress-actions">
          <button className="button danger" onClick={onCancel} disabled={cancelBusy || status === "cancelling"}>
            {cancelBusy || status === "cancelling" ? <Loader2 size={16} /> : <XCircle size={16} />}
            {status === "cancelling" ? "正在取消" : "取消评测"}
          </button>
          <span className="panel-caption">取消后会停止后续任务；如果当前正在等待模型返回，会在该次调用结束后退出。</span>
        </div>
      ) : null}
    </section>
  );
}

function TaskInstructionPreview({
  preview,
  analyzing,
  selectedKeys,
  onSelectionChange
}: {
  preview: JsonObject;
  analyzing: boolean;
  selectedKeys: string[];
  onSelectionChange: (keys: string[]) => void;
}) {
  const items = preview.items || [];
  const [selectedItem, setSelectedItem] = useState<JsonObject | null>(null);
  const [renderMarkdown, setRenderMarkdown] = useState(true);
  function openTaskInstruction(item: JsonObject) {
    setSelectedItem(item);
    setRenderMarkdown(true);
  }
  function toggleTaskInstruction(item: JsonObject, index: number, checked: boolean) {
    const key = taskInstructionKey(item, index);
    const nextKeys = selectedKeys.filter((itemKey) => itemKey !== key);
    if (checked) nextKeys.push(key);
    onSelectionChange(nextKeys);
  }
  if (analyzing) {
    return (
      <div className="task-preview">
        <div className="task-preview-head">
          <strong>正在识别任务指令</strong>
          <span><Loader2 size={14} /> 解析中</span>
        </div>
      </div>
    );
  }
  if (!preview.count && !items.length) return null;
  return (
    <div className="task-preview">
      <div className="task-preview-head">
        <strong>任务指令</strong>
        <span>{preview.source_type || "文件"} · 已选 {selectedKeys.length}/{preview.count || items.length} 条</span>
      </div>
      <div className="task-tab-list">
        {items.map((item: JsonObject, index: number) => {
          const key = taskInstructionKey(item, index);
          return (
            <div className="task-tab" key={key}>
              <label className="task-checkbox" title="选择后参与评测">
                <input
                  type="checkbox"
                  checked={selectedKeys.includes(key)}
                  onChange={(event) => toggleTaskInstruction(item, index, event.target.checked)}
                />
              </label>
              <button
                className="task-tab-main"
                onClick={() => openTaskInstruction(item)}
                type="button"
              >
                <span>第{index + 1}条</span>
                <strong>{oneLineTaskSummary(item, index)}</strong>
              </button>
            </div>
          );
        })}
      </div>
      {selectedItem ? (
        <div className="task-modal-backdrop" onClick={() => setSelectedItem(null)}>
          <div className="task-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="task-modal-head">
              <div>
                <div className="panel-caption">任务指令详情</div>
                <h2>{oneLineTaskSummary(selectedItem, items.indexOf(selectedItem))}</h2>
              </div>
              <div className="task-modal-actions">
                <label className="render-toggle">
                  <input type="checkbox" checked={renderMarkdown} onChange={(event) => setRenderMarkdown(event.target.checked)} />
                  渲染 MD
                </label>
                <button className="button ghost" onClick={() => setSelectedItem(null)} type="button">
                  关闭
                </button>
              </div>
            </div>
            {renderMarkdown ? (
              <MarkdownContent content={selectedItem.content || selectedItem.preview || "暂无内容"} />
            ) : (
              <pre className="task-modal-content">{selectedItem.content || selectedItem.preview || "暂无内容"}</pre>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

type MarkdownBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "ordered"; marker: string; text: string }
  | { type: "bullet"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "paragraph"; text: string };

function MarkdownContent({ content }: { content: string }) {
  const blocks = markdownBlocks(content);
  return (
    <div className="markdown-rendered">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          if (block.level <= 2) return <h2 key={index}>{renderInlineMarkdown(block.text)}</h2>;
          if (block.level === 3) return <h3 key={index}>{renderInlineMarkdown(block.text)}</h3>;
          return <h4 key={index}>{renderInlineMarkdown(block.text)}</h4>;
        }
        if (block.type === "ordered") {
          return (
            <div className="md-list-row" key={index}>
              <span>{block.marker}</span>
              <p>{renderInlineMarkdown(block.text)}</p>
            </div>
          );
        }
        if (block.type === "bullet") {
          return (
            <div className="md-list-row" key={index}>
              <span>•</span>
              <p>{renderInlineMarkdown(block.text)}</p>
            </div>
          );
        }
        if (block.type === "table") {
          return (
            <div className="md-table-wrap" key={index}>
              <table className="md-table">
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th key={`${header}-${headerIndex}`}>{renderInlineMarkdown(header)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {block.headers.map((_, cellIndex) => (
                        <td key={cellIndex}>{renderInlineMarkdown(row[cellIndex] || "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function markdownBlocks(content: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = splitLines(content);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (isMarkdownTableRow(trimmed)) {
      const tableLines = [trimmed];
      let nextIndex = index + 1;
      while (nextIndex < lines.length && isMarkdownTableRow(lines[nextIndex].trim())) {
        tableLines.push(lines[nextIndex].trim());
        nextIndex += 1;
      }
      const table = markdownTableBlock(tableLines);
      if (table) {
        blocks.push(table);
        index = nextIndex - 1;
        continue;
      }
    }
    if (trimmed.startsWith("#")) {
      const level = headingLevel(trimmed);
      blocks.push({ type: "heading", level, text: trimmed.slice(level).trim() });
      continue;
    }
    const ordered = orderedListItem(trimmed);
    if (ordered) {
      blocks.push({ type: "ordered", marker: ordered.marker, text: ordered.text });
      continue;
    }
    if (trimmed.startsWith("- ")) {
      blocks.push({ type: "bullet", text: trimmed.slice(2).trim() });
      continue;
    }
    blocks.push({ type: "paragraph", text: trimmed });
  }
  return blocks;
}

function isMarkdownTableRow(text: string) {
  return text.startsWith("|") && text.endsWith("|") && text.slice(1, -1).includes("|");
}

function markdownTableBlock(lines: string[]): MarkdownBlock | null {
  if (lines.length < 2 || !isTableSeparatorRow(lines[1])) return null;
  const headers = splitTableRow(lines[0]);
  const rows = lines.slice(2).filter((line) => !isTableSeparatorRow(line)).map(splitTableRow);
  return { type: "table", headers, rows };
}

function splitTableRow(line: string) {
  return line
    .slice(1, -1)
    .split("|")
    .map((cell) => cell.trim());
}

function isTableSeparatorRow(line: string) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => {
    const chars = Array.from(cell.trim());
    return chars.length > 0 && chars.every((char) => char === "-" || char === ":" || char === " ");
  });
}

function headingLevel(text: string) {
  let level = 0;
  for (const char of text) {
    if (char !== "#") break;
    level += 1;
  }
  return level || 1;
}

function orderedListItem(text: string) {
  const dotIndex = text.indexOf(".");
  if (dotIndex <= 0) return null;
  const marker = text.slice(0, dotIndex);
  if (!Array.from(marker).every((char) => char >= "0" && char <= "9")) return null;
  const rest = text.slice(dotIndex + 1).trim();
  if (!rest) return null;
  return { marker: `${marker}.`, text: rest };
}

function renderInlineMarkdown(text: string) {
  const nodes: ReactNode[] = [];
  let index = 0;
  let key = 0;
  while (index < text.length) {
    const start = text.indexOf("**", index);
    if (start < 0) {
      nodes.push(text.slice(index));
      break;
    }
    if (start > index) nodes.push(text.slice(index, start));
    const end = text.indexOf("**", start + 2);
    if (end < 0) {
      nodes.push(text.slice(start));
      break;
    }
    nodes.push(<strong key={key}>{text.slice(start + 2, end)}</strong>);
    key += 1;
    index = end + 2;
  }
  return nodes;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Chip({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}

function ScoreChip({ score, passed }: { score: any; passed?: boolean }) {
  const tone = passed === false ? "red" : scoreTone(score);
  return <Chip tone={tone}>{display(score)}</Chip>;
}

function Progress({ value, max }: { value: number; max: number }) {
  const width = max ? Math.max(0, Math.min(100, (Number(value) / Number(max)) * 100)) : 0;
  return (
    <div className="progress">
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

function DataTable({ rows, columns }: { rows: JsonObject[]; columns: Array<[string, string]> }) {
  if (!rows.length) return <Empty text="暂无数据。" />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([, label]) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id || row.run_id || row.scene_id || row.dataset_id || row.experiment_id || index}>
              {columns.map(([key]) => (
                <td key={key}>{formatCell(row[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function uploadFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiJson("/files/upload", {
    method: "POST",
    body: form
  });
}

async function apiJson(path: string, init?: RequestInit) {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  return response.json();
}

async function apiText(path: string) {
  const response = await fetch(`/api/backend${path}`, { cache: "no-store" });
  if (!response.ok) return "";
  return response.text();
}

function jsonHeaders() {
  return {
    "Content-Type": "application/json"
  };
}

async function responseError(response: Response) {
  try {
    const data = await response.json();
    return data.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

function parseJsonl(text: string) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean) as JsonObject[];
}

function formatCell(value: any) {
  if (Array.isArray(value)) {
    if (!value.length) return "-";
    return value.join(", ");
  }
  if (typeof value === "boolean") {
    return value ? <Chip tone="green">是</Chip> : <Chip tone="red">否</Chip>;
  }
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 80)}...` : text;
}

function display(value: any) {
  if (value === null || value === undefined || value === "") return "-";
  return value;
}

function scoreTone(score: any) {
  if (typeof score !== "number") return "";
  if (score >= 80) return "green";
  if (score >= 60) return "amber";
  return "red";
}

function passRate(run: JsonObject) {
  const total = Number(run.evaluation_count || run.case_count || 0);
  const passed = Number(run.passed_count || 0);
  if (!total) return "-";
  return `${Math.round((passed / total) * 100)}%`;
}

function runLabel(run: JsonObject) {
  return run.run_display_name || run.scene_name || run.run_id || "";
}

function annotationRunLabel(run: JsonObject) {
  const parts = [
    runLabel(run),
    run.run_display_time || "",
    `${run.case_count || 0} case`
  ].filter(Boolean);
  return parts.join(" · ");
}

function firstNumeric(values: any[]) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function rawRecordTitle(row: JsonObject, index: number) {
  if (row.case_id) return `${index + 1}. ${row.case_id}`;
  if (row.task_name || row.role) return `${index + 1}. ${[row.task_name, row.role, row.model].filter(Boolean).join(" · ")}`;
  if (row.scene_id) return `${index + 1}. ${row.scene_id}`;
  return `第 ${index + 1} 条记录`;
}

function collectPhoenixDatasetResults(result: JsonObject) {
  const results: JsonObject[] = [];
  for (const asset of result.assets || []) {
    if (asset.phoenix_case_seed_dataset) results.push(asset.phoenix_case_seed_dataset);
  }
  for (const run of result.runs || []) {
    if (run.phoenix_case_seed_dataset) results.push(run.phoenix_case_seed_dataset);
    if (run.phoenix_generated_dialogue_dataset) results.push(run.phoenix_generated_dialogue_dataset);
  }
  return results.filter(Boolean);
}

function progressDetailText(job: JsonObject) {
  const details = job.details || {};
  const sceneIndex = Number(details.scene_index || 0);
  const sceneCount = Number(details.scene_count || 0);
  const taskIndex = Number(details.task_index || 0);
  const taskCount = Number(details.task_count || 0);
  const caseCount = Number(details.case_count || details.target_case_count || 0);
  const completedCaseCount = Number(details.completed_case_count ?? details.generated_count ?? 0);
  const generatedCount = Number(details.generated_count || 0);
  const caseStart = Number(details.case_range_start || 0);
  const caseEnd = Number(details.case_range_end || 0);
  const caseIndex = Number(details.case_index || 0);
  if (sceneIndex && sceneCount && caseCount) {
    const sceneText = `第 ${sceneIndex}/${sceneCount} 个场景`;
    if (completedCaseCount || completedCaseCount === 0) {
      const runningText = caseIndex && completedCaseCount < caseCount ? `，正在第 ${caseIndex}/${caseCount} 条` : "";
      return `${sceneText}，已完成 ${completedCaseCount}/${caseCount} 条对话${runningText}`;
    }
    if (caseIndex) {
      return `${sceneText}，第 ${caseIndex}/${caseCount} 条对话`;
    }
    return sceneText;
  }
  if (taskIndex && taskCount && caseCount && caseStart && caseEnd) {
    const caseText = caseStart === caseEnd ? `第 ${caseStart}/${caseCount} 个 case` : `第 ${caseStart}-${caseEnd}/${caseCount} 个 case`;
    return `第 ${taskIndex}/${taskCount} 条任务指令，${caseText}`;
  }
  if (taskIndex && taskCount && caseCount && caseIndex) {
    return `第 ${taskIndex}/${taskCount} 条任务指令，第 ${caseIndex}/${caseCount} 个 case`;
  }
  if (taskIndex && taskCount && caseCount) {
    const assetPhase = String(details.asset_phase || "");
    if (assetPhase === "case_cards") {
      return `第 ${taskIndex}/${taskCount} 条任务指令，已生成 ${generatedCount}/${caseCount} 个测试 case`;
    }
    return `第 ${taskIndex}/${taskCount} 条任务指令，计划生成 ${caseCount} 条对话，当前处于测试设计阶段`;
  }
  if (taskIndex && taskCount) {
    return `第 ${taskIndex}/${taskCount} 条任务指令`;
  }
  if (caseCount && caseIndex) {
    return `第 ${caseIndex}/${caseCount} 个 case`;
  }
  return "";
}

function progressCounters(job: JsonObject) {
  const details = job.details || {};
  const counters: Array<{ label: string; value: string; note: string }> = [];
  const taskIndex = Number(details.task_index || 0);
  const taskCount = Number(details.task_count || 0);
  const sceneIndex = Number(details.scene_index || 0);
  const sceneCount = Number(details.scene_count || 0);
  const caseCount = Number(details.case_count || details.target_case_count || 0);
  const generatedCount = Math.max(0, Number(details.generated_count || 0));
  const completedCaseCount = Math.max(0, Number(details.completed_case_count ?? 0));
  const caseIndex = Number(details.case_index || 0);
  const concurrency = Number(details.conversation_concurrency || 0);
  const runningCaseCount = Number(details.running_case_count || 0);
  const assetPhase = String(details.asset_phase || "");

  if (sceneIndex && sceneCount) {
    counters.push({
      label: "当前场景",
      value: `${sceneIndex}/${sceneCount}`,
      note: String(details.scene_name || details.scene_id || "")
    });
  } else if (taskIndex && taskCount) {
    counters.push({
      label: "任务指令",
      value: `${taskIndex}/${taskCount}`,
      note: String(details.current_eval_standard_path || "")
    });
  }

  if (caseCount) {
    if (sceneIndex && sceneCount) {
      counters.push({
        label: "对话生成",
        value: `${Math.min(completedCaseCount, caseCount)}/${caseCount}`,
        note: caseIndex && completedCaseCount < caseCount ? `正在第 ${caseIndex}/${caseCount} 条` : completedCaseCount >= caseCount ? "已完成" : "准备中"
      });
    } else if (assetPhase === "case_cards") {
      counters.push({
        label: "测试用例",
        value: `${Math.min(generatedCount, caseCount)}/${caseCount}`,
        note: "正在生成 case card"
      });
      counters.push({
        label: "对话生成",
        value: `0/${caseCount}`,
        note: "待测试设计完成后开始"
      });
    } else {
      counters.push({
        label: "计划对话",
        value: `0/${caseCount}`,
        note: "测试设计阶段，尚未开始"
      });
    }
  }

  if (concurrency) {
    counters.push({
      label: "并发数",
      value: `${concurrency}`,
      note: runningCaseCount ? `运行中 ${runningCaseCount}` : "当前设置"
    });
  }

  return counters;
}

function evidenceText(evidence: any) {
  if (!Array.isArray(evidence)) return String(evidence || "");
  return evidence
    .slice(0, 2)
    .map((item) => {
      if (typeof item === "string") return item;
      const turn = item.turn_index !== undefined && item.turn_index !== null ? `第${item.turn_index}轮` : "";
      return [turn, item.quote, item.explanation].filter(Boolean).join("：");
    })
    .join("；");
}

async function copyText(text: string) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard is best-effort; the raw text remains visible in the page.
  }
}

function taskInstructionKey(item: JsonObject, index: number) {
  return String(item.output_path || `${item.source_row || index + 1}:${item.title || ""}`);
}

function taskRunConfigPayload(item: JsonObject, index: number, configs: Record<string, TaskConfigState>) {
  const key = taskInstructionKey(item, index);
  const config = configs[key] || {};
  const payload: JsonObject = {
    eval_standard_path: item.output_path
  };
  const assetOutput = (config.assetOutput || "").trim();
  const runOutput = (config.runOutput || "").trim();
  const limit = taskConfigLimitValue(config);
  if (assetOutput) payload.asset_output_root = assetOutput;
  if (runOutput) payload.run_output_root = runOutput;
  if (limit !== null) {
    payload.limit = limit;
    if (limit > 0) payload.target_case_count = limit;
  }
  const hasOverrides = Boolean(assetOutput || runOutput || limit !== null);
  return hasOverrides && item.output_path ? payload : null;
}

function taskConfigValidationError(config?: TaskConfigState) {
  const rawLimit = (config?.limit || "").trim();
  if (!rawLimit) return "";
  const valid = Array.from(rawLimit).every((char) => char >= "0" && char <= "9");
  return valid ? "" : "每条任务的 case 数量只能输入非负整数。";
}

function taskConfigLimitValue(config?: TaskConfigState) {
  const rawLimit = (config?.limit || "").trim();
  if (!rawLimit) return null;
  return Number(rawLimit);
}

function oneLineTaskSummary(item: JsonObject, index: number) {
  return (item.task_summary || summarizeTaskInstruction(item.content || item.preview || "", item.title || `任务${index + 1}`)).slice(0, 10);
}

function summarizeTaskInstruction(text: string, fallback = "") {
  const task = taskTextFromMarkdown(text);
  const source = task || fallback || firstNonEmptyLine(text);
  const semantic = semanticTaskTitle(source);
  if (semantic) return semantic.slice(0, 10);
  return compactChineseSummary(source || text);
}

function taskTextFromMarkdown(text: string) {
  const lines = splitLines(text);
  for (let index = 0; index < lines.length; index += 1) {
    const stripped = lines[index].trim();
    if (!stripped.startsWith("#")) continue;
    const heading = stripMarkdownHeading(stripped);
    const headingLower = heading.toLowerCase();
    if (!headingLower.startsWith("task") && !heading.startsWith("任务")) continue;
    const inlineValue = valueAfterDelimiter(heading);
    if (inlineValue) return inlineValue;
    const collected: string[] = [];
    for (const nextLine of lines.slice(index + 1)) {
      const candidate = nextLine.trim();
      if (candidate.startsWith("#") && collected.length) break;
      if (candidate) collected.push(candidate);
    }
    if (collected.length) return collected.join(" ");
  }
  return "";
}

function valueAfterDelimiter(text: string) {
  for (const delimiter of [":", "："]) {
    if (text.includes(delimiter)) return text.split(delimiter).slice(1).join(delimiter).trim();
  }
  return "";
}

function firstNonEmptyLine(text: string) {
  for (const line of splitLines(text)) {
    const candidate = line.trim();
    if (candidate) return stripMarkdownHeading(candidate);
  }
  return "";
}

function splitLines(text: string) {
  return text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
}

function stripMarkdownHeading(text: string) {
  let value = text.trim();
  while (value.startsWith("#")) {
    value = value.slice(1).trim();
  }
  return value;
}

function semanticTaskTitle(text: string) {
  if (text.includes("直播") && (text.includes("升级") || text.includes("新增") || text.includes("选项"))) {
    return text.includes("课程") ? "课程直播升级" : "直播选项升级";
  }
  if (text.includes("飞毛腿") && text.includes("合同")) return "飞毛腿合同通知";
  if (text.includes("合同") && (text.includes("签署") || text.includes("生效"))) return "合同生效通知";
  if (text.includes("配送") && (text.includes("提醒") || text.includes("任务"))) return "配送任务提醒";
  return "";
}

function compactChineseSummary(text: string) {
  let value = text.trim();
  for (const phrase of ["角色", "任务", "你是", "请", "需要", "进行", "完成", "致电", "告知", "通知", "提醒", "他们", "客户", "用户", "商家", "老板", "骑手", "今天", "将"]) {
    value = value.split(phrase).join("");
  }
  const chars = Array.from(value).filter((char) => char >= "\u4e00" && char <= "\u9fff").join("");
  return (chars || "任务指令").slice(0, 10);
}

function isTabularFile(filename: string) {
  const lower = filename.toLowerCase();
  return [".csv", ".xlsx", ".xlsm", ".xltx", ".xltm"].some((suffix) => lower.endsWith(suffix));
}

function compactPreview(text: string, maxChars = 420) {
  const value = text.trim();
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars).trimEnd()}...`;
}

function annotationIsComplete(annotation: any) {
  if (!annotation || typeof annotation !== "object") return false;
  return annotation.review_complete ?? true;
}

const caseValidityOptions = [
  { value: "unreviewed", label: "未判断" },
  { value: "valid", label: "有效样本" },
  { value: "partial", label: "部分有效" },
  { value: "invalid", label: "无效样本" },
  { value: "expression_only", label: "仅表达质量" }
];

const validityCheckStatusOptions = [
  { value: "unreviewed", label: "未判断" },
  { value: "pass", label: "通过" },
  { value: "partial", label: "可疑/部分" },
  { value: "fail", label: "不通过" },
  { value: "not_applicable", label: "不适用" }
];

const validityCheckDefinitions = [
  {
    check_id: "natural_closure",
    label: "自然结束",
    description: "最后 1-2 轮是否形成真实电话里的闭环，而不是系统突然停掉。"
  },
  {
    check_id: "user_issue_resolved",
    label: "用户问题闭环",
    description: "用户提出的问题、疑虑或 private goal 是否已经被处理，至少客服有机会回应。"
  },
  {
    check_id: "stop_reason_valid",
    label: "停止原因合理",
    description: "不是因为单个低价值 coverage label 触发就提前结束。"
  },
  {
    check_id: "not_hard_stopped",
    label: "没有硬停",
    description: "不是 max_turns 机械截断；若是 max_turns，需要判断是否仍可作为部分有效样本。"
  },
  {
    check_id: "target_design_sufficient",
    label: "测试目标充分",
    description: "planned targets 是否足以测试任务/流程/知识/合规能力，而不只是表达质量。"
  }
];

const targetStatusOptions = [
  { value: "unreviewed", label: "未判断" },
  { value: "satisfied", label: "满足" },
  { value: "partial", label: "部分满足" },
  { value: "missing", label: "未满足" },
  { value: "not_applicable", label: "不适用" }
];

const dimensionCheckStatusOptions = [
  { value: "unreviewed", label: "未判断" },
  { value: "not_triggered", label: "未触发扣分" },
  { value: "partial", label: "部分触发" },
  { value: "triggered", label: "已触发扣分" },
  { value: "not_applicable", label: "不适用" }
];

function targetStatusLabel(status: string) {
  return targetStatusOptions.find((item) => item.value === status)?.label || "未判断";
}

function dimensionCheckStatusLabel(status: string) {
  return dimensionCheckStatusOptions.find((item) => item.value === status)?.label || "未判断";
}

function validityCheckStatusLabel(status: string) {
  return validityCheckStatusOptions.find((item) => item.value === status)?.label || "未判断";
}

function caseValidityLabel(status: string) {
  return caseValidityOptions.find((item) => item.value === status)?.label || "未判断";
}

function validityStatusTone(status: string) {
  if (status === "pass" || status === "valid") return "green";
  if (status === "partial" || status === "expression_only") return "amber";
  if (status === "fail" || status === "invalid") return "red";
  return "";
}

function validityCheckDescription(checkId: string) {
  return validityCheckDefinitions.find((item) => item.check_id === checkId)?.description || "";
}

function defaultValidityChecks(currentCase: JsonObject) {
  return validityCheckDefinitions.map((item) => ({
    ...item,
    status: "unreviewed",
    turn_index: null,
    evidence: ""
  }));
}

function suggestedValidityReview(currentCase: JsonObject) {
  const hints = currentCase.validity_hints || {};
  const checks: Record<string, string> = {
    natural_closure: hints.last_user_has_question || hints.premature_coverage_complete ? "fail" : "pass",
    user_issue_resolved: hints.last_user_has_question ? "fail" : "pass",
    stop_reason_valid: hints.premature_coverage_complete ? "fail" : hints.coverage_complete_stop ? "partial" : "pass",
    not_hard_stopped: hints.max_turns_stop ? "partial" : "pass",
    target_design_sufficient: hints.low_value_only_targets ? "fail" : Number(hints.target_count || 0) < 2 ? "partial" : "pass"
  };
  const values = Object.values(checks);
  const case_validity = hints.low_value_only_targets
    ? "expression_only"
    : values.includes("fail")
      ? "invalid"
      : values.includes("partial")
        ? "partial"
        : "valid";
  return { case_validity, checks };
}

function validityHintText(checkId: string, currentCase: JsonObject) {
  const hints = currentCase.validity_hints || {};
  if (checkId === "natural_closure") {
    return hints.last_user_has_question
      ? `最后用户仍在提问：${hints.last_user_text || ""}`
      : `结束原因：${hints.end_reason || "无"}；最后一轮角色：${hints.last_turn_role || "未知"}`;
  }
  if (checkId === "user_issue_resolved") {
    return `用户目标：${hints.private_goal || "无"}；未知事实：${(hints.unknown_facts || []).join("、") || "无"}`;
  }
  if (checkId === "stop_reason_valid") {
    return hints.premature_coverage_complete
      ? `疑似提前停止：${hints.end_reason || ""}；低价值目标：${(hints.low_value_targets || []).join("、") || "无"}`
      : `停止原因：${hints.end_reason || "无"}`;
  }
  if (checkId === "not_hard_stopped") {
    return hints.max_turns_stop ? "end_reason=max_turns，需要人工判断是否仍能评分。" : "未检测到 max_turns 硬停。";
  }
  if (checkId === "target_design_sufficient") {
    return `planned target ${hints.target_count ?? 0} 个，高价值目标 ${hints.high_value_target_count ?? 0} 个。`;
  }
  return "";
}

function defaultTargetChecks(currentCase: JsonObject, coveredTargets: string[] = []) {
  const covered = new Set(coveredTargets);
  return (currentCase.planned_targets || []).map((target: string) => ({
    target,
    status: covered.has(target) ? "satisfied" : "unreviewed",
    turn_index: null,
    evidence: ""
  }));
}

function defaultDimensionChecks(templates: JsonObject[], rubric: JsonObject) {
  if (templates.length) {
    return templates.map((item) => ({
      check_id: item.check_id,
      dimension_id: item.dimension_id,
      dimension_name: item.dimension_name || "",
      description: item.description || "",
      deduction: Number(item.deduction || 0),
      status: item.status || "unreviewed",
      turn_index: null,
      evidence: ""
    }));
  }
  return (rubric.dimensions || []).flatMap((dimension: JsonObject) => {
    const rules = dimension.deduction_rules?.length
      ? dimension.deduction_rules
      : [dimension.full_score_standard || dimension.description || dimension.name || dimension.dimension_id];
    const defaultDeduction = Number(dimension.weight || 0) / Math.max(rules.length, 1);
    return rules.map((rule: string, index: number) => ({
      check_id: `${dimension.dimension_id}__check_${String(index + 1).padStart(2, "0")}`,
      dimension_id: dimension.dimension_id,
      dimension_name: dimension.name || "",
      description: rule,
      deduction: deductionFromRuleText(rule) ?? defaultDeduction,
      status: "unreviewed",
      turn_index: null,
      evidence: ""
    }));
  });
}

function deductionFromRuleText(text: string) {
  const markerIndex = text.indexOf("扣");
  if (markerIndex < 0) return null;
  const chars: string[] = [];
  for (const char of text.slice(markerIndex + 1)) {
    if ((char >= "0" && char <= "9") || char === ".") {
      chars.push(char);
    } else if (chars.length) {
      break;
    }
  }
  if (!chars.length) return null;
  const value = Number(chars.join(""));
  return Number.isFinite(value) ? value : null;
}

function annotationTotals(form: JsonObject, rubric: JsonObject) {
  const checks = form.dimension_checks || [];
  const dimensionScores = (rubric.dimensions || []).map((dimension: JsonObject) => {
    const dimensionChecks = checks.filter((item: JsonObject) => item.dimension_id === dimension.dimension_id);
    const weight = Number(dimension.weight || 0);
    if (!dimensionChecks.length) {
      const legacy = (form.dimension_scores || []).find((item: JsonObject) => item.dimension_id === dimension.dimension_id);
      return {
        dimension_id: dimension.dimension_id,
        name: dimension.name,
        weight,
        score: Number(legacy?.score || 0)
      };
    }
    const deduction = dimensionChecks.reduce((total: number, item: JsonObject) => {
      const multiplier = item.status === "not_triggered" || item.status === "not_applicable"
        ? 0
        : item.status === "partial"
          ? 0.5
          : 1;
      return total + Number(item.deduction || 0) * multiplier;
    }, 0);
    return {
      dimension_id: dimension.dimension_id,
      name: dimension.name,
      weight,
      score: Math.max(0, Math.min(weight, weight - deduction))
    };
  });
  const rawScore = dimensionScores.reduce((total: number, item: JsonObject) => total + Number(item.score || 0), 0);
  const riskDeduction = (form.risk_flags || []).reduce((total: number, item: JsonObject) => total + Number(item.deduction || 0), 0);
  const totalScore = Math.max(0, Math.min(Number(rubric.total_score || 100), rawScore - riskDeduction));
  const passThreshold = Number(rubric.pass_threshold || 80);
  const vetoTriggered = Boolean((form.veto_items || []).length);
  const factChecks = [...(form.target_checks || []), ...checks];
  const reviewedFacts = factChecks.filter((item: JsonObject) => item.status && item.status !== "unreviewed").length;
  return {
    rawScore,
    riskDeduction,
    totalScore,
    dimensionScores,
    passThreshold,
    vetoTriggered,
    totalFacts: factChecks.length,
    reviewedFacts,
    reviewComplete: factChecks.length > 0 && reviewedFacts === factChecks.length,
    passed: totalScore >= passThreshold && !vetoTriggered
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
