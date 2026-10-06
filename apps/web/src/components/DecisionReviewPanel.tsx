import React from 'react';
import { CaseDecision, DecisionOutcome } from '../types';
import { EpistemicBadge, OutcomeBadge } from './EvidenceWidgets';
import { Cpu, Scale, ShieldCheck, UserCheck } from 'lucide-react';

interface DecisionReviewPanelProps {
  decision: CaseDecision;
  reviewerName: string;
  setReviewerName: (v: string) => void;
  reviewOutcome: DecisionOutcome;
  setReviewOutcome: (v: DecisionOutcome) => void;
  reviewAcceptedQty: number;
  setReviewAcceptedQty: (v: number) => void;
  reviewDamagedQty: number;
  setReviewDamagedQty: (v: number) => void;
  reviewNotes: string;
  setReviewNotes: (v: string) => void;
  onSubmitOverride: (e: React.FormEvent) => void;
  onReviewEvidence: () => void;
  loading: boolean;
}

export function DecisionReviewPanel({
  decision,
  reviewerName,
  setReviewerName,
  reviewOutcome,
  setReviewOutcome,
  reviewAcceptedQty,
  setReviewAcceptedQty,
  reviewDamagedQty,
  setReviewDamagedQty,
  reviewNotes,
  setReviewNotes,
  onSubmitOverride,
  onReviewEvidence,
  loading,
}: DecisionReviewPanelProps) {
  return (
    <div className="space-y-6">
      {/* Top Decision Panel */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                DECISION
              </span>
              {decision.is_human_override ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/35 text-[11px] font-mono font-semibold">
                  <UserCheck className="w-3 h-3" aria-hidden="true" />
                  <span>Decision Source: Human Reviewer ({decision.human_reviewer})</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-mono">
                  <Cpu className="w-3 h-3 text-sky-400" aria-hidden="true" />
                  <span>Decision Source: Deterministic Rule Engine</span>
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 pt-1">
              <OutcomeBadge outcome={decision.outcome} />
              <EpistemicBadge type={decision.epistemic_status} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onReviewEvidence}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 text-xs font-semibold transition"
            >
              Review Evidence
            </button>
            <a
              href="#human-override-form"
              className="px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-semibold transition"
            >
              Override Decision
            </a>
          </div>
        </div>

        {/* Why? Bullet List */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="md:col-span-2 p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
              Why did the system reach this decision?
            </span>
            <p className="text-slate-200 leading-relaxed">{decision.summary_reason}</p>
            {decision.detailed_explanation && decision.detailed_explanation.length > 0 && (
              <ul className="list-disc list-inside space-y-1 text-slate-300 pt-1">
                {decision.detailed_explanation.map((line, idx) => (
                  <li key={idx}>{line}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 block">
              Recommended Reviewer Action
            </span>
            <p className="text-slate-200 leading-relaxed">{decision.next_action}</p>
            <div className="pt-2 border-t border-slate-800 space-y-1 font-mono text-[11px] text-slate-400">
              <div>
                Ordered: <strong className="text-white">{decision.ordered_quantity} units</strong>
              </div>
              <div>
                Delivered: <strong className="text-white">{decision.delivered_quantity} units</strong>
              </div>
              <div>
                Verified Damaged:{' '}
                <strong className="text-white">{decision.verified_damaged_quantity} units</strong>
              </div>
              <div>
                Settlement Adjustment:{' '}
                <strong className="text-emerald-300">
                  ${decision.recommended_payout_adjustment_usd.toFixed(2)}
                </strong>
              </div>
            </div>
          </div>
        </div>

        {/* If Human Override was applied, display explicit audit box */}
        {decision.is_human_override && (
          <div className="p-4 rounded-lg bg-sky-950/25 border border-sky-500/40 text-xs space-y-1">
            <div className="font-semibold text-sky-300 flex items-center justify-between">
              <span>Human Reviewer Override Recorded by {decision.human_reviewer}</span>
              <span className="font-mono text-[11px]">
                {new Date(decision.decided_at).toLocaleString()}
              </span>
            </div>
            <p className="text-slate-200">
              <strong>Reviewer Note:</strong> {decision.human_override_notes}
            </p>
          </div>
        )}
      </div>

      {/* Bottom Grid: Deterministic Rule Trace + Human Override Form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Scale className="w-4 h-4 text-indigo-400" aria-hidden="true" />
                <span>Deterministic Contract & SLA Rule Evaluation Trace</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluated deterministically in Python over normalized claims—never delegated to an LLM.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {decision.rule_traces.map((rt) => (
              <div
                key={rt.rule_id}
                className={`p-3.5 rounded-lg border text-xs ${
                  rt.passed
                    ? 'bg-slate-950 border-emerald-500/30'
                    : 'bg-amber-950/15 border-amber-500/40'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-bold text-slate-100">
                    {rt.rule_id} — {rt.rule_name}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] ${
                      rt.passed
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    }`}
                  >
                    {rt.passed ? 'PASS ✓' : 'REQUIRES REVIEW ⚠'}
                  </span>
                </div>
                <p className="text-slate-300 mb-2">{rt.explanation}</p>
                <pre className="text-[11px] font-mono text-slate-400 bg-slate-900/90 p-2 rounded border border-slate-800 overflow-x-auto">
                  Inputs: {JSON.stringify(rt.inputs_used)}
                </pre>
              </div>
            ))}
          </div>
        </div>

        {/* Human Review Form */}
        <div
          id="human-override-form"
          className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4"
        >
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <UserCheck className="w-4 h-4 text-sky-400" aria-hidden="true" />
            <div>
              <h3 className="text-sm font-bold text-white">
                Human Adjudicator Review & Override
              </h3>
              <p className="text-[11px] text-slate-400">
                Overrides are attributed to the human reviewer in the tamper-evident audit trail.
              </p>
            </div>
          </div>

          <form onSubmit={onSubmitOverride} className="space-y-3 text-xs">
            <div>
              <label
                htmlFor="reviewer-id-input"
                className="block text-slate-300 mb-1 font-medium"
              >
                Reviewer Identifier
              </label>
              <input
                id="reviewer-id-input"
                type="text"
                required
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
              />
            </div>
            <div>
              <label
                htmlFor="override-decision-select"
                className="block text-slate-300 mb-1 font-medium"
              >
                Review Decision
              </label>
              <select
                id="override-decision-select"
                value={reviewOutcome}
                onChange={(e) => setReviewOutcome(e.target.value as DecisionOutcome)}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
              >
                <option value="approved">Approved</option>
                <option value="partially_approved">Partially Approved</option>
                <option value="disputed">Disputed / Rejected</option>
                <option value="manual_review_required">Keep in Manual Review</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label
                  htmlFor="accepted-units-input"
                  className="block text-slate-300 mb-1 font-medium"
                >
                  Accepted Units
                </label>
                <input
                  id="accepted-units-input"
                  type="number"
                  value={reviewAcceptedQty}
                  onChange={(e) => setReviewAcceptedQty(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
                />
              </div>
              <div>
                <label
                  htmlFor="damaged-units-input"
                  className="block text-slate-300 mb-1 font-medium"
                >
                  Verified Damaged
                </label>
                <input
                  id="damaged-units-input"
                  type="number"
                  value={reviewDamagedQty}
                  onChange={(e) => setReviewDamagedQty(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white font-mono"
                />
              </div>
            </div>
            <div>
              <label
                htmlFor="override-notes-textarea"
                className="block text-slate-300 mb-1 font-medium"
              >
                Override Reason & Evidence References *
              </label>
              <textarea
                id="override-notes-textarea"
                rows={3}
                required
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Cite physical dock count or supporting evidence IDs..."
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-white"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !reviewNotes.trim()}
              className="w-full py-2 rounded-lg bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-semibold transition"
            >
              Record Human Review Decision
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
