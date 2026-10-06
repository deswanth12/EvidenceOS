import React, { useEffect } from 'react';
import {
  CaseDecision,
  EvidenceItem,
  NormalizedClaim,
  RuleEvaluationTrace,
} from '../types';
import { EpistemicBadge } from './EvidenceWidgets';
import {
  ArrowRight,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Mic,
  Scale,
  X,
} from 'lucide-react';

interface ProvenanceModalProps {
  caseId: string;
  claim: NormalizedClaim | null;
  allEvidence: EvidenceItem[];
  allClaims: NormalizedClaim[];
  decision?: CaseDecision | null;
  onClose: () => void;
  onInspectEvidence: (item: EvidenceItem) => void;
}

export function ProvenanceModal({
  caseId,
  claim,
  allEvidence,
  allClaims,
  decision,
  onClose,
  onInspectEvidence,
}: ProvenanceModalProps) {
  useEffect(() => {
    if (!claim) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [claim, onClose]);

  if (!claim) return null;

  // Find all claims that share the same attribute or entity to show all supporting/related sources
  const relatedClaims = allClaims.filter(
    (c) =>
      c.claim_id === claim.claim_id ||
      (c.attribute === claim.attribute && String(c.value) === String(claim.value))
  );
  const supportingEvidenceIds = Array.from(
    new Set(relatedClaims.map((c) => c.provenance.evidence_id))
  );
  const supportingItems = allEvidence.filter((ev) =>
    supportingEvidenceIds.includes(ev.id)
  );

  // Find rules that evaluated this claim attribute
  const matchingRules: RuleEvaluationTrace[] = (decision?.rule_traces || []).filter(
    (rt) => {
      const inputsStr = JSON.stringify(rt.inputs_used || {}).toLowerCase();
      return (
        rt.evidence_ids?.includes(claim.provenance.evidence_id) ||
        inputsStr.includes(claim.attribute.toLowerCase())
      );
    }
  );

  const getModalityIcon = (modality: string) => {
    if (modality === 'image') return ImageIcon;
    if (modality === 'audio') return Mic;
    return FileText;
  };

  const formatClaimLabel = (c: NormalizedClaim) => {
    const attr = c.attribute.replace(/_/g, ' ');
    const val =
      c.value !== null && c.value !== undefined ? String(c.value) : 'Inconclusive';
    return `${val} ${c.unit || ''} (${attr})`.trim();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="provenance-trace-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-[1px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono uppercase tracking-wider text-sky-400 block">
              End-to-End Provenance Trace (Decision → Rule → Claim → Evidence → File)
            </span>
            <h3 id="provenance-trace-title" className="text-sm font-bold text-white mt-0.5">
              Why did the system extract "{formatClaimLabel(claim)}"?
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close provenance trace"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Close</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs">
          {/* Breadcrumb Trace Chain */}
          <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300">
            <span className="px-2 py-0.5 rounded bg-violet-500/15 text-violet-300 border border-violet-500/30">
              Decision: {decision?.outcome?.replace(/_/g, ' ').toUpperCase() || 'PENDING'}
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span className="px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
              Rule: {matchingRules[0]?.rule_id || 'SLA_VERIFICATION'}
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              Claim: {claim.attribute}={String(claim.value)}
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30">
              Evidence: {claim.provenance.evidence_id}
            </span>
          </div>

          {/* CLAIM & TYPE Box */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-mono uppercase text-slate-400 block">
                CLAIM
              </span>
              <div className="text-sm font-bold text-white font-mono">
                {formatClaimLabel(claim)}
              </div>
              <div className="text-slate-400">
                Entity: <span className="font-mono text-sky-300">{claim.entity_key}</span>
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
              <span className="text-[11px] font-mono uppercase text-slate-400 block">
                EPISTEMIC TYPE & EXTRACTION REASON
              </span>
              <div className="flex items-center gap-2 pt-0.5">
                <EpistemicBadge type={claim.epistemic_type} />
                <span className="font-mono text-slate-300">
                  Method: {claim.provenance.extraction_method}
                </span>
              </div>
              <p className="text-slate-300 pt-1">{claim.reason}</p>
            </div>
          </div>

          {/* SUPPORTED BY Section */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2.5">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block">
              SUPPORTED BY ({supportingItems.length} Evidence Source
              {supportingItems.length === 1 ? '' : 's'})
            </span>
            <div className="space-y-2">
              {supportingItems.map((ev) => {
                const Icon = getModalityIcon(ev.modality);
                const rawUrl = `/api/cases/${caseId}/evidence/${ev.id}/raw`;
                return (
                  <div
                    key={ev.id}
                    className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-4 h-4 text-sky-400 shrink-0" aria-hidden="true" />
                      <div>
                        <div className="font-semibold text-white">
                          {ev.original_filename}
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          ID: {ev.id} • Role: {ev.document_role.replace(/_/g, ' ')} • SHA-256:{' '}
                          {ev.sha256_hash.slice(0, 12)}…
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          onClose();
                          onInspectEvidence(ev);
                        }}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 font-medium"
                      >
                        Inspect Payload
                      </button>
                      <a
                        href={rawUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/30 font-medium"
                      >
                        <span>Original File</span>
                        <ExternalLink className="w-3 h-3" aria-hidden="true" />
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Inline Highlighted Source Snippet */}
          {claim.provenance.raw_snippet && (
            <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-mono uppercase text-amber-300 font-semibold block">
                  INLINE SOURCE HIGHLIGHT (@ {claim.provenance.location || 'Document'})
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  Exact line supporting {claim.attribute}={String(claim.value)}
                </span>
              </div>
              <div className="rounded border border-slate-800 bg-slate-900 divide-y divide-slate-800/60 font-mono text-xs overflow-hidden">
                {String(claim.provenance.raw_snippet)
                  .split(/\r?\n/)
                  .filter((l) => l.trim().length > 0)
                  .map((line, idx, arr) => {
                    const upper = line.toUpperCase();
                    const skuClean = claim.entity_key.replace('ITEM:', '').toUpperCase();
                    const valStr =
                      claim.value !== null && claim.value !== undefined
                        ? String(claim.value).toUpperCase()
                        : '';
                    const isMatch =
                      arr.length === 1 ||
                      upper.includes('ITEM |') ||
                      upper.includes(skuClean) ||
                      (valStr.length > 0 && upper.includes(valStr)) ||
                      upper.includes('DAMAGED') ||
                      upper.includes('ORDERED') ||
                      upper.includes('DELIVERED');
                    return (
                      <div
                        key={idx}
                        className={`px-3 py-1.5 flex items-start justify-between gap-3 ${
                          isMatch
                            ? 'bg-amber-500/20 border-l-4 border-amber-400 text-amber-100 font-semibold'
                            : 'text-slate-300'
                        }`}
                      >
                        <div className="flex items-start gap-2.5 min-w-0">
                          <span className="text-[10px] text-slate-500 select-none shrink-0 pt-0.5">
                            L{String(idx + 1).padStart(2, '0')}
                          </span>
                          <span className="break-all">{line}</span>
                        </div>
                        {isMatch && (
                          <span className="shrink-0 px-1.5 py-0.5 rounded bg-amber-500/25 text-amber-200 border border-amber-400/40 text-[10px]">
                            ← Highlighted Claim Line
                          </span>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Downstream Rule Impact */}
          {matchingRules.length > 0 && (
            <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-[11px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                <Scale className="w-3.5 h-3.5 text-indigo-400" aria-hidden="true" />
                DOWNSTREAM DETERMINISTIC RULES USING THIS CLAIM
              </span>
              {matchingRules.map((rt) => (
                <div
                  key={rt.rule_id}
                  className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-start justify-between gap-3"
                >
                  <div>
                    <div className="font-mono font-semibold text-slate-200">
                      {rt.rule_id}: {rt.rule_name}
                    </div>
                    <p className="text-slate-400 mt-0.5">{rt.explanation}</p>
                  </div>
                  <span
                    className={`font-mono font-bold shrink-0 ${
                      rt.passed ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {rt.passed ? 'PASS ✓' : 'REVIEW ⚠'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
