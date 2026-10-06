import React, { useState } from 'react';
import { AuditEvent, AuditTrailResponse } from '../types';
import { CheckCircle2, ChevronDown, ChevronRight, History, ShieldAlert } from 'lucide-react';

interface AuditTrailPanelProps {
  auditTrail: AuditTrailResponse;
}

const HUMAN_READABLE_EVENT_LABELS: Record<string, string> = {
  CASE_CREATED: 'Case initialized',
  EVIDENCE_INGESTED: 'Evidence uploaded & hashed',
  EVIDENCE_EXTRACTED: 'Evidence processed & claims extracted',
  CLAIMS_NORMALIZED: 'Claims normalized to canonical schema',
  ENTITIES_RESOLVED: 'Shipment & SKU entities linked',
  CONFLICTS_DETECTED: 'Cross-modal conflict check completed',
  HISTORICAL_MATCH_CHECKED: 'Historical duplicate hash check completed',
  RULES_EVALUATED: 'Deterministic contract rules evaluated',
  DECISION_COMPUTED: 'Verification decision computed',
  HUMAN_REVIEW_OVERRIDE: 'Reviewer override recorded',
};

function formatEventSummary(ev: AuditEvent): string {
  if (HUMAN_READABLE_EVENT_LABELS[ev.event_type]) {
    const details = ev.details || {};
    if (ev.event_type === 'EVIDENCE_INGESTED' && details.filename) {
      return `Evidence uploaded (${details.filename})`;
    }
    if (ev.event_type === 'DECISION_COMPUTED' && details.outcome) {
      const outcomeStr = String(details.outcome).replace(/_/g, ' ');
      return `Decision reached: ${outcomeStr}`;
    }
    if (ev.event_type === 'HUMAN_REVIEW_OVERRIDE' && details.outcome) {
      return `Reviewer override → ${String(details.outcome).replace(/_/g, ' ')}`;
    }
    return HUMAN_READABLE_EVENT_LABELS[ev.event_type];
  }
  return ev.event_type.replace(/_/g, ' ').toLowerCase();
}

export function AuditTrailPanel({ auditTrail }: AuditTrailPanelProps) {
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <History className="w-4 h-4 text-sky-400" aria-hidden="true" />
            <span>Chronological Tamper-Evident Audit Trail</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Every ingestion, extraction, conflict check, rule evaluation, and human review is cryptographically chained (`SHA-256`).
          </p>
        </div>
        <div
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold ${
            auditTrail.chain_integrity.valid
              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-500/15 border-rose-500/40 text-rose-300'
          }`}
        >
          {auditTrail.chain_integrity.valid ? (
            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
          ) : (
            <ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
          )}
          <span>
            Chain Integrity: {auditTrail.chain_integrity.valid ? 'VERIFIED ✓' : 'TAMPERED ✗'} (
            {auditTrail.chain_integrity.event_count} events)
          </span>
        </div>
      </div>

      {/* Chronological Timeline */}
      <div className="relative pl-4 border-l-2 border-slate-800 space-y-3">
        {auditTrail.events.map((ev, idx) => {
          const isExpanded = Boolean(expandedIds[ev.id]);
          const timeStr = ev.created_at
            ? new Date(ev.created_at).toLocaleTimeString([], {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })
            : `Step ${idx + 1}`;
          const isHuman =
            ev.event_type.includes('HUMAN') ||
            (ev.actor &&
              ev.actor !== 'system' &&
              ev.actor !== 'demo_seeder' &&
              ev.actor !== 'pipeline');

          return (
            <div
              key={ev.id}
              className="relative rounded-lg bg-slate-950 border border-slate-800 p-3.5 text-xs"
            >
              {/* Timeline Dot */}
              <span
                aria-hidden="true"
                className={`absolute -left-[21px] top-4 w-2.5 h-2.5 rounded-full border-2 border-slate-950 ${
                  isHuman ? 'bg-sky-400' : 'bg-emerald-400'
                }`}
              />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                    {timeStr}
                  </span>
                  <span className="font-semibold text-white">
                    {formatEventSummary(ev)}
                  </span>
                  <span className="font-mono text-[11px] text-sky-300">
                    [{ev.event_type}]
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                      isHuman
                        ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30'
                        : 'bg-slate-900 text-slate-400 border border-slate-800'
                    }`}
                  >
                    Actor: {ev.actor}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {ev.duration_ms !== undefined && ev.duration_ms !== null && (
                    <span className="font-mono text-[11px] text-slate-400">
                      {ev.duration_ms} ms
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => toggleExpand(ev.id)}
                    aria-expanded={isExpanded}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 font-mono text-[11px]"
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-3 h-3" aria-hidden="true" />
                    ) : (
                      <ChevronRight className="w-3 h-3" aria-hidden="true" />
                    )}
                    <span>{isExpanded ? 'Hide Details' : 'Inspect Hash & Payload'}</span>
                  </button>
                </div>
              </div>

              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                  <pre className="text-[11px] font-mono text-slate-300 bg-slate-900/90 p-2.5 rounded border border-slate-800 overflow-x-auto">
                    {JSON.stringify(ev.details, null, 2)}
                  </pre>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-400">
                    <span>Previous Hash: {ev.previous_event_hash}</span>
                    <span className="text-emerald-400">Event SHA-256: {ev.event_hash}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
