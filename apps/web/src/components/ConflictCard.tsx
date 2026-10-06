import React from 'react';
import { EvidenceConflict, HistoricalWarning } from '../types';
import { EpistemicBadge } from './EvidenceWidgets';
import { AlertTriangle, ExternalLink, History } from 'lucide-react';

interface ConflictSectionProps {
  conflicts: EvidenceConflict[];
  historicalWarnings: HistoricalWarning[];
  onInspectEvidenceById: (evidenceId: string) => void;
  onSelectCase: (caseId: string) => void;
}

export function ConflictPresentationList({
  conflicts,
  historicalWarnings,
  onInspectEvidenceById,
  onSelectCase,
}: ConflictSectionProps) {
  const formatRoleLabel = (role: string) =>
    role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  const formatConflictHeading = (conflictType: string) => {
    if (conflictType.includes('DAMAGE')) return 'DAMAGE QUANTITY CONFLICT';
    if (conflictType.includes('SHORT_DELIVERY') || conflictType.includes('QUANTITY'))
      return 'DELIVERY QUANTITY CONFLICT';
    if (conflictType.includes('INSUFFICIENT') || conflictType.includes('VISUAL'))
      return 'INSUFFICIENT VISUAL CORROBORATION';
    return conflictType.replace(/_/g, ' ');
  };

  return (
    <div className="eos-reveal eos-stagger-4 space-y-5">
      {/* 1. Cross-Modal Contradictions */}
      <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" aria-hidden="true" />
              <span>Cross-Modal Evidence Conflicts ({conflicts.length})</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Highlights where documents, inspection photos, and voice statements disagree on quantities or condition.
            </p>
          </div>
          <span
            className={`px-2.5 py-1 rounded text-xs font-mono font-semibold border ${
              conflicts.length > 0
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
            }`}
          >
            {conflicts.length > 0
              ? `⚠ ${conflicts.length} Conflict${conflicts.length > 1 ? 's' : ''} — Review Required`
              : '✓ Zero Conflicts Detected'}
          </span>
        </div>

        {conflicts.length === 0 ? (
          <div className="eos-card p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300">
            All submitted sources (Purchase Order, Delivery Challan, Inspection Image, and Voice Report) agree on quantities and item condition.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {conflicts.map((cnf) => (
              <div
                key={cnf.conflict_id}
                className="eos-card rounded-xl bg-slate-950 border border-amber-500/40 overflow-hidden"
              >
                {/* Conflict Top Banner */}
                <div className="px-4 py-3 bg-amber-500/10 border-b border-amber-500/20 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-300 font-mono font-bold text-xs">
                      ⚠ {formatConflictHeading(cnf.conflict_type)}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      ({cnf.entity_key})
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-500/40 text-[11px] font-mono font-semibold">
                      Severity: Review required ({cnf.severity.toUpperCase()})
                    </span>
                    <EpistemicBadge type={cnf.epistemic_type} />
                  </div>
                </div>

                {/* Conflict Body */}
                <div className="p-4 space-y-3 text-xs">
                  <p className="text-slate-200 font-medium">{cnf.description}</p>

                  {/* Structured Competing Sources Table */}
                  <div className="rounded-lg border border-slate-800 overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-900 text-slate-400 font-mono text-[11px] uppercase">
                        <tr>
                          <th className="py-2 px-3">Disagreeing Source</th>
                          <th className="py-2 px-3">Reported Value</th>
                          <th className="py-2 px-3">Evidence ID</th>
                          <th className="py-2 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80 bg-slate-950">
                        {cnf.competing_values.map((cv, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/50">
                            <td className="py-2.5 px-3 font-medium text-slate-200">
                              {formatRoleLabel(cv.document_role)}
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-amber-300">
                              {cv.value !== null && cv.value !== undefined
                                ? `${cv.value} ${
                                    cnf.attribute.includes('damage')
                                      ? 'damaged'
                                      : 'units'
                                  }`
                                : 'Inconclusive / Unclear'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-400">
                              {cv.evidence_id}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <button
                                type="button"
                                onClick={() => onInspectEvidenceById(cv.evidence_id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-sky-400 border border-slate-700 font-medium"
                              >
                                <span>View supporting evidence</span>
                                <ExternalLink className="w-3 h-3" aria-hidden="true" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Historical Duplicate / Reused Evidence Warnings */}
      <div className="eos-panel bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <History className="w-4 h-4 text-amber-400" aria-hidden="true" />
              <span>
                Historical Evidence Reuse Check (SHA-256 & 64-Bit Perceptual dHash)
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Compares uploaded photographs and documents against prior cases to detect exact or visually perturbed duplicates.
            </p>
          </div>
          <span
            className={`px-2.5 py-1 rounded text-xs font-mono font-semibold border ${
              historicalWarnings.length > 0
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
            }`}
          >
            {historicalWarnings.length > 0
              ? `⚠ ${historicalWarnings.length} Historical Match`
              : '✓ Unique Evidence Verified'}
          </span>
        </div>

        {historicalWarnings.length === 0 ? (
          <div className="eos-card p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300">
            ✓ All uploaded files and inspection images passed SHA-256 and 64-bit dHash uniqueness checks against prior disputes.
          </div>
        ) : (
          <div className="space-y-4">
            {historicalWarnings.map((w) => {
              const currentImgUrl = `/api/cases/${w.case_id}/evidence/${w.current_evidence_id}/raw`;
              const historicalImgUrl = `/api/cases/${w.historical_case_id}/evidence/${w.historical_evidence_id}/raw`;
              return (
                <div
                  key={w.match_id}
                  className="eos-card p-4 rounded-xl bg-amber-950/20 border border-amber-500/40 space-y-3.5 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 text-amber-200 border border-amber-500/40 font-bold font-mono">
                      ⚠ Potentially reused evidence
                    </span>
                    <span className="font-mono text-amber-200 bg-amber-950/60 px-2.5 py-1 rounded border border-amber-500/30">
                      Match: {w.match_type} • Similarity:{' '}
                      {(w.similarity_score * 100).toFixed(1)}% (Hamming Distance:{' '}
                      {w.hamming_distance ?? 0}/64)
                    </span>
                  </div>

                  <p className="text-slate-200">{w.warning_message}</p>

                  {/* Side-by-Side Visual Evidence Comparison */}
                  <div
                    aria-label="Side-by-side reused image comparison"
                    className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1"
                  >
                    {/* Left: Current Claim Image */}
                    <div className="eos-card rounded-lg bg-slate-950 border border-slate-800 p-3 space-y-2">
                      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1.5">
                        <span className="font-semibold text-sky-300 uppercase tracking-wider text-[11px] font-mono">
                          Current Claim Image
                        </span>
                        <span className="font-mono text-[11px] text-slate-400">
                          {w.current_evidence_id}
                        </span>
                      </div>
                      <div className="flex justify-center items-center bg-slate-900 rounded p-2.5 border border-slate-800 min-h-[140px]">
                        <img
                          src={currentImgUrl}
                          alt={`Current claim evidence ${w.current_evidence_id}`}
                          className="max-h-40 rounded object-contain"
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>Case: {w.case_id}</span>
                        <button
                          type="button"
                          onClick={() => onInspectEvidenceById(w.current_evidence_id)}
                          className="text-sky-400 hover:underline font-sans font-medium"
                        >
                          Inspect Current File →
                        </button>
                      </div>
                    </div>

                    {/* Right: Historical Prior-Claim Image */}
                    <div className="eos-card rounded-lg bg-slate-950 border border-amber-500/30 p-3 space-y-2">
                      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1.5">
                        <span className="font-semibold text-amber-300 uppercase tracking-wider text-[11px] font-mono">
                          Historical Image (Prior Claim)
                        </span>
                        <span className="font-mono text-[11px] text-slate-400">
                          {w.historical_evidence_id}
                        </span>
                      </div>
                      <div className="flex justify-center items-center bg-slate-900 rounded p-2.5 border border-slate-800 min-h-[140px]">
                        <img
                          src={historicalImgUrl}
                          alt={`Historical prior case evidence ${w.historical_evidence_id}`}
                          className="max-h-40 rounded object-contain"
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>Prior Case: {w.historical_case_id}</span>
                        <button
                          type="button"
                          onClick={() => onSelectCase(w.historical_case_id)}
                          className="text-amber-400 hover:underline font-sans font-medium"
                        >
                          Open Prior Case →
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2.5 pt-1">
                    <button
                      type="button"
                      onClick={() => onInspectEvidenceById(w.current_evidence_id)}
                      className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-sky-300 font-medium border border-slate-700"
                    >
                      View Current Evidence ({w.current_evidence_id})
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectCase(w.historical_case_id)}
                      className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-amber-300 font-medium border border-slate-700"
                    >
                      Open Prior Case ({w.historical_case_id})
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
