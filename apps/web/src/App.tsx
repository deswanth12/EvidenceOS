import React, { useEffect, useState } from 'react';
import { api } from './api';
import {
  AuditTrailResponse,
  CaseDetail,
  CaseSummary,
  DecisionOutcome,
  EvaluationReport,
  EvidenceItem,
} from './types';
import {
  EpistemicBadge,
  EvidenceInspectorDrawer,
  InteractiveEvidenceGraph,
  OutcomeBadge,
} from './components/EvidenceWidgets';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Clock,
  FilePlus2,
  FolderKanban,
  GitBranch,
  History,
  Layers,
  Play,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  Upload,
  UserCheck,
} from 'lucide-react';

type ActiveTab =
  | 'overview'
  | 'upload'
  | 'timeline'
  | 'graph'
  | 'conflicts'
  | 'decision'
  | 'audit'
  | 'evaluation'
  | 'create_case';

const GUIDED_STORY_STEPS: Array<{
  step: number;
  title: string;
  subtitle: string;
  tab: ActiveTab;
}> = [
  {
    step: 1,
    title: '1. Upload & Ingest',
    subtitle: 'SHA-256 + 64-bit dHash & Magic Byte Check',
    tab: 'overview',
  },
  {
    step: 2,
    title: '2. Investigate Claims',
    subtitle: 'Normalize PO, Challan, Photo & Voice',
    tab: 'timeline',
  },
  {
    step: 3,
    title: '3. Evidence Conflict',
    subtitle: 'Surface Cross-Modal Contradictions',
    tab: 'conflicts',
  },
  {
    step: 4,
    title: '4. Explain Provenance',
    subtitle: 'Trace DAG to Original Files',
    tab: 'graph',
  },
  {
    step: 5,
    title: '5. Deterministic Decision',
    subtitle: 'Evaluate SLA Rules & Human Review',
    tab: 'decision',
  },
];

export function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditTrailResponse | null>(null);
  const [evalReport, setEvalReport] = useState<EvaluationReport | null>(null);
  const [evalSuiteType, setEvalSuiteType] = useState<'heldout_150' | 'extended_60' | 'canonical_5'>('heldout_150');
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
  const [guidedStepIndex, setGuidedStepIndex] = useState<number>(0);
  const [inspectedEvidence, setInspectedEvidence] = useState<EvidenceItem | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Create Case form state
  const [newTitle, setNewTitle] = useState('');
  const [newPo, setNewPo] = useState('PO-2026-2050');
  const [newSupplier, setNewSupplier] = useState('Apex Industrial Components Ltd.');
  const [newBuyer, setNewBuyer] = useState('Vertex Logistics & Manufacturing Corp.');
  const [newDesc, setNewDesc] = useState('');

  // Upload Evidence state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadRole, setUploadRole] = useState<string>('');
  const [manualText, setManualText] = useState<string>('');
  const [manualRole, setManualRole] = useState<string>('voice_report');

  // Human Review Override state
  const [reviewerName, setReviewerName] = useState('senior_procurement_auditor');
  const [reviewOutcome, setReviewOutcome] = useState<DecisionOutcome>('partially_approved');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewAcceptedQty, setReviewAcceptedQty] = useState<number>(8);
  const [reviewDamagedQty, setReviewDamagedQty] = useState<number>(2);

  const loadCases = async (preferredId?: string) => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const list = await api.listCases();
      const sorted = [...list].sort((a, b) => a.id.localeCompare(b.id));
      setCases(sorted);
      const targetId =
        preferredId ||
        selectedCaseId ||
        sorted.find((c) => c.id === 'case_03_conflicting_evidence')?.id ||
        (sorted[0]?.id ?? '');
      if (targetId) {
        setSelectedCaseId(targetId);
        await loadCaseDetail(targetId);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load cases');
    } finally {
      setLoading(false);
    }
  };

  const loadCaseDetail = async (cid: string) => {
    try {
      const [detail, audit] = await Promise.all([
        api.getCaseDetail(cid),
        api.getAuditTrail(cid),
      ]);
      setCaseDetail(detail);
      setAuditTrail(audit);
      if (detail.latest_decision) {
        setReviewAcceptedQty(detail.latest_decision.accepted_quantity);
        setReviewDamagedQty(detail.latest_decision.verified_damaged_quantity);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load case details');
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleSelectCase = async (cid: string) => {
    setSelectedCaseId(cid);
    setInspectedEvidence(null);
    if (activeTab === 'create_case' || activeTab === 'evaluation') {
      setActiveTab('overview');
    }
    await loadCaseDetail(cid);
  };

  const handleInspectEvidenceById = (evId: string) => {
    if (!caseDetail) return;
    const found = caseDetail.evidence_items.find((e) => e.id === evId);
    if (found) {
      setInspectedEvidence(found);
    }
  };

  const handleGuidedStepClick = (idx: number) => {
    setGuidedStepIndex(idx);
    setActiveTab(GUIDED_STORY_STEPS[idx].tab);
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      setLoading(true);
      const created = await api.createCase({
        title: newTitle,
        po_number: newPo,
        supplier_name: newSupplier,
        buyer_name: newBuyer,
        description: newDesc,
      });
      setNewTitle('');
      setNewDesc('');
      await loadCases(created.id);
      setActiveTab('upload');
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !selectedCaseId) return;
    try {
      setLoading(true);
      await api.uploadEvidence(
        selectedCaseId,
        uploadFile,
        uploadRole || undefined
      );
      setUploadFile(null);
      await loadCaseDetail(selectedCaseId);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualText.trim() || !selectedCaseId) return;
    try {
      setLoading(true);
      await api.addManualEvidence(selectedCaseId, {
        filename: `${manualRole}_note.txt`,
        document_role: manualRole,
        text_content: manualText,
      });
      setManualText('');
      await loadCaseDetail(selectedCaseId);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunPipeline = async () => {
    if (!selectedCaseId) return;
    try {
      setLoading(true);
      await api.processCase(selectedCaseId);
      await loadCases(selectedCaseId);
      setActiveTab('overview');
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleHumanOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId || !reviewNotes.trim()) return;
    try {
      setLoading(true);
      await api.submitHumanReview(selectedCaseId, {
        outcome: reviewOutcome,
        reviewer: reviewerName,
        notes: reviewNotes,
        accepted_quantity: Number(reviewAcceptedQty),
        verified_damaged_quantity: Number(reviewDamagedQty),
      });
      setReviewNotes('');
      await loadCases(selectedCaseId);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async (
    suite: 'heldout_150' | 'extended_60' | 'canonical_5' = evalSuiteType
  ) => {
    try {
      setLoading(true);
      setEvalSuiteType(suite);
      const rep = await api.runEvaluation(suite);
      setEvalReport(rep);
      setActiveTab('evaluation');
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetDemoCases = async () => {
    try {
      setLoading(true);
      await api.seedDemoCases();
      await loadCases('case_03_conflicting_evidence');
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const checklist = caseDetail?.pipeline_checklist || {};
  const dec = caseDetail?.latest_decision;
  const ablation = evalReport?.ablation_comparison;

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100">
      {/* Top Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-30 px-6 py-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/40 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white text-base">
                EvidenceOS
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30 font-mono">
                VeriDock v0.3.0
              </span>
            </div>
            <p className="text-xs text-slate-400">
              AI Evidence Verification Engine for B2B Delivery & Procurement Disputes
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              handleSelectCase('case_03_conflicting_evidence');
              handleGuidedStepClick(0);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Launch Guided Flagship Demo (Case 3)</span>
          </button>
          <button
            onClick={() => setActiveTab('create_case')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 transition"
          >
            <FilePlus2 className="w-3.5 h-3.5 text-sky-400" />
            <span>New Case</span>
          </button>
          <button
            onClick={() => handleRunEvaluation('heldout_150')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 transition"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>150-Case Held-Out Evaluation</span>
          </button>
          <button
            onClick={handleResetDemoCases}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
            title="Re-seed all 5 canonical benchmark cases"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Reset Demo</span>
          </button>
        </div>
      </header>

      {errorMsg && (
        <div className="bg-rose-950/80 border-b border-rose-500/40 px-6 py-2.5 text-xs text-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button
            onClick={() => setErrorMsg(null)}
            className="text-rose-300 underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content Layout */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Sidebar: Case Switcher & Dashboard */}
        <aside className="w-full lg:w-80 border-r border-slate-800 bg-slate-950/50 flex flex-col shrink-0">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <FolderKanban className="w-3.5 h-3.5 text-sky-400" />
              Canonical Dispute Cases ({cases.length})
            </span>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
            {cases.map((c) => {
              const isSelected = c.id === selectedCaseId;
              return (
                <button
                  key={c.id}
                  onClick={() => handleSelectCase(c.id)}
                  className={`w-full text-left p-3.5 transition-colors ${
                    isSelected
                      ? 'bg-sky-500/10 border-l-2 border-l-sky-400'
                      : 'hover:bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-xs font-mono text-slate-400">
                      {c.po_number || c.id}
                    </span>
                    <OutcomeBadge outcome={c.latest_decision_outcome} />
                  </div>
                  <div className="text-xs font-semibold text-slate-100 line-clamp-2 mb-1.5">
                    {c.title}
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                    <span>Evidence: {c.evidence_count}</span>
                    {c.conflict_count > 0 && (
                      <span className="text-amber-400">
                        ⚠ {c.conflict_count} conflict{c.conflict_count > 1 ? 's' : ''}
                      </span>
                    )}
                    {c.historical_warning_count > 0 && (
                      <span className="text-rose-400">⚠ Reused Img</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Center Workspace */}
        <main className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Guided Investigation Story Bar (Upload -> Investigate -> Conflict -> Explain -> Decision) */}
          {caseDetail && activeTab !== 'create_case' && activeTab !== 'evaluation' && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono uppercase tracking-wider text-sky-400 font-semibold">
                  Interactive Investigation Flow: Upload → Investigate → Conflict → Explain → Decision
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      handleGuidedStepClick(
                        (guidedStepIndex + 1) % GUIDED_STORY_STEPS.length
                      )
                    }
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 text-xs font-semibold border border-sky-500/30 transition"
                  >
                    <span>Next Investigation Step</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
                {GUIDED_STORY_STEPS.map((s, idx) => {
                  const isCurrent = activeTab === s.tab;
                  return (
                    <button
                      key={s.step}
                      onClick={() => handleGuidedStepClick(idx)}
                      className={`text-left p-2.5 rounded-lg border transition ${
                        isCurrent
                          ? 'bg-sky-500/15 border-sky-400 text-white'
                          : 'bg-slate-950/70 border-slate-800/80 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="text-xs font-bold">{s.title}</div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">
                        {s.subtitle}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 'overview', label: '1. Case Overview & Status', icon: Layers },
                { id: 'upload', label: '2. Evidence Upload', icon: Upload },
                { id: 'timeline', label: '3. Evidence & Provenance', icon: Clock },
                { id: 'graph', label: '4. Evidence Graph', icon: GitBranch },
                { id: 'conflicts', label: '5. Conflict Analysis', icon: AlertTriangle },
                { id: 'decision', label: '6. Decision & Rules', icon: Scale },
                { id: 'audit', label: '7. Audit Trail', icon: History },
                { id: 'evaluation', label: '8. Research Benchmark & Ablations', icon: BarChart3 },
              ].map((t) => {
                const Icon = t.icon;
                const active = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      if (t.id === 'evaluation' && !evalReport) {
                        handleRunEvaluation('heldout_150');
                      } else {
                        setActiveTab(t.id as ActiveTab);
                      }
                    }}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                      active
                        ? 'bg-sky-500 text-slate-950 font-semibold shadow-sm'
                        : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{t.label}</span>
                  </button>
                );
              })}
            </div>

            {caseDetail && activeTab !== 'create_case' && activeTab !== 'evaluation' && (
              <button
                onClick={handleRunPipeline}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition shadow"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Re-Run Verification Pipeline</span>
              </button>
            )}
          </div>

          {/* Create Case Screen */}
          {activeTab === 'create_case' && (
            <div className="max-w-2xl bg-slate-900/70 border border-slate-800 rounded-xl p-6 space-y-4">
              <h2 className="text-base font-bold text-white">
                Create New B2B Delivery Dispute Case
              </h2>
              <form onSubmit={handleCreateCase} className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">
                    Case Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g., Shipment SHP-9020 Hydraulic Pump Dispute"
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-slate-300 mb-1 font-medium">
                      PO Number
                    </label>
                    <input
                      type="text"
                      value={newPo}
                      onChange={(e) => setNewPo(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 mb-1 font-medium">
                      Supplier Name
                    </label>
                    <input
                      type="text"
                      value={newSupplier}
                      onChange={(e) => setNewSupplier(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 mb-1 font-medium">
                      Buyer Name
                    </label>
                    <input
                      type="text"
                      value={newBuyer}
                      onChange={(e) => setNewBuyer(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">
                    Case Description
                  </label>
                  <textarea
                    rows={3}
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    placeholder="Describe the delivery discrepancy or procurement claim..."
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                  />
                </div>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold"
                >
                  Create Case & Proceed to Evidence Upload
                </button>
              </form>
            </div>
          )}

          {/* Evaluation & Ablation Screen */}
          {activeTab === 'evaluation' && (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/70 border border-slate-800 rounded-xl p-5">
                <div>
                  <h2 className="text-base font-bold text-white">
                    {evalReport?.benchmark_version || 'Empirical Multimodal Benchmark & Model Ablation'}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Evaluates {evalReport?.total_cases || 150} independent cases ({evalReport?.total_evidence_files || 564} binary PDF, PNG, and WAV files) with 95% Wilson confidence intervals, 4-system baselines, and 6-stage modality ablations.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => handleRunEvaluation('heldout_150')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      evalSuiteType === 'heldout_150'
                        ? 'bg-sky-500 text-slate-950 border-sky-400'
                        : 'bg-slate-950 text-slate-300 border-slate-800'
                    }`}
                  >
                    150-Case Blind Held-Out (N=150)
                  </button>
                  <button
                    onClick={() => handleRunEvaluation('extended_60')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      evalSuiteType === 'extended_60'
                        ? 'bg-sky-500 text-slate-950 border-sky-400'
                        : 'bg-slate-950 text-slate-300 border-slate-800'
                    }`}
                  >
                    60-Case Dev Suite (N=60)
                  </button>
                  <button
                    onClick={() => handleRunEvaluation('canonical_5')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      evalSuiteType === 'canonical_5'
                        ? 'bg-sky-500 text-slate-950 border-sky-400'
                        : 'bg-slate-950 text-slate-300 border-slate-800'
                    }`}
                  >
                    5-Case Canonical Regression (N=5)
                  </button>
                </div>
              </div>

              {evalReport && (
                <>
                  {/* Primary KPI Summary Strip with 95% Wilson CIs */}
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Decision Accuracy</div>
                      <div className="text-lg font-bold text-emerald-400 font-mono mt-1">
                        {(evalReport.metrics.decision_accuracy * 100).toFixed(1)}%
                      </div>
                      {evalReport.metrics.decision_accuracy_ci_95 && (
                        <div className="text-[10px] font-mono text-slate-400">
                          95% CI [{(evalReport.metrics.decision_accuracy_ci_95[0] * 100).toFixed(1)}%,{' '}
                          {(evalReport.metrics.decision_accuracy_ci_95[1] * 100).toFixed(1)}%]
                        </div>
                      )}
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Macro-F1</div>
                      <div className="text-lg font-bold text-sky-400 font-mono mt-1">
                        {(evalReport.metrics.macro_f1 ?? evalReport.metrics.decision_accuracy).toFixed(4)}
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">Unweighted 5-class F1</div>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Confident Error Rate</div>
                      <div className="text-lg font-bold text-emerald-400 font-mono mt-1">
                        {((evalReport.metrics.confident_error_rate ?? 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">Unsafe auto-payouts</div>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Field-Level Acc</div>
                      <div className="text-lg font-bold text-white font-mono mt-1">
                        {(evalReport.metrics.field_level_accuracy * 100).toFixed(1)}%
                      </div>
                      {evalReport.metrics.field_level_accuracy_ci_95 && (
                        <div className="text-[10px] font-mono text-slate-400">
                          95% CI [{(evalReport.metrics.field_level_accuracy_ci_95[0] * 100).toFixed(1)}%,{' '}
                          {(evalReport.metrics.field_level_accuracy_ci_95[1] * 100).toFixed(1)}%]
                        </div>
                      )}
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Conflict Precision / Recall</div>
                      <div className="text-lg font-bold text-amber-400 font-mono mt-1">
                        {(evalReport.metrics.conflict_detection_precision * 100).toFixed(1)}% /{' '}
                        {(evalReport.metrics.conflict_detection_recall * 100).toFixed(1)}%
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        Dup Acc: {(evalReport.metrics.duplicate_detection_accuracy * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800">
                      <div className="text-[11px] text-slate-400 uppercase font-mono">Mean / P95 Latency</div>
                      <div className="text-lg font-bold text-slate-200 font-mono mt-1">
                        {evalReport.metrics.mean_processing_latency_ms.toFixed(0)} /{' '}
                        {evalReport.metrics.p95_processing_latency_ms.toFixed(0)} ms
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">Offline cost: $0.00</div>
                    </div>
                  </div>

                  {/* Data Origin Breakdown (SYNTHETIC vs REAL_WORLD_INSPIRED) */}
                  {evalReport.data_origin_breakdown && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <h3 className="text-sm font-bold text-white">
                        Data Origin Split: Controlled Synthetic vs. Real-World-Inspired Adversarial Cases
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {Object.entries(evalReport.data_origin_breakdown).map(([origin, stats]) => (
                          <div key={origin} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                            <div>
                              <span className="text-xs font-mono uppercase text-sky-400 font-bold">{origin}</span>
                              <p className="text-xs text-slate-400 mt-0.5">
                                {stats.passed_cases} / {stats.total_cases} cases passed (95% CI [{(stats.ci_95[0] * 100).toFixed(1)}%, {(stats.ci_95[1] * 100).toFixed(1)}%])
                              </p>
                            </div>
                            <div className="text-lg font-bold font-mono text-emerald-400">
                              {(stats.accuracy * 100).toFixed(1)}%
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Four-System Baseline Comparison Table (Phase 6) */}
                  {evalReport.four_system_comparison && evalReport.four_system_comparison.length > 0 && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div>
                        <h3 className="text-sm font-bold text-white">
                          Four-System Baseline Comparison on Blind Held-Out Test Set (N={evalReport.total_cases})
                        </h3>
                        <p className="text-xs text-slate-400">
                          Compares Strict Regex (Baseline A), Structured Normalizer (Baseline B), Standalone Semantic AI without Rules (System C), and Full EvidenceOS (System D).
                        </p>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px]">
                            <tr>
                              <th className="p-3">System Architecture</th>
                              <th className="p-3">Decision Acc (95% CI)</th>
                              <th className="p-3">Macro-F1</th>
                              <th className="p-3">Field Acc</th>
                              <th className="p-3">Conflict P / R</th>
                              <th className="p-3">Abstention Rate</th>
                              <th className="p-3">Confident Error Rate</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800 font-mono">
                            {evalReport.four_system_comparison.map((sys) => {
                              const isBest = sys.system_id === 'System D';
                              const ci = sys.metrics.decision_accuracy_ci_95;
                              return (
                                <tr key={sys.system_id} className={isBest ? 'bg-emerald-950/20' : ''}>
                                  <td className="p-3 font-sans font-semibold text-white">
                                    {sys.system_name}
                                  </td>
                                  <td className={`p-3 font-bold ${isBest ? 'text-emerald-400' : 'text-slate-200'}`}>
                                    {(sys.metrics.decision_accuracy * 100).toFixed(1)}%{' '}
                                    {ci && (
                                      <span className="text-[10px] text-slate-400 font-normal">
                                        [{(ci[0] * 100).toFixed(1)}%, {(ci[1] * 100).toFixed(1)}%]
                                      </span>
                                    )}
                                  </td>
                                  <td className="p-3 text-sky-300">
                                    {(sys.metrics.macro_f1 ?? 0).toFixed(4)}
                                  </td>
                                  <td className="p-3 text-slate-200">
                                    {(sys.metrics.field_level_accuracy * 100).toFixed(1)}%
                                  </td>
                                  <td className="p-3 text-slate-300">
                                    {(sys.metrics.conflict_detection_precision * 100).toFixed(1)}% /{' '}
                                    {(sys.metrics.conflict_detection_recall * 100).toFixed(1)}%
                                  </td>
                                  <td className="p-3 text-slate-300">
                                    {((sys.metrics.appropriate_abstention_rate ?? 0) * 100).toFixed(1)}%
                                  </td>
                                  <td
                                    className={`p-3 font-bold ${
                                      (sys.metrics.confident_error_rate ?? 0) > 0.05
                                        ? 'text-rose-400'
                                        : 'text-emerald-400'
                                    }`}
                                  >
                                    {((sys.metrics.confident_error_rate ?? 0) * 100).toFixed(1)}%
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Six-Stage Modality Ablation Study Table (Phase 7) */}
                  {evalReport.modality_ablations && evalReport.modality_ablations.length > 0 && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div>
                        <h3 className="text-sm font-bold text-white">
                          Controlled Modality & Component Ablation Study (Ablations A–F)
                        </h3>
                        <p className="text-xs text-slate-400">
                          Isolates the empirical contribution of documents, voice transcripts, dock photos, perceptual hash history, and the deterministic rule engine.
                        </p>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px]">
                            <tr>
                              <th className="p-3">Ablation Stage</th>
                              <th className="p-3">Decision Acc (95% CI)</th>
                              <th className="p-3">Macro-F1</th>
                              <th className="p-3">Duplicate Acc</th>
                              <th className="p-3">Abstention Rate</th>
                              <th className="p-3">Confident Error Rate</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800 font-mono">
                            {evalReport.modality_ablations.map((ab) => {
                              const isFull = ab.ablation_id === 'Ablation F';
                              return (
                                <tr key={ab.ablation_id} className={isFull ? 'bg-emerald-950/20' : ''}>
                                  <td className="p-3 font-sans font-medium text-white">
                                    <span className="font-mono text-sky-400 mr-1.5">{ab.ablation_id}:</span>
                                    {ab.name}
                                  </td>
                                  <td className={`p-3 font-bold ${isFull ? 'text-emerald-400' : 'text-slate-200'}`}>
                                    {(ab.decision_accuracy * 100).toFixed(1)}%{' '}
                                    <span className="text-[10px] text-slate-400 font-normal">
                                      [{(ab.decision_accuracy_ci_95[0] * 100).toFixed(1)}%,{' '}
                                      {(ab.decision_accuracy_ci_95[1] * 100).toFixed(1)}%]
                                    </span>
                                  </td>
                                  <td className="p-3 text-sky-300">{ab.macro_f1.toFixed(4)}</td>
                                  <td className="p-3 text-slate-300">
                                    {(ab.duplicate_detection_accuracy * 100).toFixed(1)}%
                                  </td>
                                  <td className="p-3 text-slate-300">
                                    {(ab.appropriate_abstention_rate * 100).toFixed(1)}%
                                  </td>
                                  <td
                                    className={`p-3 font-bold ${
                                      ab.confident_error_rate > 0.05 ? 'text-rose-400' : 'text-emerald-400'
                                    }`}
                                  >
                                    {(ab.confident_error_rate * 100).toFixed(1)}%
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Head-to-Head Ablation Comparison Table */}
                  {ablation && !evalReport.four_system_comparison && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-sm font-bold text-white">
                            Head-to-Head Ablation: Semantic Multimodal Extractor vs. Strict Deterministic Regex Baseline
                          </h3>
                          <p className="text-xs text-slate-400">
                            Demonstrates why semantic extraction is necessary for prose delivery notes and colloquial warehouse voice transcripts, while keeping final rule evaluation deterministic.
                          </p>
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px]">
                            <tr>
                              <th className="p-3">Evaluation Metric (N={evalReport.total_cases} Cases)</th>
                              <th className="p-3 text-emerald-400">
                                Semantic Multimodal Pipeline ({ablation.semantic_multimodal_pipeline.provider || ablation.semantic_multimodal_pipeline.provider_name})
                              </th>
                              <th className="p-3 text-amber-400">
                                Strict Regex Baseline ({ablation.strict_regex_baseline.provider || ablation.strict_regex_baseline.provider_name})
                              </th>
                              <th className="p-3">Delta / Engineering Insight</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800 font-mono">
                            <tr>
                              <td className="p-3 font-sans font-medium text-slate-200">Decision Accuracy</td>
                              <td className="p-3 text-emerald-400 font-bold">
                                {(ablation.semantic_multimodal_pipeline.metrics.decision_accuracy * 100).toFixed(1)}%
                              </td>
                              <td className="p-3 text-amber-400">
                                {(ablation.strict_regex_baseline.metrics.decision_accuracy * 100).toFixed(1)}%
                              </td>
                              <td className="p-3 font-sans text-slate-300">
                                Baseline fails on prose POs & colloquial audio
                              </td>
                            </tr>
                            <tr>
                              <td className="p-3 font-sans font-medium text-slate-200">Field-Level Quantity Accuracy</td>
                              <td className="p-3 text-emerald-400 font-bold">
                                {(ablation.semantic_multimodal_pipeline.metrics.field_level_accuracy * 100).toFixed(1)}%
                              </td>
                              <td className="p-3 text-amber-400">
                                {(ablation.strict_regex_baseline.metrics.field_level_accuracy * 100).toFixed(1)}%
                              </td>
                              <td className="p-3 font-sans text-slate-300">
                                Gain on unstructured prose dispatch documents
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Error Taxonomy & Failure Inspector (Phase 10 & 11) */}
                  {evalReport.failures && evalReport.failures.length > 0 && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div>
                        <h3 className="text-sm font-bold text-white">
                          Error Taxonomy & Residual Failure Analysis ({evalReport.failures.length} / {evalReport.total_cases} Cases)
                        </h3>
                        <p className="text-xs text-slate-400">
                          Every error in System D is a conservative abstention to manual_review_required (0.0% Confident Error Rate).
                        </p>
                      </div>
                      <div className="space-y-2">
                        {evalReport.failures.map((f) => (
                          <div
                            key={f.case_id}
                            className="p-3 rounded-lg bg-slate-950 border border-rose-500/30 flex flex-col gap-1 text-xs"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-mono font-bold text-white">
                                {f.case_id} ({f.category})
                              </span>
                              <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono text-[11px]">
                                {f.failure_taxonomy}
                              </span>
                            </div>
                            <div className="text-slate-300">{f.root_cause_explanation}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Category Breakdown Grid */}
                  {evalReport.category_breakdown && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <h3 className="text-sm font-bold text-white">
                        Stratified Accuracy by Dispute Scenario Category
                      </h3>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                        {evalReport.category_breakdown.map((cb) => (
                          <div
                            key={cb.category}
                            className="p-3 rounded-lg bg-slate-950 border border-slate-800"
                          >
                            <div className="text-[11px] font-mono text-sky-400 uppercase truncate" title={cb.category}>
                              {cb.category.replace(/_/g, ' ')}
                            </div>
                            <div className="text-sm font-bold font-mono text-white mt-1">
                              {(cb.accuracy * 100).toFixed(1)}% ({cb.passed_cases}/{cb.total_cases})
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950/80 text-slate-400 uppercase font-mono text-[11px]">
                        <tr>
                          <th className="p-3">Case</th>
                          <th className="p-3">Category</th>
                          <th className="p-3">Expected</th>
                          <th className="p-3">Actual</th>
                          <th className="p-3">Ord/Del/Dmg</th>
                          <th className="p-3">Conflicts</th>
                          <th className="p-3">Latency</th>
                          <th className="p-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {evalReport.case_results.map((r) => (
                          <tr key={r.case_id} className="hover:bg-slate-900/40">
                            <td className="p-3 font-medium text-white">{r.title}</td>
                            <td className="p-3 font-mono text-[11px] text-slate-400">
                              {r.category || 'canonical'}
                            </td>
                            <td className="p-3">
                              <OutcomeBadge outcome={r.expected_outcome} />
                            </td>
                            <td className="p-3">
                              <OutcomeBadge outcome={r.actual_outcome} />
                            </td>
                            <td className="p-3 font-mono">
                              {r.ordered_qty} / {r.delivered_qty} / {r.verified_damaged_qty}
                            </td>
                            <td className="p-3 font-mono">
                              {r.conflicts_detected} (exp {r.expected_conflicts})
                            </td>
                            <td className="p-3 font-mono">{r.latency_ms} ms</td>
                            <td className="p-3">
                              {r.passed ? (
                                <span className="text-emerald-400 font-semibold">PASS ✓</span>
                              ) : (
                                <span className="text-rose-400 font-semibold">
                                  {r.failure_taxonomy || 'EDGE FAIL ✗'}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Active Case Screens */}
          {caseDetail && activeTab !== 'create_case' && activeTab !== 'evaluation' && (
            <>
              {/* Case Header Banner */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1 max-w-3xl">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
                      {caseDetail.po_number || caseDetail.id}
                    </span>
                    <span className="text-xs text-slate-400">
                      Supplier: <strong className="text-slate-200">{caseDetail.supplier_name}</strong> → Buyer:{' '}
                      <strong className="text-slate-200">{caseDetail.buyer_name}</strong>
                    </span>
                  </div>
                  <h1 className="text-lg font-bold text-white">{caseDetail.title}</h1>
                  <p className="text-xs text-slate-300">{caseDetail.description}</p>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <OutcomeBadge outcome={dec?.outcome} />
                  {dec && (
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                      <span>Confidence: {(dec.overall_confidence * 100).toFixed(0)}%</span>
                      <EpistemicBadge type={dec.epistemic_status} />
                    </div>
                  )}
                </div>
              </div>

              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left Column: Required CASE STATUS Checklist */}
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
                      CASE STATUS PIPELINE
                    </h3>
                    <div className="space-y-2.5 text-xs">
                      {[
                        {
                          label: 'Evidence received',
                          ok: checklist.evidence_received,
                          warn: false,
                        },
                        {
                          label: 'Documents processed',
                          ok: checklist.documents_processed,
                          warn: false,
                        },
                        {
                          label: 'Images analyzed',
                          ok: checklist.images_analyzed,
                          warn: false,
                        },
                        {
                          label: 'Voice analyzed',
                          ok: checklist.voice_analyzed,
                          warn: false,
                        },
                        {
                          label: 'Evidence linked',
                          ok: checklist.evidence_linked,
                          warn: false,
                        },
                        {
                          label: 'Conflicts detected',
                          ok: !checklist.conflicts_detected,
                          warn: checklist.conflicts_detected,
                        },
                        {
                          label: 'Rules evaluated',
                          ok: checklist.rules_evaluated,
                          warn: false,
                        },
                      ].map((row) => (
                        <div
                          key={row.label}
                          className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80"
                        >
                          <span className="font-medium text-slate-200">{row.label}</span>
                          {row.warn ? (
                            <span className="text-amber-400 font-bold font-mono text-sm">
                              ⚠ ({caseDetail.conflicts.length + caseDetail.historical_warnings.length})
                            </span>
                          ) : row.ok ? (
                            <span className="text-emerald-400 font-bold font-mono text-sm">
                              ✓
                            </span>
                          ) : (
                            <span className="text-slate-600 font-mono">—</span>
                          )}
                        </div>
                      ))}

                      <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                        <span className="font-bold text-white">Decision</span>
                        <OutcomeBadge outcome={dec?.outcome} />
                      </div>
                    </div>
                  </div>

                  {/* Right 2 Columns: Non-Technical Executive Explanation + Quantity Reconciliation */}
                  <div className="lg:col-span-2 space-y-5">
                    {dec && (
                      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                          <h3 className="text-xs font-bold uppercase tracking-wider text-sky-400">
                            Executive Decision Summary (What Happened & Why)
                          </h3>
                          <EpistemicBadge type={dec.epistemic_status} />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                            <span className="text-[11px] font-semibold uppercase text-slate-400">
                              What Happened & Why Is The System Saying This?
                            </span>
                            <p className="text-slate-100 leading-relaxed">
                              {dec.summary_reason}
                            </p>
                          </div>
                          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                            <span className="text-[11px] font-semibold uppercase text-emerald-400">
                              What Should I Do Next?
                            </span>
                            <p className="text-slate-100 leading-relaxed">
                              {dec.next_action}
                            </p>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-1">
                          {[
                            { label: 'Ordered (PO)', val: `${dec.ordered_quantity} units` },
                            { label: 'Delivered (Challan)', val: `${dec.delivered_quantity} units` },
                            { label: 'Verified Damaged', val: `${dec.verified_damaged_quantity} units` },
                            { label: 'Accepted Intact', val: `${dec.accepted_quantity} units` },
                            {
                              label: 'Credit Adjustment',
                              val: `$${dec.recommended_payout_adjustment_usd.toFixed(2)}`,
                            },
                          ].map((q) => (
                            <div
                              key={q.label}
                              className="p-3 rounded-lg bg-slate-950/90 border border-slate-800 text-center"
                            >
                              <div className="text-[10px] uppercase text-slate-400">
                                {q.label}
                              </div>
                              <div className="text-sm font-bold font-mono text-white mt-1">
                                {q.val}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Clickable Evidence Artifacts Grid */}
                    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                          Supporting Evidence Artifacts (Click Any Evidence to Inspect Provenance)
                        </h3>
                        <span className="text-xs font-mono text-slate-400">
                          {caseDetail.evidence_items.length} artifacts
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {caseDetail.evidence_items.map((item) => {
                          const prov = item.extracted_payload?.provenance;
                          return (
                            <div
                              key={item.id}
                              onClick={() => setInspectedEvidence(item)}
                              className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-sky-500/60 cursor-pointer transition flex items-start justify-between gap-3"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-semibold text-sky-300">
                                    {item.document_role.replace(/_/g, ' ').toUpperCase()}
                                  </span>
                                  <EpistemicBadge type={prov?.epistemic_type} />
                                </div>
                                <div className="text-xs text-white font-medium">
                                  {item.original_filename}
                                </div>
                                <div className="text-[11px] font-mono text-slate-400">
                                  SHA256: {item.sha256_hash.slice(0, 12)}… • Conf:{' '}
                                  {prov ? `${(prov.confidence * 100).toFixed(0)}%` : 'N/A'}
                                </div>
                              </div>
                              <span className="text-[11px] text-sky-400 font-mono shrink-0">
                                Inspect →
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: EVIDENCE UPLOAD */}
              {activeTab === 'upload' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white">
                      Upload Multimodal Evidence File (PDF, PNG/JPG, WAV/MP3, JSON, CSV)
                    </h3>
                    <form onSubmit={handleFileUpload} className="space-y-4 text-xs">
                      <div>
                        <label className="block text-slate-300 mb-1 font-medium">
                          Select File (Max 25 MB, Validated by Magic Bytes)
                        </label>
                        <input
                          type="file"
                          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                          className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-sky-500 file:text-slate-950"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-300 mb-1 font-medium">
                          Document / Evidence Role (Optional — Auto-Detected if omitted)
                        </label>
                        <select
                          value={uploadRole}
                          onChange={(e) => setUploadRole(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                        >
                          <option value="">Auto-detect from file & content</option>
                          <option value="purchase_order">Purchase Order (PO)</option>
                          <option value="delivery_challan">Delivery Challan / Packing Slip</option>
                          <option value="invoice">Commercial Invoice</option>
                          <option value="inspection_image">Product / Dock Inspection Image</option>
                          <option value="voice_report">Warehouse / Driver Voice Report</option>
                        </select>
                      </div>
                      <button
                        type="submit"
                        disabled={!uploadFile || loading}
                        className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-semibold"
                      >
                        Ingest & Hash Evidence File
                      </button>
                    </form>
                  </div>

                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white">
                      Add Manual Dock Note or Voice Transcript
                    </h3>
                    <form onSubmit={handleManualSubmit} className="space-y-4 text-xs">
                      <div>
                        <label className="block text-slate-300 mb-1 font-medium">
                          Evidence Type
                        </label>
                        <select
                          value={manualRole}
                          onChange={(e) => setManualRole(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                        >
                          <option value="voice_report">Receiving Dock Voice Report</option>
                          <option value="delivery_challan">Delivery Note Text</option>
                          <option value="purchase_order">Purchase Order Text</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-slate-300 mb-1 font-medium">
                          Statement / Structured Text
                        </label>
                        <textarea
                          rows={4}
                          value={manualText}
                          onChange={(e) => setManualText(e.target.value)}
                          placeholder='e.g., "Two boxes of SKU-IND-100 were damaged during unloading."'
                          className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={!manualText.trim() || loading}
                        className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-slate-950 font-semibold"
                      >
                        Ingest Manual Statement
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* TAB 3: EVIDENCE TIMELINE & NORMALIZED CLAIMS */}
              {activeTab === 'timeline' && (
                <div className="space-y-4">
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                    <h3 className="text-sm font-bold text-white">
                      Normalized Cross-Modal Claims & Epistemological Classification
                    </h3>
                    <p className="text-xs text-slate-400">
                      Every extracted statement is normalized into a canonical{' '}
                      <code className="text-sky-300">(entity_key, attribute, value)</code> tuple with explicit provenance.
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] uppercase">
                          <tr>
                            <th className="p-3">Entity Key</th>
                            <th className="p-3">Attribute</th>
                            <th className="p-3">Value</th>
                            <th className="p-3">Epistemic Status</th>
                            <th className="p-3">Source Role & Method</th>
                            <th className="p-3">Confidence</th>
                            <th className="p-3">Reason</th>
                            <th className="p-3">Provenance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {caseDetail.claims.map((c) => (
                            <tr key={c.claim_id} className="hover:bg-slate-900/50">
                              <td className="p-3 font-mono text-sky-300">{c.entity_key}</td>
                              <td className="p-3 font-mono">{c.attribute}</td>
                              <td className="p-3 font-mono font-bold text-white">
                                {c.value !== null && c.value !== undefined ? String(c.value) : 'UNCLEAR'}
                              </td>
                              <td className="p-3">
                                <EpistemicBadge type={c.epistemic_type} />
                              </td>
                              <td className="p-3 font-mono text-[11px] text-slate-300">
                                {c.provenance.document_role} ({c.provenance.extraction_method})
                              </td>
                              <td className="p-3 font-mono">
                                {(c.provenance.confidence * 100).toFixed(0)}%
                              </td>
                              <td className="p-3 text-slate-300">{c.reason}</td>
                              <td className="p-3">
                                <button
                                  onClick={() => handleInspectEvidenceById(c.provenance.evidence_id)}
                                  className="text-sky-400 hover:underline font-mono text-[11px]"
                                >
                                  {c.provenance.evidence_id}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: EVIDENCE GRAPH */}
              {activeTab === 'graph' && (
                <InteractiveEvidenceGraph
                  graph={caseDetail.graph}
                  onSelectEvidenceId={handleInspectEvidenceById}
                />
              )}

              {/* TAB 5: CONFLICT ANALYSIS & HISTORICAL MATCHING */}
              {activeTab === 'conflicts' && (
                <div className="space-y-5">
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                      <span>Historical Evidence Reuse & Perceptual Hash Analysis</span>
                    </h3>
                    {caseDetail.historical_warnings.length === 0 ? (
                      <p className="text-xs text-emerald-400">
                        ✓ All uploaded files and inspection images passed SHA-256 and 64-bit dHash uniqueness checks against prior cases.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {caseDetail.historical_warnings.map((w) => (
                          <div
                            key={w.match_id}
                            className="p-4 rounded-lg bg-rose-950/30 border border-rose-500/40 space-y-2 text-xs"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-rose-300">
                                ⚠ Potentially reused evidence detected
                              </span>
                              <span className="font-mono text-rose-200">
                                Match Type: {w.match_type} • Similarity:{' '}
                                {(w.similarity_score * 100).toFixed(1)}% (Hamming Dist:{' '}
                                {w.hamming_distance}/64)
                              </span>
                            </div>
                            <p className="text-slate-200">{w.warning_message}</p>
                            <div className="flex gap-3 pt-1">
                              <button
                                onClick={() => handleInspectEvidenceById(w.current_evidence_id)}
                                className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-sky-400 font-mono text-[11px] border border-slate-700"
                              >
                                Inspect Current Evidence ({w.current_evidence_id})
                              </button>
                              <button
                                onClick={() => handleSelectCase(w.historical_case_id)}
                                className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-amber-300 font-mono text-[11px] border border-slate-700"
                              >
                                Switch to Historical Case ({w.historical_case_id})
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span>Cross-Modal Contradictions ({caseDetail.conflicts.length})</span>
                    </h3>
                    {caseDetail.conflicts.length === 0 ? (
                      <p className="text-xs text-emerald-400">
                        ✓ Zero contradictions detected across Purchase Order, Delivery Challan, Inspection Image, and Voice claims.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {caseDetail.conflicts.map((cnf) => (
                          <div
                            key={cnf.conflict_id}
                            className="p-4 rounded-lg bg-amber-950/20 border border-amber-500/40 space-y-3 text-xs"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-amber-300">
                                {cnf.conflict_type} ({cnf.severity.toUpperCase()})
                              </span>
                              <EpistemicBadge type={cnf.epistemic_type} />
                            </div>
                            <p className="text-slate-100 font-medium">{cnf.description}</p>
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                              {cnf.competing_values.map((cv, idx) => (
                                <div
                                  key={idx}
                                  onClick={() => handleInspectEvidenceById(cv.evidence_id)}
                                  className="p-2.5 rounded bg-slate-950 border border-slate-800 hover:border-sky-500/50 cursor-pointer"
                                >
                                  <div className="text-[11px] font-mono text-sky-400">
                                    {cv.document_role} ({cv.evidence_id})
                                  </div>
                                  <div className="text-sm font-bold font-mono text-white mt-0.5">
                                    Value: {cv.value !== null && cv.value !== undefined ? String(cv.value) : 'INCONCLUSIVE'}
                                  </div>
                                  <div className="text-[10px] font-mono text-slate-400">
                                    Confidence: {(cv.confidence * 100).toFixed(0)}%
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 6: DETERMINISTIC RULES, DECISION & HUMAN REVIEW */}
              {activeTab === 'decision' && dec && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div>
                        <h3 className="text-sm font-bold text-white">
                          Deterministic Contract & SLA Rule Evaluation Trace
                        </h3>
                        <p className="text-xs text-slate-400">
                          Every rule is evaluated deterministically in Python over normalized claims—never delegated to an LLM.
                        </p>
                      </div>
                      <OutcomeBadge outcome={dec.outcome} />
                    </div>

                    <div className="space-y-3">
                      {dec.rule_traces.map((rt) => (
                        <div
                          key={rt.rule_id}
                          className={`p-3.5 rounded-lg border text-xs ${
                            rt.passed
                              ? 'bg-emerald-950/10 border-emerald-500/30'
                              : 'bg-amber-950/20 border-amber-500/40'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono font-bold text-slate-100">
                              {rt.rule_id} — {rt.rule_name}
                            </span>
                            <span
                              className={`font-mono font-bold ${
                                rt.passed ? 'text-emerald-400' : 'text-amber-400'
                              }`}
                            >
                              {rt.passed ? 'PASS ✓' : 'FAIL ⚠'}
                            </span>
                          </div>
                          <p className="text-slate-300 mb-2">{rt.explanation}</p>
                          <pre className="text-[11px] font-mono text-slate-400 bg-slate-950 p-2 rounded border border-slate-800 overflow-x-auto">
                            Inputs: {JSON.stringify(rt.inputs_used)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Human-in-the-Loop Adjudication Panel */}
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                      <UserCheck className="w-4 h-4 text-sky-400" />
                      <h3 className="text-sm font-bold text-white">
                        Human Adjudicator Review & Override
                      </h3>
                    </div>
                    <p className="text-xs text-slate-400">
                      When conflicts or low-confidence visual evidence occur, EvidenceOS routes the case to human review and logs overrides in the hash-chained audit trail.
                    </p>
                    <form onSubmit={handleHumanOverride} className="space-y-3 text-xs">
                      <div>
                        <label className="block text-slate-300 mb-1">Reviewer Identifier</label>
                        <input
                          type="text"
                          required
                          value={reviewerName}
                          onChange={(e) => setReviewerName(e.target.value)}
                          className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-800 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-300 mb-1">Override Decision</label>
                        <select
                          value={reviewOutcome}
                          onChange={(e) => setReviewOutcome(e.target.value as DecisionOutcome)}
                          className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-800 text-white"
                        >
                          <option value="approved">Approved</option>
                          <option value="partially_approved">Partially Approved</option>
                          <option value="disputed">Disputed / Rejected</option>
                          <option value="manual_review_required">Keep in Manual Review</option>
                        </select>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-300 mb-1">Accepted Units</label>
                          <input
                            type="number"
                            value={reviewAcceptedQty}
                            onChange={(e) => setReviewAcceptedQty(Number(e.target.value))}
                            className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-800 text-white font-mono"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-300 mb-1">Verified Damaged</label>
                          <input
                            type="number"
                            value={reviewDamagedQty}
                            onChange={(e) => setReviewDamagedQty(Number(e.target.value))}
                            className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-800 text-white font-mono"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-slate-300 mb-1">
                          Adjudication Rationale (Required for Audit Trail)
                        </label>
                        <textarea
                          rows={3}
                          required
                          value={reviewNotes}
                          onChange={(e) => setReviewNotes(e.target.value)}
                          placeholder="Document physical inspection sign-off or carrier reconciliation..."
                          className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-800 text-white"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={loading || !reviewNotes.trim()}
                        className="w-full py-2 rounded-lg bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-semibold"
                      >
                        Record Human Adjudication
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* TAB 7: TAMPER-EVIDENT AUDIT TRAIL */}
              {activeTab === 'audit' && auditTrail && (
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-white">
                        Cryptographic SHA-256 Hash-Chained Audit Trail
                      </h3>
                      <p className="text-xs text-slate-400">
                        Every ingestion, extraction, conflict check, rule evaluation, and human override is chained to the previous event hash.
                      </p>
                    </div>
                    <div className="px-3 py-1 rounded bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono">
                      Chain Integrity: {auditTrail.chain_integrity.valid ? 'VERIFIED ✓' : 'BROKEN ✗'} (
                      {auditTrail.chain_integrity.event_count} events)
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    {auditTrail.events.map((ev, idx) => (
                      <div
                        key={ev.id}
                        className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-slate-500">#{idx + 1}</span>
                            <span className="font-mono font-bold text-sky-300">
                              {ev.event_type}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 font-mono text-[10px]">
                              stage: {ev.stage}
                            </span>
                            <span className="text-slate-400">by {ev.actor}</span>
                          </div>
                          <span className="font-mono text-[11px] text-slate-400">
                            {ev.duration_ms ? `${ev.duration_ms} ms • ` : ''}
                            {ev.model_used ? `${ev.model_used} • ` : ''}
                            {new Date(ev.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <pre className="text-[11px] font-mono text-slate-300 bg-slate-900/90 p-2 rounded border border-slate-800 overflow-x-auto">
                          {JSON.stringify(ev.details)}
                        </pre>
                        <div className="flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-500 pt-1">
                          <span>Prev Hash: {ev.previous_event_hash?.slice(0, 24)}…</span>
                          <span className="text-emerald-400/90">
                            Event SHA-256: {ev.event_hash.slice(0, 24)}…
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* Clickable Evidence Provenance Drawer */}
      <EvidenceInspectorDrawer
        caseId={selectedCaseId}
        item={inspectedEvidence}
        onClose={() => setInspectedEvidence(null)}
      />
    </div>
  );
}
export default App;
