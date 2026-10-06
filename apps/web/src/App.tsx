import React, { useEffect, useState } from 'react';
import { api } from './api';
import {
  AuditTrailResponse,
  CaseDetail,
  CaseSummary,
  DecisionOutcome,
  EvaluationReport,
  EvidenceItem,
  NormalizedClaim,
} from './types';
import {
  EpistemicBadge,
  EvidenceInspectorDrawer,
  InteractiveEvidenceGraph,
  OutcomeBadge,
} from './components/EvidenceWidgets';
import { ProvenanceModal } from './components/ProvenanceModal';
import { ConflictPresentationList } from './components/ConflictCard';
import { DecisionReviewPanel } from './components/DecisionReviewPanel';
import { AuditTrailPanel } from './components/AuditTrailPanel';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock,
  ExternalLink,
  FilePlus2,
  FileText,
  FolderKanban,
  GitBranch,
  HelpCircle,
  History,
  Image as ImageIcon,
  Layers,
  Menu,
  Mic,
  Play,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
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

type PrimarySection =
  | 'cases'
  | 'evidence'
  | 'investigation'
  | 'benchmarks'
  | 'audit';

const GUIDED_STORY_STEPS: Array<{
  step: number;
  title: string;
  subtitle: string;
  tab: ActiveTab;
  description: string;
}> = [
  {
    step: 1,
    title: '1. Upload & Ingest',
    subtitle: 'SHA-256 + 64-bit dHash & Magic Byte Check',
    tab: 'overview',
    description:
      'Ingests the Purchase Order PDF, Delivery Challan PDF, Dock Photo PNG, and Warehouse Voice WAV while preserving original files.',
  },
  {
    step: 2,
    title: '2. Investigate Claims',
    subtitle: 'Normalize PO, Challan, Photo & Voice',
    tab: 'timeline',
    description:
      'Extracts structured quantities from each modality and tags every claim as FACT, INFERENCE, RULE, or UNCERTAINTY. Click [Why?] on any claim.',
  },
  {
    step: 3,
    title: '3. Evidence Conflict',
    subtitle: 'Surface Cross-Modal Contradictions',
    tab: 'conflicts',
    description:
      'Flags where the Delivery Challan (8 delivered), Voice Report (5 damaged), and Inspection Photo (2 damaged) contradict each other.',
  },
  {
    step: 4,
    title: '4. Explain Provenance',
    subtitle: 'Trace DAG to Original Files',
    tab: 'graph',
    description:
      'Traces every claim from the Purchase Order and Shipment SKU down to the conflicts, rules, and decision.',
  },
  {
    step: 5,
    title: '5. Deterministic Decision',
    subtitle: 'Evaluate SLA Rules & Human Review',
    tab: 'decision',
    description:
      'Evaluates deterministic contract rules and routes the contradicted case to Manual Review Required so a human reviewer can adjudicate.',
  },
];

export function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [auditTrail, setAuditTrail] = useState<AuditTrailResponse | null>(null);
  const [evalReport, setEvalReport] = useState<EvaluationReport | null>(null);
  const [evalSuiteType, setEvalSuiteType] = useState<
    'heldout_150' | 'extended_60' | 'canonical_5'
  >('heldout_150');
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
  const [guidedStepIndex, setGuidedStepIndex] = useState<number>(0);
  const [inspectedEvidence, setInspectedEvidence] =
    useState<EvidenceItem | null>(null);
  const [tracedClaim, setTracedClaim] = useState<NormalizedClaim | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);

  // Create Case form state
  const [newTitle, setNewTitle] = useState('');
  const [newPo, setNewPo] = useState('PO-2026-2050');
  const [newSupplier, setNewSupplier] = useState(
    'Apex Industrial Components Ltd.'
  );
  const [newBuyer, setNewBuyer] = useState(
    'Vertex Logistics & Manufacturing Corp.'
  );
  const [newDesc, setNewDesc] = useState('');

  // Upload Evidence state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadRole, setUploadRole] = useState<string>('');
  const [manualText, setManualText] = useState<string>('');
  const [manualRole, setManualRole] = useState<string>('voice_report');

  // Human Review Override state
  const [reviewerName, setReviewerName] = useState('senior_procurement_auditor');
  const [reviewOutcome, setReviewOutcome] =
    useState<DecisionOutcome>('partially_approved');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewAcceptedQty, setReviewAcceptedQty] = useState<number>(8);
  const [reviewDamagedQty, setReviewDamagedQty] = useState<number>(2);

  const loadCases = async (preferredId?: string) => {
    try {
      setLoading(true);
      setLoadingStage('Loading dispute cases & evidence state...');
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
      setErrorMsg(
        err.message ||
          'Unable to load dispute cases. Verify the FastAPI server is running.'
      );
    } finally {
      setLoading(false);
      setLoadingStage('');
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
      setErrorMsg(err.message || 'Failed to load case investigation details.');
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleSelectCase = async (cid: string) => {
    setSelectedCaseId(cid);
    setInspectedEvidence(null);
    setTracedClaim(null);
    setMobileSidebarOpen(false);
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
      setLoadingStage('Creating new dispute investigation case...');
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
      setErrorMsg(`Case creation failed: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !selectedCaseId) return;
    try {
      setLoading(true);
      setLoadingStage(
        `Uploading & computing SHA-256 / dHash for ${uploadFile.name}...`
      );
      await api.uploadEvidence(
        selectedCaseId,
        uploadFile,
        uploadRole || undefined
      );
      setUploadFile(null);
      await loadCaseDetail(selectedCaseId);
    } catch (err: any) {
      setErrorMsg(
        `Evidence upload failed (${uploadFile.name}): ${err.message}. Check that the file is a valid PDF, PNG, JPG, WAV, JSON, or CSV under 25 MB.`
      );
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualText.trim() || !selectedCaseId) return;
    try {
      setLoading(true);
      setLoadingStage('Ingesting & hashing manual dock statement...');
      await api.addManualEvidence(selectedCaseId, {
        filename: `${manualRole}_note.txt`,
        document_role: manualRole,
        text_content: manualText,
      });
      setManualText('');
      await loadCaseDetail(selectedCaseId);
    } catch (err: any) {
      setErrorMsg(`Manual statement ingestion failed: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleRunPipeline = async () => {
    if (!selectedCaseId) return;
    try {
      setLoading(true);
      setLoadingStage(
        'Processing documents → Analyzing images & voice → Linking entities → Checking conflicts → Evaluating SLA rules...'
      );
      await api.processCase(selectedCaseId);
      await loadCases(selectedCaseId);
      setActiveTab('overview');
    } catch (err: any) {
      setErrorMsg(`Verification pipeline error: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleHumanOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId || !reviewNotes.trim()) return;
    try {
      setLoading(true);
      setLoadingStage(
        'Recording human reviewer decision & chaining SHA-256 audit entry...'
      );
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
      setErrorMsg(`Human review submission failed: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleRunEvaluation = async (
    suite: 'heldout_150' | 'extended_60' | 'canonical_5' = evalSuiteType
  ) => {
    try {
      setLoading(true);
      setLoadingStage(
        `Running ${
          suite === 'heldout_150'
            ? '150-case blind held-out evaluation'
            : suite === 'extended_60'
            ? '60-case development benchmark'
            : '5-case canonical regression'
        }...`
      );
      setEvalSuiteType(suite);
      const rep = await api.runEvaluation(suite);
      setEvalReport(rep);
      setActiveTab('evaluation');
    } catch (err: any) {
      setErrorMsg(`Benchmark evaluation failed: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const handleResetDemoCases = async () => {
    try {
      setLoading(true);
      setLoadingStage('Re-seeding the 5 canonical VeriDock dispute cases...');
      await api.seedDemoCases();
      await loadCases('case_03_conflicting_evidence');
      setActiveTab('overview');
    } catch (err: any) {
      setErrorMsg(`Reset demo cases failed: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadingStage('');
    }
  };

  const checklist = caseDetail?.pipeline_checklist || {};
  const dec = caseDetail?.latest_decision;

  // Map ActiveTab to the 5 primary navigation sections
  const currentPrimarySection: PrimarySection =
    activeTab === 'evaluation'
      ? 'benchmarks'
      : activeTab === 'audit'
      ? 'audit'
      : activeTab === 'upload'
      ? 'evidence'
      : activeTab === 'create_case'
      ? 'cases'
      : 'investigation';

  // Compute timeline stage statuses for the 5-stage Investigation Timeline
  const getStageStatus = (
    stepNum: number
  ): {
    label: string;
    cls: string;
    badgeCls: string;
  } => {
    if (!caseDetail || caseDetail.evidence_items.length === 0) {
      return {
        label: 'Not started',
        cls: 'border-slate-800 bg-slate-950/60 text-slate-400',
        badgeCls: 'bg-slate-800 text-slate-400',
      };
    }
    const hasConflicts =
      caseDetail.conflicts.length + caseDetail.historical_warnings.length > 0;
    const isCurrent = GUIDED_STORY_STEPS[stepNum - 1].tab === activeTab;

    if (stepNum === 3 && hasConflicts) {
      return {
        label: isCurrent ? 'Current • Needs attention' : 'Needs attention ⚠',
        cls: isCurrent
          ? 'border-amber-400 bg-amber-500/15 text-white'
          : 'border-amber-500/40 bg-amber-950/20 text-slate-200 hover:border-amber-400',
        badgeCls: 'bg-amber-500/20 text-amber-300 border border-amber-500/40',
      };
    }
    if (
      stepNum === 5 &&
      dec &&
      (dec.outcome === 'manual_review_required' ||
        dec.outcome === 'insufficient_evidence')
    ) {
      return {
        label: isCurrent ? 'Current • Review required' : 'Needs attention ⚠',
        cls: isCurrent
          ? 'border-amber-400 bg-amber-500/15 text-white'
          : 'border-amber-500/40 bg-amber-950/20 text-slate-200 hover:border-amber-400',
        badgeCls: 'bg-amber-500/20 text-amber-300 border border-amber-500/40',
      };
    }
    if (isCurrent) {
      return {
        label: 'Current ●',
        cls: 'border-sky-400 bg-sky-500/15 text-white',
        badgeCls: 'bg-sky-500/20 text-sky-300 border border-sky-500/40',
      };
    }
    if (dec) {
      return {
        label: 'Completed ✓',
        cls: 'border-slate-800 bg-slate-950/80 text-slate-200 hover:border-slate-700',
        badgeCls:
          'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
      };
    }
    return {
      label: 'In progress',
      cls: 'border-slate-800 bg-slate-950/80 text-slate-300',
      badgeCls: 'bg-slate-800 text-slate-300',
    };
  };

  return (
    <div className="eos-viewport-shell flex flex-col bg-[#0b111e] text-slate-100">
      {/* Top Application Header Shell */}
      <header className="border-b border-slate-800 bg-slate-950/95 sticky top-0 z-30 px-4 lg:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
            aria-label="Toggle navigation sidebar"
            className="lg:hidden p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-200"
          >
            <Menu className="w-4 h-4" aria-hidden="true" />
          </button>
          <div className="w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-500/40 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-sky-400" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white text-sm sm:text-base">
                EvidenceOS
              </span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-900 text-sky-300 border border-slate-700 font-mono">
                VeriDock
              </span>
              <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                <span
                  className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                  aria-hidden="true"
                />
                <span>System OK</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              B2B Delivery & Procurement Dispute Verification Workstation
            </p>
          </div>
        </div>

        {/* Right Header Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              handleSelectCase('case_03_conflicting_evidence');
              handleGuidedStepClick(0);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 transition"
          >
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Launch Guided Flagship Demo (Case 3)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('create_case')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-slate-100 border border-slate-700 transition"
          >
            <FilePlus2 className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
            <span>New Case</span>
          </button>
          <button
            type="button"
            onClick={handleResetDemoCases}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
            title="Reset all 5 canonical cases to their initial state"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`}
              aria-hidden="true"
            />
            <span className="hidden md:inline">Reset Demo</span>
          </button>
        </div>
      </header>

      {/* Meaningful Stage-Aware Loading Banner */}
      {loading && loadingStage && (
        <div
          role="status"
          aria-live="polite"
          className="bg-sky-950/90 border-b border-sky-500/40 px-6 py-2 text-xs text-sky-200 flex items-center gap-2.5"
        >
          <RefreshCw className="w-3.5 h-3.5 animate-spin text-sky-400 shrink-0" />
          <span className="font-mono">{loadingStage}</span>
        </div>
      )}

      {/* Actionable Error Banner */}
      {errorMsg && (
        <div
          role="alert"
          className="bg-rose-950/90 border-b border-rose-500/50 px-6 py-3 text-xs text-rose-100 flex flex-wrap items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>
              <strong>Operation Error:</strong> {errorMsg}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => loadCases(selectedCaseId)}
              className="px-2.5 py-1 rounded bg-rose-900 hover:bg-rose-800 text-rose-100 border border-rose-700 font-medium"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Main Application Body: Sidebar + Investigation Workspace */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Navigation & Case Switcher Sidebar */}
        <aside
          aria-label="Primary Navigation and Dispute Cases"
          className={`${
            mobileSidebarOpen ? 'block' : 'hidden'
          } lg:flex w-full lg:w-80 border-r border-slate-800 bg-slate-950/80 flex-col shrink-0`}
        >
          {/* 5 Primary Navigation Items: Cases, Evidence, Investigation, Benchmarks, Audit */}
          <nav
            aria-label="Workspace Sections"
            className="p-3 border-b border-slate-800 space-y-1"
          >
            <div className="px-2 pb-1 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              Navigation
            </div>
            {[
              {
                id: 'cases' as PrimarySection,
                label: 'Cases',
                sub: `${cases.length} active`,
                icon: FolderKanban,
                onClick: () => setActiveTab('overview'),
              },
              {
                id: 'evidence' as PrimarySection,
                label: 'Evidence',
                sub: `${caseDetail?.evidence_items.length ?? 0} files`,
                icon: Upload,
                onClick: () => setActiveTab('upload'),
              },
              {
                id: 'investigation' as PrimarySection,
                label: 'Investigation',
                sub: 'Claims, Conflicts & Decision',
                icon: Scale,
                onClick: () => setActiveTab('overview'),
              },
              {
                id: 'benchmarks' as PrimarySection,
                label: 'Benchmarks',
                sub: 'n=150 Held-Out Suite',
                icon: BarChart3,
                onClick: () => {
                  if (!evalReport) {
                    handleRunEvaluation('heldout_150');
                  } else {
                    setActiveTab('evaluation');
                  }
                },
              },
              {
                id: 'audit' as PrimarySection,
                label: 'Audit Trail',
                sub: `${auditTrail?.events.length ?? 0} chained events`,
                icon: History,
                onClick: () => setActiveTab('audit'),
              },
            ].map((navItem) => {
              const Icon = navItem.icon;
              const isCurrent = currentPrimarySection === navItem.id;
              return (
                <button
                  key={navItem.id}
                  type="button"
                  onClick={() => {
                    navItem.onClick();
                    setMobileSidebarOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition ${
                    isCurrent
                      ? 'bg-sky-500/15 text-sky-300 border border-sky-500/35'
                      : 'text-slate-300 hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
                    <span>{navItem.label}</span>
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    {navItem.sub}
                  </span>
                </button>
              );
            })}
          </nav>

          {/* Case Switcher List */}
          <div className="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between bg-slate-950">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
              Dispute Cases ({cases.length})
            </span>
            <button
              type="button"
              onClick={() => setActiveTab('create_case')}
              className="text-[11px] text-sky-400 hover:underline font-medium"
            >
              + New Case
            </button>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/70">
            {cases.map((c) => {
              const isSelected = c.id === selectedCaseId;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => handleSelectCase(c.id)}
                  className={`w-full text-left p-3.5 transition-colors ${
                    isSelected
                      ? 'bg-sky-500/10 border-l-2 border-l-sky-400'
                      : 'hover:bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-xs font-mono font-semibold text-slate-300">
                      {c.po_number || c.id}
                    </span>
                    <OutcomeBadge outcome={c.latest_decision_outcome} />
                  </div>
                  <div className="text-xs font-semibold text-white line-clamp-2 mb-1.5">
                    {c.title}
                  </div>
                  <div className="flex flex-wrap items-center gap-2.5 text-[11px] text-slate-400 font-mono">
                    <span>Evidence: {c.evidence_count}</span>
                    {c.conflict_count > 0 && (
                      <span className="text-amber-300">
                        ⚠ {c.conflict_count} conflict
                        {c.conflict_count > 1 ? 's' : ''}
                      </span>
                    )}
                    {c.historical_warning_count > 0 && (
                      <span className="text-rose-300">⚠ Reused Img</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Center Main Investigation Workspace */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {/* Workflow Breadcrumb Strip: CASE -> EVIDENCE -> INVESTIGATION -> CONFLICTS -> PROVENANCE -> RULES -> DECISION -> HUMAN REVIEW -> AUDIT */}
          {caseDetail && activeTab !== 'create_case' && activeTab !== 'evaluation' && (
            <div className="eos-panel eos-reveal eos-stagger-1 flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-400">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-slate-300 font-semibold">WORKFLOW:</span>
                {[
                  { label: 'CASE', tab: 'overview' as ActiveTab },
                  { label: 'EVIDENCE', tab: 'upload' as ActiveTab },
                  { label: 'CLAIMS', tab: 'timeline' as ActiveTab },
                  { label: 'CONFLICTS', tab: 'conflicts' as ActiveTab },
                  { label: 'PROVENANCE', tab: 'graph' as ActiveTab },
                  { label: 'RULES & DECISION', tab: 'decision' as ActiveTab },
                  { label: 'AUDIT', tab: 'audit' as ActiveTab },
                ].map((w, i, arr) => (
                  <React.Fragment key={w.label}>
                    <button
                      type="button"
                      onClick={() => setActiveTab(w.tab)}
                      className={`px-1.5 py-0.5 rounded transition ${
                        activeTab === w.tab
                          ? 'bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40'
                          : 'hover:text-white'
                      }`}
                    >
                      {w.label}
                    </button>
                    {i < arr.length - 1 && (
                      <span aria-hidden="true" className="text-slate-600">
                        →
                      </span>
                    )}
                  </React.Fragment>
                ))}
              </div>
              <button
                type="button"
                onClick={handleRunPipeline}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-slate-950 font-sans font-semibold text-xs transition"
              >
                <Play className="w-3 h-3 fill-current" aria-hidden="true" />
                <span>Investigate / Re-Verify Case</span>
              </button>
            </div>
          )}

          {/* Create Case Screen */}
          {activeTab === 'create_case' && (
            <div className="eos-panel eos-reveal eos-stagger-1 max-w-2xl bg-slate-900/80 border border-slate-800 rounded-xl p-6 space-y-4">
              <h2 className="text-base font-bold text-white">
                Create New B2B Delivery Dispute Case
              </h2>
              <form onSubmit={handleCreateCase} className="space-y-4 text-xs">
                <div>
                  <label
                    htmlFor="new-case-title"
                    className="block text-slate-300 mb-1 font-medium"
                  >
                    Case Title *
                  </label>
                  <input
                    id="new-case-title"
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
                    <label
                      htmlFor="new-case-po"
                      className="block text-slate-300 mb-1 font-medium"
                    >
                      PO Number
                    </label>
                    <input
                      id="new-case-po"
                      type="text"
                      value={newPo}
                      onChange={(e) => setNewPo(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="new-case-supplier"
                      className="block text-slate-300 mb-1 font-medium"
                    >
                      Supplier Name
                    </label>
                    <input
                      id="new-case-supplier"
                      type="text"
                      value={newSupplier}
                      onChange={(e) => setNewSupplier(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="new-case-buyer"
                      className="block text-slate-300 mb-1 font-medium"
                    >
                      Buyer Name
                    </label>
                    <input
                      id="new-case-buyer"
                      type="text"
                      value={newBuyer}
                      onChange={(e) => setNewBuyer(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                    />
                  </div>
                </div>
                <div>
                  <label
                    htmlFor="new-case-desc"
                    className="block text-slate-300 mb-1 font-medium"
                  >
                    Case Description
                  </label>
                  <textarea
                    id="new-case-desc"
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

          {/* Benchmarks Dashboard Screen */}
          {activeTab === 'evaluation' && (
            <BenchmarkDashboard
              evalReport={evalReport}
              evalSuiteType={evalSuiteType}
              onRunEvaluation={handleRunEvaluation}
              loading={loading}
            />
          )}

          {/* Active Case Investigation Screens */}
          {caseDetail &&
            activeTab !== 'create_case' &&
            activeTab !== 'evaluation' && (
              <>
                {/* 1. CASE OVERVIEW HEADER */}
                <section
                  aria-label="Case Overview Header"
                  className="eos-panel eos-reveal eos-stagger-2 bg-slate-900/85 border border-slate-800 rounded-xl p-5 space-y-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-1.5 max-w-3xl">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-slate-950 text-sky-300 border border-slate-700">
                          CASE {caseDetail.po_number || caseDetail.id}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          ID: {caseDetail.id}
                        </span>
                        <span className="text-xs text-slate-400">
                          • Supplier:{' '}
                          <strong className="text-slate-200">
                            {caseDetail.supplier_name}
                          </strong>{' '}
                          → Buyer:{' '}
                          <strong className="text-slate-200">
                            {caseDetail.buyer_name}
                          </strong>
                        </span>
                      </div>
                      <h1 className="text-lg font-bold text-white">
                        {caseDetail.title}
                      </h1>
                      <p className="text-xs text-slate-300">
                        {caseDetail.description}
                      </p>
                    </div>

                    {/* Compact Status & Metadata Box */}
                    <div className="eos-card flex flex-col items-start sm:items-end gap-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 shrink-0">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                        STATUS & DECISION
                      </div>
                      <div className="flex items-center gap-2">
                        <OutcomeBadge outcome={dec?.outcome} />
                        {dec && <EpistemicBadge type={dec.epistemic_status} />}
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-slate-400 pt-1">
                        <span>Evidence: {caseDetail.evidence_items.length}</span>
                        <span>
                          Conflicts:{' '}
                          {caseDetail.conflicts.length +
                            caseDetail.historical_warnings.length}
                        </span>
                        <span>
                          Updated:{' '}
                          {new Date(caseDetail.updated_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 2. MEANINGFUL SUMMARY CARDS (Ordered, Received, Damaged, Conflicts, Evidence, Review) */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 pt-1">
                    {[
                      {
                        label: 'Ordered',
                        value: dec ? `${dec.ordered_quantity} units` : '—',
                        sub: 'Purchase Order',
                        tone: 'text-white',
                      },
                      {
                        label: 'Received',
                        value: dec ? `${dec.delivered_quantity} units` : '—',
                        sub: 'Delivery Challan',
                        tone: 'text-white',
                      },
                      {
                        label: 'Damaged',
                        value: dec
                          ? `${dec.verified_damaged_quantity} units`
                          : '—',
                        sub: 'Verified Damaged',
                        tone:
                          dec && dec.verified_damaged_quantity > 0
                            ? 'text-amber-300'
                            : 'text-emerald-300',
                      },
                      {
                        label: 'Conflicts',
                        value: String(
                          caseDetail.conflicts.length +
                            caseDetail.historical_warnings.length
                        ),
                        sub:
                          caseDetail.conflicts.length +
                            caseDetail.historical_warnings.length >
                          0
                            ? 'Contradictions found'
                            : 'No contradictions',
                        tone:
                          caseDetail.conflicts.length +
                            caseDetail.historical_warnings.length >
                          0
                            ? 'text-amber-300'
                            : 'text-emerald-300',
                      },
                      {
                        label: 'Evidence',
                        value: `${caseDetail.evidence_items.length} items`,
                        sub: 'PDF, Image, Voice',
                        tone: 'text-sky-300',
                      },
                      {
                        label: 'Review',
                        value:
                          dec?.outcome === 'manual_review_required' ||
                          dec?.outcome === 'insufficient_evidence'
                            ? 'Required'
                            : dec?.is_human_override
                            ? 'Reviewed'
                            : dec
                            ? 'Not Required'
                            : 'Pending',
                        sub: dec?.is_human_override
                          ? `By ${dec.human_reviewer}`
                          : 'Human-in-the-loop',
                        tone:
                          dec?.outcome === 'manual_review_required'
                            ? 'text-amber-300'
                            : 'text-emerald-300',
                      },
                    ].map((card) => (
                      <div
                        key={card.label}
                        className="eos-card p-3 rounded-lg bg-slate-950 border border-slate-800"
                      >
                        <div className="text-[11px] font-mono uppercase text-slate-400">
                          {card.label}
                        </div>
                        <div
                          className={`text-base font-bold font-mono mt-0.5 ${card.tone}`}
                        >
                          {card.value}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5 truncate">
                          {card.sub}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 3. 5-STAGE INVESTIGATION TIMELINE (with distinct Completed / Current / Needs Attention states) */}
                <section
                  aria-label="5-Stage Investigation Timeline"
                  className="eos-panel eos-reveal eos-stagger-3 bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-xs font-bold text-white">
                        Investigation Workflow (5-Stage Verification Pipeline)
                      </span>
                      <span className="text-xs text-slate-400 ml-2">
                        {GUIDED_STORY_STEPS[guidedStepIndex]?.description}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        handleGuidedStepClick(
                          (guidedStepIndex + 1) % GUIDED_STORY_STEPS.length
                        )
                      }
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 text-xs font-semibold border border-sky-500/35 transition"
                    >
                      <span>Next Investigation Step</span>
                      <ArrowRight className="w-3 h-3" aria-hidden="true" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5">
                    {GUIDED_STORY_STEPS.map((s, idx) => {
                      const st = getStageStatus(s.step);
                      return (
                        <button
                          key={s.step}
                          type="button"
                          onClick={() => handleGuidedStepClick(idx)}
                          className={`eos-interactive-card text-left p-3 rounded-lg border transition ${st.cls}`}
                        >
                          <div className="flex items-center justify-between gap-1 mb-1">
                            <span className="text-xs font-bold">{s.title}</span>
                          </div>
                          <div className="text-[11px] text-slate-400 truncate mb-2">
                            {s.subtitle}
                          </div>
                          <span
                            className={`inline-block text-[10px] font-mono px-1.5 py-0.5 rounded ${st.badgeCls}`}
                          >
                            {st.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>

                {/* Sub-Navigation Bar for Investigation Views */}
                <div
                  role="tablist"
                  aria-label="Case Investigation Views"
                  className="flex flex-wrap items-center gap-1.5 border-b border-slate-800 pb-3"
                >
                  {[
                    {
                      id: 'overview',
                      label: '1. Overview & Evidence',
                      icon: Layers,
                    },
                    {
                      id: 'upload',
                      label: '2. Upload Evidence',
                      icon: Upload,
                    },
                    {
                      id: 'timeline',
                      label: '3. Claims & [Why?] Provenance',
                      icon: Clock,
                    },
                    {
                      id: 'conflicts',
                      label: `4. Conflicts (${
                        caseDetail.conflicts.length +
                        caseDetail.historical_warnings.length
                      })`,
                      icon: AlertTriangle,
                    },
                    {
                      id: 'graph',
                      label: '5. Evidence Graph',
                      icon: GitBranch,
                    },
                    {
                      id: 'decision',
                      label: '6. Decision, Rules & Review',
                      icon: Scale,
                    },
                    {
                      id: 'audit',
                      label: `7. Audit Trail (${auditTrail?.events.length ?? 0})`,
                      icon: History,
                    },
                  ].map((t) => {
                    const Icon = t.icon;
                    const active = activeTab === t.id;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => setActiveTab(t.id as ActiveTab)}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                          active
                            ? 'bg-sky-500 text-slate-950 font-semibold shadow-sm'
                            : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                        <span>{t.label}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Empty State if Case Has No Uploaded Evidence Yet */}
                {caseDetail.evidence_items.length === 0 &&
                  activeTab !== 'upload' && (
                    <div className="p-8 rounded-xl bg-slate-900/70 border border-slate-800 text-center space-y-3">
                      <Upload
                        className="w-8 h-8 text-sky-400 mx-auto"
                        aria-hidden="true"
                      />
                      <h3 className="text-sm font-bold text-white">
                        No evidence uploaded yet.
                      </h3>
                      <p className="text-xs text-slate-400 max-w-md mx-auto">
                        Upload a purchase order, delivery challan, inspection image, or voice report to begin the investigation.
                      </p>
                      <button
                        type="button"
                        onClick={() => setActiveTab('upload')}
                        className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-semibold"
                      >
                        Upload Evidence Now
                      </button>
                    </div>
                  )}

                {/* TAB 1: OVERVIEW (Evidence-First + Conflict Summary + Decision Summary) */}
                {activeTab === 'overview' &&
                  caseDetail.evidence_items.length > 0 && (
                    <div className="eos-reveal eos-stagger-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
                      {/* Left Column: Pipeline Checklist + Quick Decision Card */}
                      <div className="space-y-5">
                        <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
                          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
                            VERIFICATION STAGE STATUS
                          </h3>
                          <div className="space-y-2 text-xs">
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
                                className="eos-card flex items-center justify-between p-2.5 rounded-lg bg-slate-950 border border-slate-800/80"
                              >
                                <span className="font-medium text-slate-200">
                                  {row.label}
                                </span>
                                {row.warn ? (
                                  <span className="text-amber-300 font-bold font-mono text-xs">
                                    ⚠ Needs Review (
                                    {caseDetail.conflicts.length +
                                      caseDetail.historical_warnings.length}
                                    )
                                  </span>
                                ) : row.ok ? (
                                  <span className="text-emerald-400 font-bold font-mono text-xs">
                                    ✓ Complete
                                  </span>
                                ) : (
                                  <span className="text-slate-500 font-mono text-xs">
                                    Not started
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Decision Summary Box */}
                        {dec && (
                          <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3 text-xs">
                            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                              <span className="font-mono uppercase font-bold text-slate-400">
                                DECISION SUMMARY
                              </span>
                              <OutcomeBadge outcome={dec.outcome} />
                            </div>
                            <p className="text-slate-200 leading-relaxed">
                              {dec.summary_reason}
                            </p>
                            <div className="eos-card p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                              <span className="text-[11px] font-semibold uppercase text-emerald-400 block">
                                Next Reviewer Step
                              </span>
                              <p className="text-slate-200">{dec.next_action}</p>
                            </div>
                            <div className="flex gap-2 pt-1">
                              <button
                                type="button"
                                onClick={() => setActiveTab('conflicts')}
                                className="flex-1 py-1.5 px-2.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-center"
                              >
                                View Conflicts
                              </button>
                              <button
                                type="button"
                                onClick={() => setActiveTab('decision')}
                                className="flex-1 py-1.5 px-2.5 rounded bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-center"
                              >
                                Review / Override
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Right 2 Columns: Evidence First Viewer + Top Claims with [Why?] */}
                      <div className="lg:col-span-2 space-y-5">
                        {/* Evidence Viewer Cards */}
                        <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                            <div>
                              <h3 className="text-sm font-bold text-white">
                                Submitted Evidence Artifacts ({caseDetail.evidence_items.length})
                              </h3>
                              <p className="text-xs text-slate-400">
                                Click any evidence item to inspect its extracted claims, SHA-256 / dHash, or open the original file.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setActiveTab('upload')}
                              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-xs font-medium"
                            >
                              + Add Evidence
                            </button>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {caseDetail.evidence_items.map((item) => {
                              const prov = item.extracted_payload?.provenance;
                              const rawUrl = api.rawEvidenceUrl(
                                caseDetail.id,
                                item.id
                              );
                              const ModIcon =
                                item.modality === 'image'
                                  ? ImageIcon
                                  : item.modality === 'audio'
                                  ? Mic
                                  : FileText;
                              return (
                                <div
                                  key={item.id}
                                  className="eos-interactive-card p-3.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-sky-500/50 flex flex-col justify-between gap-3 text-xs"
                                >
                                  <div className="space-y-1.5">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="inline-flex items-center gap-1.5 font-semibold text-sky-300">
                                        <ModIcon
                                          className="w-3.5 h-3.5"
                                          aria-hidden="true"
                                        />
                                        <span>
                                          {item.document_role
                                            .replace(/_/g, ' ')
                                            .toUpperCase()}
                                        </span>
                                      </span>
                                      <EpistemicBadge type={prov?.epistemic_type} />
                                    </div>
                                    <div className="font-bold text-white text-sm">
                                      {item.original_filename}
                                    </div>
                                    <div className="font-mono text-[11px] text-slate-400 space-y-0.5">
                                      <div>
                                        ID: {item.id} • Type:{' '}
                                        {item.modality.toUpperCase()} • Status:{' '}
                                        {item.processed_at
                                          ? 'Processed ✓'
                                          : 'Uploaded'}
                                      </div>
                                      <div>
                                        SHA-256: {item.sha256_hash.slice(0, 16)}…
                                        {item.perceptual_hash
                                          ? ` • dHash: ${item.perceptual_hash}`
                                          : ''}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-900">
                                    <button
                                      type="button"
                                      onClick={() => setInspectedEvidence(item)}
                                      className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-sky-300 border border-slate-700 font-medium"
                                    >
                                      Inspect Claims & Provenance
                                    </button>
                                    <a
                                      href={rawUrl}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="eos-btn-link inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 font-mono text-[11px]"
                                    >
                                      <span>Original File</span>
                                      <ExternalLink
                                        className="w-3 h-3"
                                        aria-hidden="true"
                                      />
                                    </a>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Key Extracted Claims with [Why?] Button */}
                        <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="text-sm font-bold text-white">
                                Extracted Claims & Provenance Trace
                              </h3>
                              <p className="text-xs text-slate-400">
                                Click <strong>[Why?]</strong> on any claim to see the exact evidence source, epistemic type, and downstream rule impact.
                              </p>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            {caseDetail.claims.slice(0, 8).map((c) => (
                              <div
                                key={c.claim_id}
                                className="eos-card p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between gap-2 text-xs"
                              >
                                <div className="space-y-0.5 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono text-[11px] text-slate-400">
                                      {c.provenance.document_role.replace(
                                        /_/g,
                                        ' '
                                      )}
                                    </span>
                                    <EpistemicBadge type={c.epistemic_type} />
                                  </div>
                                  <div className="font-mono font-bold text-white truncate">
                                    {c.attribute.replace(/_/g, ' ')}:{' '}
                                    {c.value !== null && c.value !== undefined
                                      ? `${c.value} ${c.unit || ''}`
                                      : 'Inconclusive'}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => setTracedClaim(c)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/35 font-mono font-semibold shrink-0"
                                >
                                  <HelpCircle
                                    className="w-3 h-3"
                                    aria-hidden="true"
                                  />
                                  <span>Why?</span>
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                {/* TAB 2: EVIDENCE VIEWER & UPLOAD */}
                {activeTab === 'upload' && (
                  <div className="eos-reveal eos-stagger-4 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
                        <h3 className="text-sm font-bold text-white">
                          Upload Multimodal Evidence File (PDF, PNG/JPG, WAV, JSON, CSV)
                        </h3>
                        <form
                          onSubmit={handleFileUpload}
                          className="space-y-4 text-xs"
                        >
                          <div>
                            <label
                              htmlFor="evidence-file-input"
                              className="block text-slate-300 mb-1 font-medium"
                            >
                              Select Evidence File (Max 25 MB, Validated by Magic Bytes)
                            </label>
                            <input
                              id="evidence-file-input"
                              type="file"
                              onChange={(e) =>
                                setUploadFile(e.target.files?.[0] || null)
                              }
                              className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-sky-500 file:text-slate-950"
                            />
                          </div>
                          <div>
                            <label
                              htmlFor="evidence-role-select"
                              className="block text-slate-300 mb-1 font-medium"
                            >
                              Evidence Role (Optional — Auto-Detected if omitted)
                            </label>
                            <select
                              id="evidence-role-select"
                              value={uploadRole}
                              onChange={(e) => setUploadRole(e.target.value)}
                              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                            >
                              <option value="">
                                Auto-detect from file & content
                              </option>
                              <option value="purchase_order">
                                Purchase Order (PO)
                              </option>
                              <option value="delivery_challan">
                                Delivery Challan / Packing Slip
                              </option>
                              <option value="invoice">Commercial Invoice</option>
                              <option value="inspection_image">
                                Product / Dock Inspection Image
                              </option>
                              <option value="voice_report">
                                Warehouse / Driver Voice Report
                              </option>
                            </select>
                          </div>
                          <button
                            type="submit"
                            disabled={!uploadFile || loading}
                            className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-semibold"
                          >
                            Upload & Compute SHA-256 / dHash
                          </button>
                        </form>
                      </div>

                      <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
                        <h3 className="text-sm font-bold text-white">
                          Add Manual Dock Note or Voice Transcript
                        </h3>
                        <form
                          onSubmit={handleManualSubmit}
                          className="space-y-4 text-xs"
                        >
                          <div>
                            <label
                              htmlFor="manual-role-select"
                              className="block text-slate-300 mb-1 font-medium"
                            >
                              Evidence Type
                            </label>
                            <select
                              id="manual-role-select"
                              value={manualRole}
                              onChange={(e) => setManualRole(e.target.value)}
                              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
                            >
                              <option value="voice_report">
                                Receiving Dock Voice Report
                              </option>
                              <option value="delivery_challan">
                                Delivery Note Text
                              </option>
                              <option value="purchase_order">
                                Purchase Order Text
                              </option>
                            </select>
                          </div>
                          <div>
                            <label
                              htmlFor="manual-statement-textarea"
                              className="block text-slate-300 mb-1 font-medium"
                            >
                              Statement / Structured Text
                            </label>
                            <textarea
                              id="manual-statement-textarea"
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
                  </div>
                )}

                {/* TAB 3: CLAIMS & [Why?] PROVENANCE TABLE */}
                {activeTab === 'timeline' && (
                  <div className="eos-panel eos-reveal eos-stagger-4 bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div>
                      <h3 className="text-sm font-bold text-white">
                        Normalized Cross-Modal Claims & Epistemic Provenance
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Every claim is linked to its source file, extraction method, and epistemic classification. Click <strong>[Why?]</strong> to trace a claim from the final decision down to the original evidence file.
                      </p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] uppercase">
                          <tr>
                            <th className="p-3">Entity / SKU</th>
                            <th className="p-3">Claim Attribute</th>
                            <th className="p-3">Extracted Value</th>
                            <th className="p-3">Epistemic Type</th>
                            <th className="p-3">Source Evidence</th>
                            <th className="p-3">Reason</th>
                            <th className="p-3 text-right">Traceability</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {caseDetail.claims.map((c) => (
                            <tr key={c.claim_id} className="hover:bg-slate-900/50">
                              <td className="p-3 font-mono text-sky-300">
                                {c.entity_key}
                              </td>
                              <td className="p-3 font-mono">{c.attribute}</td>
                              <td className="p-3 font-mono font-bold text-white">
                                {c.value !== null && c.value !== undefined
                                  ? `${c.value} ${c.unit || ''}`
                                  : 'INCONCLUSIVE'}
                              </td>
                              <td className="p-3">
                                <EpistemicBadge type={c.epistemic_type} />
                              </td>
                              <td className="p-3 font-mono text-[11px] text-slate-300">
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleInspectEvidenceById(
                                      c.provenance.evidence_id
                                    )
                                  }
                                  className="text-sky-400 hover:underline"
                                >
                                  {c.provenance.document_role} (
                                  {c.provenance.evidence_id})
                                </button>
                              </td>
                              <td className="p-3 text-slate-300">{c.reason}</td>
                              <td className="p-3 text-right">
                                <button
                                  type="button"
                                  onClick={() => setTracedClaim(c)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/35 font-mono font-semibold"
                                >
                                  <HelpCircle
                                    className="w-3 h-3"
                                    aria-hidden="true"
                                  />
                                  <span>Why?</span>
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
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

                {/* TAB 5: CONFLICT PRESENTATION */}
                {activeTab === 'conflicts' && (
                  <ConflictPresentationList
                    conflicts={caseDetail.conflicts}
                    historicalWarnings={caseDetail.historical_warnings}
                    onInspectEvidenceById={handleInspectEvidenceById}
                    onSelectCase={handleSelectCase}
                  />
                )}

                {/* TAB 6: DECISION PANEL, RULES & HUMAN REVIEW */}
                {activeTab === 'decision' && dec && (
                  <DecisionReviewPanel
                    decision={dec}
                    reviewerName={reviewerName}
                    setReviewerName={setReviewerName}
                    reviewOutcome={reviewOutcome}
                    setReviewOutcome={setReviewOutcome}
                    reviewAcceptedQty={reviewAcceptedQty}
                    setReviewAcceptedQty={setReviewAcceptedQty}
                    reviewDamagedQty={reviewDamagedQty}
                    setReviewDamagedQty={setReviewDamagedQty}
                    reviewNotes={reviewNotes}
                    setReviewNotes={setReviewNotes}
                    onSubmitOverride={handleHumanOverride}
                    onReviewEvidence={() => setActiveTab('overview')}
                    loading={loading}
                  />
                )}

                {/* TAB 7: CHRONOLOGICAL TAMPER-EVIDENT AUDIT TRAIL */}
                {activeTab === 'audit' && auditTrail && (
                  <AuditTrailPanel auditTrail={auditTrail} />
                )}
              </>
            )}
        </main>
      </div>

      {/* Interactive [Why?] Provenance Trace Modal */}
      <ProvenanceModal
        caseId={selectedCaseId}
        claim={tracedClaim}
        allEvidence={caseDetail?.evidence_items || []}
        allClaims={caseDetail?.claims || []}
        decision={dec}
        onClose={() => setTracedClaim(null)}
        onInspectEvidence={(item) => setInspectedEvidence(item)}
      />

      {/* Original Evidence & Cryptographic Provenance Drawer */}
      <EvidenceInspectorDrawer
        caseId={selectedCaseId}
        item={inspectedEvidence}
        onClose={() => setInspectedEvidence(null)}
      />
    </div>
  );
}

export default App;
