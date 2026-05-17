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
  Database,
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
  UploadCloud,
  Workflow,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";

type PageKey = "workbench" | "new" | "reports" | "annotations" | "admin";
type JsonObject = Record<string, any>;
const sidebarStorageKey = "dialogue-eval-sidebar-collapsed";
const legacyTaskInputStorageKey = "dialogue-eval-task-input";

type TaskInputState = {
  fileName?: string;
  uploadedFile?: JsonObject | null;
  taskPreview?: JsonObject;
  selectedTaskKeys?: string[];
};

const navItems: Array<{ key: PageKey; label: string; icon: ReactNode }> = [
  { key: "workbench", label: "工作台", icon: <Gauge size={18} /> },
  { key: "new", label: "新建评测", icon: <Sparkles size={18} /> },
  { key: "reports", label: "评测报告", icon: <BarChart3 size={18} /> },
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
  const phoenixUrl = process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006";
  const evaluationRunning = Boolean(evaluationProgress?.job_id && ["queued", "running"].includes(String(evaluationProgress.status || "")));

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
    if (!jobId || !["queued", "running"].includes(status)) return;

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
          <Workbench health={health} assets={assets} runs={runs} registryStatus={registryStatus} />
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
        {page === "reports" ? <Reports runs={runs} initialRunId={reportRunId} /> : null}
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
  registryStatus
}: {
  health: JsonObject;
  assets: JsonObject[];
  runs: JsonObject[];
  registryStatus: JsonObject;
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
            <DataTable
              columns={[
                ["run_display_name", "运行"],
                ["case_count", "Case"],
                ["evaluation_count", "已评分"],
                ["passed_count", "通过"],
                ["average_score", "平均分"],
                ["risk_count", "风险"],
                ["veto_count", "否决"]
              ]}
              rows={runs.slice(0, 8)}
            />
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
  const [limit, setLimit] = useState("0");
  const [generatedAssets, setGeneratedAssets] = useState<JsonObject[]>([]);
  const [generatedRuns, setGeneratedRuns] = useState<JsonObject[]>([]);
  const [busy, setBusy] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState("");
  const uploadedFile = taskInputState.uploadedFile || null;
  const taskPreview = taskInputState.taskPreview || {};
  const taskItems = taskPreview.items || [];
  const selectedTaskKeys = taskInputState.selectedTaskKeys || [];
  const selectedTaskItems = taskItems.filter((item: JsonObject, index: number) => selectedTaskKeys.includes(taskInstructionKey(item, index)));
  const selectedEvalStandardPaths = selectedTaskItems.map((item: JsonObject) => item.output_path).filter(Boolean);
  const selectedEvalStandardPayload = taskItems.length ? selectedEvalStandardPaths : null;
  const selectedFileName = file?.name || taskInputState.fileName || "";
  const hasTaskInput = Boolean(file || uploadedFile);
  const taskSelectionError = taskItems.length > 0 && selectedTaskItems.length === 0 ? "请至少选择一条任务指令。" : "";
  const normalizedLimit = limit.trim();
  const caseLimitValid = normalizedLimit.length > 0 && Array.from(normalizedLimit).every((char) => char >= "0" && char <= "9");
  const caseLimitValue = caseLimitValid ? Number(normalizedLimit) : 0;
  const caseLimitError = caseLimitValid ? "" : "请输入非负整数，只能包含数字。";
  const completedEvaluationResult = evaluationProgress?.status === "completed" ? (evaluationProgress.result || {}) : {};
  const visibleGeneratedAssets = generatedAssets.length ? generatedAssets : (completedEvaluationResult.assets || []);
  const visibleGeneratedRuns = generatedRuns.length ? generatedRuns : (completedEvaluationResult.runs || []);

  function updateSelectedTaskKeys(nextKeys: string[]) {
    setTaskInputState({
      ...taskInputState,
      selectedTaskKeys: nextKeys
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
    if (caseLimitError) {
      setMessage("请先修正高级配置里的 case 数量。");
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
          limit: caseLimitValue > 0 ? caseLimitValue : null,
          skip_evaluation: skipEvaluation,
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
      {evaluationProgress ? <EvaluationProgress job={evaluationProgress} onOpenReport={onOpenReport} /> : null}

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
              disabled={busy === "evaluation" || evaluationRunning || analyzing || !hasTaskInput || Boolean(caseLimitError || taskSelectionError)}
            >
              {busy === "evaluation" || evaluationRunning ? <Loader2 size={16} /> : <PlayCircle size={16} />}
              {evaluationRunning ? "评测运行中" : "开始完整评测"}
            </button>
            <button className="button" onClick={generateAssetsOnly} disabled={busy === "asset" || evaluationRunning || analyzing || !hasTaskInput || Boolean(taskSelectionError)}>
              {busy === "asset" ? <Loader2 size={16} /> : <Boxes size={16} />}
              仅生成中间资产
            </button>
          </div>
        </section>

        <section className="panel">
          <PanelHeader title="高级配置" icon={<Settings size={18} />} />
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
            <Field label="case 数量">
              <input
                className={`input ${caseLimitError ? "invalid" : ""}`}
                inputMode="numeric"
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
                placeholder="0"
              />
              {caseLimitError ? <small className="field-error">{caseLimitError}</small> : <small>0 表示使用全部 case card</small>}
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
        </section>
      </div>
    </>
  );
}

function Reports({ runs, initialRunId = "" }: { runs: JsonObject[]; initialRunId?: string }) {
  const [selectedRun, setSelectedRun] = useState("");
  const [evaluations, setEvaluations] = useState<JsonObject[]>([]);
  const [conversations, setConversations] = useState<JsonObject[]>([]);
  const [selectedCase, setSelectedCase] = useState("");
  const [reportTab, setReportTab] = useState("overview");
  const [rawFile, setRawFile] = useState("conversation_log.jsonl");
  const [rawText, setRawText] = useState("");
  const [summaryText, setSummaryText] = useState("");
  const [scoreText, setScoreText] = useState("");
  const [message, setMessage] = useState("");
  const appliedInitialRunId = useRef("");

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

      {!runs.length ? (
        <Empty text="还没有运行记录。" />
      ) : !selectedRun ? (
        <section className="panel">
          <PanelHeader title="评测运行列表" icon={<BarChart3 size={18} />} />
          <RunList runs={runs} onOpen={openRun} />
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
              <a className="button" href={process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006"} target="_blank" rel="noreferrer">
                <Workflow size={16} />
                打开 Phoenix
              </a>
            </div>
          </section>

          <RunMetrics run={run} />
          {message ? <div className="message error">{message}</div> : null}

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
          ) : null}

          {reportTab === "cases" ? (
            <div className="grid two">
              <section className="panel">
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
            <div className="grid two">
              <section className="panel">
                <PanelHeader title="总评分报告" icon={<FileText size={18} />} />
                <pre className="markdown">{scoreText || "暂无评分报告。"}</pre>
              </section>
              <section className="panel">
                <PanelHeader title="覆盖报告" icon={<Activity size={18} />} />
                <pre className="markdown">{summaryText || "暂无覆盖报告。"}</pre>
              </section>
            </div>
          ) : null}

          {reportTab === "raw" ? (
            <section className="panel">
              <PanelHeader title="原始文件" icon={<FileText size={18} />} />
              <div className="toolbar" style={{ marginBottom: 12 }}>
                <select className="select" style={{ maxWidth: 260 }} value={rawFile} onChange={(event) => setRawFile(event.target.value)}>
                  {rawRunFiles.map(([file, label]) => (
                    <option key={file} value={file}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <pre className="code">{rawText}</pre>
            </section>
          ) : null}
        </>
      )}
    </>
  );
}

function RunList({ runs, onOpen }: { runs: JsonObject[]; onOpen: (runId: string) => void }) {
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
            <th>风险</th>
            <th>一票否决</th>
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
              <td>{run.risk_count || 0}</td>
              <td>{run.veto_count || 0}</td>
              <td>
                <button className="button ghost" onClick={(event) => {
                  event.stopPropagation();
                  onOpen(run.run_id);
                }}>
                  查看详情
                </button>
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
                <option key={run.run_id} value={run.run_id}>{runLabel(run)}</option>
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
  return (
    <section className="panel">
      <PanelHeader title="服务状态" icon={<Activity size={18} />} />
      <pre className="code">{JSON.stringify(health, null, 2)}</pre>
    </section>
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
        <Metric label="Base URL" value={status.phoenix_base_url || "-"} />
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
          ["prompt_hash", "输入 Hash"],
          ["success", "成功"]
        ]}
      />
    </section>
  );
}

function CaseDetail({ evaluation, conversation }: { evaluation: JsonObject; conversation: JsonObject }) {
  const turns = conversation.turns || [];
  const scores = evaluation.dimension_scores || [];
  return (
    <section className="panel">
      <PanelHeader title={evaluation.case_id || conversation.case_id || "Case 详情"} icon={<MessageSquareText size={18} />} />
      <div className="metric-grid" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <Metric label="总分" value={display(evaluation.total_score)} tone={scoreTone(evaluation.total_score)} />
        <Metric label="合格线" value={display(evaluation.pass_threshold)} />
        <Metric label="通过" value={evaluation.passed ? "是" : "否"} tone={evaluation.passed ? "green" : "red"} />
        <Metric label="风险扣分" value={display(evaluation.risk_deduction_total)} />
      </div>
      <div className="grid two">
        <div>
          <h3>原始对话</h3>
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
        </div>
        <div>
          <h3>评分维度</h3>
          <div className="grid">
            {scores.length ? (
              scores.map((score: JsonObject) => (
                <div key={score.dimension_id || score.name} className="panel" style={{ boxShadow: "none" }}>
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
        </div>
      </div>
    </section>
  );
}

function RunMetrics({ run }: { run: JsonObject }) {
  return (
    <div className="metric-grid">
      <Metric label="Case 数" value={run.case_count || 0} />
      <Metric label="已评分" value={run.evaluation_count || 0} />
      <Metric label="通过数" value={run.passed_count || 0} />
      <Metric label="平均分" value={display(run.average_score)} tone={scoreTone(run.average_score)} />
      <Metric label="风险数" value={run.risk_count || 0} tone={run.risk_count ? "red" : "green"} />
      <Metric label="一票否决" value={run.veto_count || 0} tone={run.veto_count ? "red" : "green"} />
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

function EvaluationProgress({ job, onOpenReport }: { job: JsonObject; onOpenReport?: (runId: string) => void }) {
  const steps = job.steps || [];
  const completedRuns = job.status === "completed" ? (job.result?.runs || []) : [];
  const completedRunId = completedRuns[0]?.run_id || "";
  return (
    <section className={`panel progress-panel ${job.status === "failed" ? "failed" : ""}`}>
      <div className="progress-head">
        <div>
          <div className="panel-title">{job.stage || "正在评测"}</div>
          <div className="panel-caption">{job.message || "后台任务正在执行。"}</div>
        </div>
        <Chip tone={job.status === "completed" ? "green" : job.status === "failed" ? "red" : ""}>
          {job.status === "completed" ? "已完成" : job.status === "failed" ? "失败" : "运行中"}
        </Chip>
      </div>
      <div className="progress-bar" aria-label="评测进度">
        <span style={{ width: `${Math.max(0, Math.min(100, Number(job.percent || 0)))}%` }} />
      </div>
      <div className="progress-meta">
        <span>{display(job.percent)}%</span>
        {job.details?.run_id ? <span>运行 {job.details.run_id}</span> : null}
        {job.details?.case_id ? <span>Case {job.details.case_id}</span> : null}
      </div>
      <div className="progress-steps">
        {steps.map((step: JsonObject) => (
          <div className={`progress-step ${step.status || "pending"}`} key={step.key}>
            <span className="progress-step-icon">
              {step.status === "completed" ? <CheckCircle2 size={15} /> : step.status === "in_progress" ? <Loader2 size={15} /> : step.status === "failed" ? <XCircle size={15} /> : null}
            </span>
            <span>{step.label}</span>
          </div>
        ))}
      </div>
      {completedRunId && onOpenReport ? (
        <div className="progress-actions">
          <button className="button primary" onClick={() => onOpenReport(completedRunId)}>
            <BarChart3 size={16} />
            查看评测结果
          </button>
          {completedRuns.length > 1 ? (
            <span className="panel-caption">本次生成 {completedRuns.length} 份报告，进入后可在报告中心切换查看。</span>
          ) : null}
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
        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function markdownBlocks(content: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  for (const line of splitLines(content)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
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

function taskInstructionKey(item: JsonObject, index: number) {
  return String(item.output_path || `${item.source_row || index + 1}:${item.title || ""}`);
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
