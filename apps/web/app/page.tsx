"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Boxes,
  CheckCircle2,
  ChevronLeft,
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
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";

type PageKey = "workbench" | "new" | "reports" | "assets" | "registry" | "settings";
type JsonObject = Record<string, any>;
const sidebarStorageKey = "dialogue-eval-sidebar-collapsed";

const navItems: Array<{ key: PageKey; label: string; icon: ReactNode }> = [
  { key: "workbench", label: "工作台", icon: <Gauge size={18} /> },
  { key: "new", label: "新建评测", icon: <Sparkles size={18} /> },
  { key: "reports", label: "报告中心", icon: <BarChart3 size={18} /> },
  { key: "assets", label: "场景资产", icon: <Layers3 size={18} /> },
  { key: "registry", label: "实验库", icon: <Database size={18} /> },
  { key: "settings", label: "系统设置", icon: <Settings size={18} /> }
];

const assetFiles = [
  ["scene_asset.yaml", "场景说明"],
  ["coverage_plan.yaml", "评测检查点"],
  ["user_profiles.yaml", "用户画像"],
  ["case_cards.yaml", "测试用例"],
  ["scoring_rubric.yaml", "评分规则"],
  ["materialized_eval_standard.md", "实例化任务标准"],
  ["variable_assignments.yaml", "变量替换记录"],
  ["asset_generation_report.md", "资产生成报告"]
];

const rawRunFiles = [
  ["conversation_log.jsonl", "对话记录"],
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
  const phoenixUrl = process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006";

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
    } catch {
      setSidebarCollapsed(false);
    }
  }, []);

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
              onClick={() => setPage(item.key)}
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
          <Workbench health={health} assets={assets} runs={runs} registryStatus={registryStatus} setPage={setPage} />
        ) : null}
        {page === "new" ? <NewEvaluation assets={assets} onDone={refresh} setPage={setPage} /> : null}
        {page === "reports" ? <Reports runs={runs} /> : null}
        {page === "assets" ? <AssetsCenter assets={assets} /> : null}
        {page === "registry" ? <RegistryCenter status={registryStatus} onRefresh={refresh} /> : null}
        {page === "settings" ? <SystemSettings health={health} runs={runs} onRefresh={refresh} /> : null}
      </main>
    </div>
  );
}

function Workbench({
  health,
  assets,
  runs,
  registryStatus,
  setPage
}: {
  health: JsonObject;
  assets: JsonObject[];
  runs: JsonObject[];
  registryStatus: JsonObject;
  setPage: (page: PageKey) => void;
}) {
  const latestRun = runs[0] || {};
  const latestPassRate = passRate(latestRun);
  return (
    <>
      <PageHeader
        eyebrow="Workbench"
        title="评测工作台"
        subtitle="围绕任务输入、评测运行、报告结论和 Trace 调试组织你的对话模型评测。"
        actions={
          <>
            <button className="button primary" onClick={() => setPage("new")}>
              <Sparkles size={16} />
              新建评测
            </button>
            <button className="button" onClick={() => setPage("reports")}>
              <FileText size={16} />
              查看报告
            </button>
          </>
        }
      />

      <div className="metric-grid">
        <Metric label="服务状态" value={health.status || "unknown"} />
        <Metric label="场景资产" value={assets.length} />
        <Metric label="运行记录" value={runs.length} />
        <Metric label="最近平均分" value={display(latestRun.average_score)} tone={scoreTone(latestRun.average_score)} />
        <Metric label="最近通过率" value={latestPassRate} />
        <Metric label="沉淀实验" value={registryStatus.experiments || 0} />
      </div>

      <div className="grid two">
        <section className="panel">
          <PanelHeader
            title="最近评测"
            caption="优先关注低分、高风险和一票否决的运行。"
            icon={<History size={18} />}
          />
          {runs.length ? (
            <DataTable
              columns={[
                ["run_id", "运行"],
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

        <section className="panel">
          <PanelHeader title="资产概览" caption="同一任务指令会复用资产版本。" icon={<Boxes size={18} />} />
          {assets.length ? (
            <DataTable
              columns={[
                ["scene_name", "场景"],
                ["scene_id", "标识"],
                ["case_count", "Case"],
                ["coverage_label_count", "检查点"]
              ]}
              rows={assets.slice(0, 8)}
            />
          ) : (
            <Empty text="还没有场景资产。" />
          )}
        </section>
      </div>
    </>
  );
}

function NewEvaluation({
  assets,
  onDone,
  setPage
}: {
  assets: JsonObject[];
  onDone: () => Promise<void>;
  setPage: (page: PageKey) => void;
}) {
  const validAssets = assets.filter((item) => item.valid);
  const [file, setFile] = useState<File | null>(null);
  const [businessConfig, setBusinessConfig] = useState("");
  const [generationPolicy, setGenerationPolicy] = useState("configs/generation_policy.yaml");
  const [modelConfig, setModelConfig] = useState("configs/model_config.yaml");
  const [assetOutput, setAssetOutput] = useState("outputs/assets");
  const [runOutput, setRunOutput] = useState("outputs/runs");
  const [fakeAsset, setFakeAsset] = useState(false);
  const [fakeRun, setFakeRun] = useState(false);
  const [skipEvaluation, setSkipEvaluation] = useState(false);
  const [limit, setLimit] = useState(0);
  const [generatedAssets, setGeneratedAssets] = useState<JsonObject[]>([]);
  const [selectedScene, setSelectedScene] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  const sceneOptions = useMemo(() => {
    const merged = [...generatedAssets, ...validAssets];
    const seen = new Set<string>();
    return merged.filter((item) => {
      if (!item.scene_id || seen.has(item.scene_id)) return false;
      seen.add(item.scene_id);
      return true;
    });
  }, [generatedAssets, validAssets]);

  useEffect(() => {
    if (!selectedScene && sceneOptions.length) {
      setSelectedScene(sceneOptions[0].scene_id);
    }
  }, [sceneOptions, selectedScene]);

  async function generateAssets() {
    if (!file) {
      setMessage("请先上传 Markdown、CSV 或 Excel 任务文件。");
      return;
    }
    setBusy("asset");
    setMessage("");
    try {
      const uploaded = await uploadFile(file);
      const result = await apiJson("/assets/generate", {
        method: "POST",
        body: JSON.stringify({
          eval_standard_file_path: uploaded.path,
          business_config_path: businessConfig || null,
          generation_policy_path: generationPolicy,
          model_config_path: modelConfig,
          output_root: assetOutput,
          fake_llm: fakeAsset
        }),
        headers: jsonHeaders()
      });
      const nextAssets = result.assets || [];
      setGeneratedAssets(nextAssets);
      if (nextAssets[0]?.scene_id) setSelectedScene(nextAssets[0].scene_id);
      setMessage(`已生成或复用 ${result.count || 0} 个场景资产。`);
      await onDone();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function runEvaluation() {
    if (!selectedScene) {
      setMessage("请选择要运行的场景资产。");
      return;
    }
    setBusy("run");
    setMessage("");
    try {
      const result = await apiJson("/runs", {
        method: "POST",
        body: JSON.stringify({
          scene_id: selectedScene,
          business_config_path: businessConfig || null,
          model_config_path: modelConfig,
          output_root: runOutput,
          limit: limit > 0 ? limit : null,
          skip_evaluation: skipEvaluation,
          fake_llm: fakeRun
        }),
        headers: jsonHeaders()
      });
      setMessage(`评测完成：${result.run_id}`);
      await onDone();
      setPage("reports");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="New Evaluation"
        title="新建评测"
        subtitle="上传任务文件，生成或复用资产，然后运行用户模拟器和评分流程。"
      />

      <div className="steps">
        <Step index={1} title="任务输入" note={file ? file.name : "Markdown / CSV / Excel"} active={!file} complete={!!file} />
        <Step
          index={2}
          title="场景资产"
          note={generatedAssets.length ? `${generatedAssets.length} 个资产` : "生成或选择已有资产"}
          active={!!file && !generatedAssets.length}
          complete={!!selectedScene}
        />
        <Step index={3} title="运行评测" note={selectedScene || "选择 case 范围"} active={!!selectedScene} complete={false} />
      </div>

      {message ? <div className="message">{message}</div> : null}

      <div className="grid two">
        <section className="panel">
          <PanelHeader title="任务输入" caption="系统会自动识别 Markdown、CSV 或 Excel；CSV/Excel 默认读取第 2 列第 2 行之后。" icon={<UploadCloud size={18} />} />
          <label className="file-drop">
            <UploadCloud size={28} />
            <strong>{file ? file.name : "选择任务文件"}</strong>
            <span className="panel-caption">支持 .md, .csv, .xlsx</span>
            <input
              hidden
              type="file"
              accept=".md,.markdown,.csv,.xlsx,.xlsm,.xltx,.xltm"
              onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] || null)}
            />
          </label>

          <details style={{ marginTop: 14 }}>
            <summary>高级配置</summary>
            <div className="form-grid" style={{ marginTop: 12 }}>
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
            </div>
            <label className="chip" style={{ marginTop: 12 }}>
              <input type="checkbox" checked={fakeAsset} onChange={(event) => setFakeAsset(event.target.checked)} />
              资产生成使用 fake LLM
            </label>
          </details>

          <div className="actions" style={{ marginTop: 16 }}>
            <button className="button primary" onClick={generateAssets} disabled={busy === "asset"}>
              {busy === "asset" ? <Loader2 size={16} /> : <Sparkles size={16} />}
              生成场景资产
            </button>
          </div>
        </section>

        <section className="panel">
          <PanelHeader title="运行评测" caption="选择资产和 case 数量，启动客服模型、用户模型、judge 和评分流程。" icon={<PlayCircle size={18} />} />
          <div className="form-grid">
            <Field label="场景资产">
              <select className="select" value={selectedScene} onChange={(event) => setSelectedScene(event.target.value)}>
                {sceneOptions.map((asset) => (
                  <option key={asset.scene_id} value={asset.scene_id}>
                    {asset.scene_name || asset.scene_id}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="case 数量">
              <input className="input" type="number" min={0} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
              <small>0 表示全量</small>
            </Field>
            <Field label="运行输出目录">
              <input className="input" value={runOutput} onChange={(event) => setRunOutput(event.target.value)} />
            </Field>
            <Field label="评分">
              <label className="chip">
                <input type="checkbox" checked={skipEvaluation} onChange={(event) => setSkipEvaluation(event.target.checked)} />
                只跑对话
              </label>
            </Field>
          </div>
          <label className="chip" style={{ marginTop: 12 }}>
            <input type="checkbox" checked={fakeRun} onChange={(event) => setFakeRun(event.target.checked)} />
            运行使用 fake LLM
          </label>
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="button primary" onClick={runEvaluation} disabled={busy === "run" || !selectedScene}>
              {busy === "run" ? <Loader2 size={16} /> : <PlayCircle size={16} />}
              开始评测
            </button>
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <PanelHeader title="可用场景资产" caption="优先显示本次生成结果；也可直接运行历史资产。" icon={<Layers3 size={18} />} />
        {sceneOptions.length ? <AssetsTable assets={sceneOptions} /> : <Empty text="暂无可用资产。" />}
      </section>
    </>
  );
}

function Reports({ runs }: { runs: JsonObject[] }) {
  const [selectedRun, setSelectedRun] = useState(runs[0]?.run_id || "");
  const [evaluations, setEvaluations] = useState<JsonObject[]>([]);
  const [conversations, setConversations] = useState<JsonObject[]>([]);
  const [selectedCase, setSelectedCase] = useState("");
  const [reportTab, setReportTab] = useState("overview");
  const [rawFile, setRawFile] = useState("conversation_log.jsonl");
  const [rawText, setRawText] = useState("");
  const [summaryText, setSummaryText] = useState("");
  const [scoreText, setScoreText] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (runs[0]?.run_id && !selectedRun) setSelectedRun(runs[0].run_id);
  }, [runs, selectedRun]);

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

  return (
    <>
      <PageHeader
        eyebrow="Reports"
        title="报告中心"
        subtitle="从总分、通过率和风险进入 case 详情，查看原始对话和评分证据。"
      />

      {!runs.length ? (
        <Empty text="还没有运行记录。" />
      ) : (
        <>
          <section className="panel">
            <div className="form-grid">
              <Field label="运行记录">
                <select className="select" value={selectedRun} onChange={(event) => setSelectedRun(event.target.value)}>
                  {runs.map((item) => (
                    <option key={item.run_id} value={item.run_id}>
                      {item.run_id}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Trace">
                <a className="button" href={process.env.NEXT_PUBLIC_PHOENIX_UI_URL || "http://127.0.0.1:6006"} target="_blank" rel="noreferrer">
                  <Workflow size={16} />
                  打开 Phoenix
                </a>
              </Field>
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
                <PanelHeader title="Case 评分" caption="按总分和风险快速定位问题样本。" icon={<ClipboardList size={18} />} />
                {evaluations.length ? <CaseScoreTable evaluations={evaluations} onSelect={setSelectedCase} /> : <Empty text="没有评分结果。" />}
              </section>
              <section className="panel">
                <PanelHeader title="高频未覆盖检查点" caption="用于判断客服模型或任务资产需要补强的方向。" icon={<AlertTriangle size={18} />} />
                <MissingTargets evaluations={evaluations} />
              </section>
            </div>
          ) : null}

          {reportTab === "cases" ? (
            <div className="grid two">
              <section className="panel">
                <PanelHeader title="Case 列表" caption="点击左侧 case 查看详情。" icon={<MessageSquareText size={18} />} />
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
                <PanelHeader title="总评分报告" caption="由评分结果汇总生成。" icon={<FileText size={18} />} />
                <pre className="markdown">{scoreText || "暂无评分报告。"}</pre>
              </section>
              <section className="panel">
                <PanelHeader title="覆盖报告" caption="由对话覆盖情况汇总生成。" icon={<Activity size={18} />} />
                <pre className="markdown">{summaryText || "暂无覆盖报告。"}</pre>
              </section>
            </div>
          ) : null}

          {reportTab === "raw" ? (
            <section className="panel">
              <PanelHeader title="原始文件" caption="调试和审计时使用，默认不需要阅读。" icon={<FileText size={18} />} />
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

function AssetsCenter({ assets }: { assets: JsonObject[] }) {
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
      <PageHeader
        eyebrow="Assets"
        title="场景资产"
        subtitle="查看模型生成的场景说明、检查点、用户画像、测试用例和评分规则。"
      />
      <section className="panel">
        <PanelHeader title="资产列表" caption="资产按任务输入内容 hash 复用，避免同一任务生成多个场景。" icon={<Layers3 size={18} />} />
        {validAssets.length ? <AssetsTable assets={validAssets} /> : <Empty text="还没有可用资产。" />}
      </section>

      {validAssets.length ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <PanelHeader title="资产文件" caption="默认展示业务化名称，原始 YAML/Markdown 用于审计。" icon={<FileText size={18} />} />
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

function RegistryCenter({ status, onRefresh }: { status: JsonObject; onRefresh: () => Promise<void> }) {
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
      <PageHeader
        eyebrow="Registry"
        title="实验库"
        subtitle="DialogueEval 自己沉淀业务实验数据，Phoenix 负责 Trace 调试。"
        actions={
          <button className="button" onClick={indexExisting}>
            <RefreshCw size={16} />
            扫描已有 outputs
          </button>
        }
      />
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
          <PanelHeader title="Datasets" caption="上传的 Markdown、CSV 或 Excel 输入。" icon={<Database size={18} />} />
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
          <PanelHeader title="Experiments" caption="每次批量运行或单场景运行。" icon={<Workflow size={18} />} />
          <DataTable
            rows={experiments}
            columns={[
              ["experiment_id", "实验"],
              ["run_id", "运行"],
              ["scene_id", "场景"],
              ["status", "状态"],
              ["started_at", "开始"]
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
      <PageHeader
        eyebrow="Settings"
        title="系统设置"
        subtitle="Prompt、模型调用和服务状态放在这里，避免干扰普通评测流程。"
      />
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
      <PanelHeader title="Prompt 管理" caption="运行时默认优先从 Phoenix Prompts 读取。" icon={<ClipboardList size={18} />} />
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
      <PanelHeader title="模型调用" caption="只展示摘要字段，完整 prompt 不在页面铺开。" icon={<Activity size={18} />} />
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <select className="select" style={{ maxWidth: 420 }} value={runId} onChange={(event) => setRunId(event.target.value)}>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {run.run_id}
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
      <PanelHeader title={evaluation.case_id || conversation.case_id || "Case 详情"} caption="原始对话和评分证据并排查看。" icon={<MessageSquareText size={18} />} />
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

function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      {actions ? <div className="toolbar">{actions}</div> : null}
    </header>
  );
}

function PanelHeader({ title, caption, icon }: { title: string; caption?: string; icon?: ReactNode }) {
  return (
    <div className="panel-header">
      <div>
        <div className="panel-title">{title}</div>
        {caption ? <div className="panel-caption">{caption}</div> : null}
      </div>
      {icon ? <span className="chip">{icon}</span> : null}
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
