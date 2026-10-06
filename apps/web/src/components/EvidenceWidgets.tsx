import React from 'react';
import {
  EvidenceGraph,
  EvidenceItem,
  GraphNode,
  EpistemologicalType,
} from '../types';
import {
  FileText,
  Image as ImageIcon,
  Mic,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Cpu,
  Hash,
  ExternalLink,
  Layers,
} from 'lucide-react';

export function EpistemicBadge({ type }: { type?: EpistemologicalType | string | null }) {
  if (!type) return null;
  const styles: Record<string, string> = {
    FACT: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    INFERENCE: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    RULE: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    UNCERTAINTY: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold border ${
        styles[type] || 'bg-slate-800 text-slate-300 border-slate-700'
      }`}
    >
      {type}
    </span>
  );
}

export function OutcomeBadge({ outcome }: { outcome?: string | null }) {
  if (!outcome) {
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
        Pending Processing
      </span>
    );
  }
  const map: Record<string, { label: string; cls: string }> = {
    approved: {
      label: 'Approved',
      cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    },
    partially_approved: {
      label: 'Partially Approved',
      cls: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
    },
    manual_review_required: {
      label: 'Manual Review',
      cls: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    },
    disputed: {
      label: 'Disputed',
      cls: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    },
    insufficient_evidence: {
      label: 'Insufficient Evidence',
      cls: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
    },
  };
  const cfg = map[outcome] || {
    label: outcome,
    cls: 'bg-slate-800 text-slate-300 border-slate-700',
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${cfg.cls}`}
    >
      {cfg.label}
    </span>
  );
}

export function InteractiveEvidenceGraph({
  graph,
  onSelectEvidenceId,
}: {
  graph: EvidenceGraph;
  onSelectEvidenceId: (evidenceId: string) => void;
}) {
  const evidenceNodes = graph.nodes.filter((n) => n.node_type === 'evidence');
  const claimNodes = graph.nodes.filter((n) => n.node_type === 'claim');
  const entityNodes = graph.nodes.filter((n) => n.node_type === 'entity');
  const conflictNodes = graph.nodes.filter((n) => n.node_type === 'conflict');
  const decisionNodes = graph.nodes.filter((n) => n.node_type === 'decision');

  const renderNodeCard = (node: GraphNode) => {
    const isClickable =
      node.node_type === 'evidence' ||
      (node.node_type === 'claim' && node.metadata?.evidence_id);
    const targetEvId =
      node.node_type === 'evidence' ? node.id : node.metadata?.evidence_id;

    let borderStyle = 'border-slate-800 bg-slate-900/90';
    if (node.node_type === 'evidence')
      borderStyle = 'border-sky-500/40 bg-sky-950/20 hover:border-sky-400';
    if (node.node_type === 'claim')
      borderStyle = 'border-emerald-500/30 bg-emerald-950/15 hover:border-emerald-400';
    if (node.node_type === 'entity')
      borderStyle = 'border-indigo-500/40 bg-indigo-950/25';
    if (node.node_type === 'conflict')
      borderStyle = 'border-amber-500/50 bg-amber-950/25';
    if (node.node_type === 'decision')
      borderStyle = 'border-violet-500/50 bg-violet-950/30';

    return (
      <div
        key={node.id}
        onClick={() => {
          if (isClickable && targetEvId) onSelectEvidenceId(targetEvId);
        }}
        className={`p-3 rounded-lg border transition-all ${borderStyle} ${
          isClickable ? 'cursor-pointer shadow-sm hover:shadow-sky-500/10' : ''
        }`}
      >
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
            {node.node_type}
          </span>
          <EpistemicBadge type={node.epistemic_type} />
        </div>
        <div className="text-xs font-medium text-slate-100 break-words">
          {node.label}
        </div>
        {node.metadata?.confidence !== undefined && (
          <div className="mt-1.5 text-[11px] font-mono text-slate-400">
            Confidence: {(Number(node.metadata.confidence) * 100).toFixed(0)}%
          </div>
        )}
        {isClickable && (
          <div className="mt-1.5 text-[10px] text-sky-400 flex items-center gap-1">
            <span>Inspect provenance</span>
            <ExternalLink className="w-2.5 h-2.5" />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-900/60 border border-slate-800 rounded-lg p-3">
        <div className="text-xs text-slate-300">
          <span className="font-semibold text-white">Cross-Modal Provenance DAG:</span>{' '}
          Click any Evidence or Claim node to inspect its original source artifact, hash, and extraction payload.
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span>Nodes: {graph.nodes.length}</span>
          <span>Edges: {graph.edges.length}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Column 1: Raw Evidence Sources */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 border-b border-slate-800 pb-1.5">
            1. Source Evidence ({evidenceNodes.length})
          </div>
          {evidenceNodes.map(renderNodeCard)}
        </div>

        {/* Column 2: Normalized Claims */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b border-slate-800 pb-1.5">
            2. Extracted Claims ({claimNodes.length})
          </div>
          {claimNodes.map(renderNodeCard)}
        </div>

        {/* Column 3: Resolved Canonical Entities */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-indigo-400 border-b border-slate-800 pb-1.5">
            3. Resolved Entities ({entityNodes.length})
          </div>
          {entityNodes.map(renderNodeCard)}
        </div>

        {/* Column 4: Detected Contradictions */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-400 border-b border-slate-800 pb-1.5">
            4. Conflicts ({conflictNodes.length})
          </div>
          {conflictNodes.length === 0 ? (
            <div className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/40 text-xs text-slate-400">
              No cross-modal contradictions detected.
            </div>
          ) : (
            conflictNodes.map(renderNodeCard)
          )}
        </div>

        {/* Column 5: Deterministic Decision */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-violet-400 border-b border-slate-800 pb-1.5">
            5. Final Decision ({decisionNodes.length})
          </div>
          {decisionNodes.map(renderNodeCard)}
        </div>
      </div>
    </div>
  );
}

export function EvidenceInspectorDrawer({
  caseId,
  item,
  onClose,
}: {
  caseId: string;
  item: EvidenceItem | null;
  onClose: () => void;
}) {
  if (!item) return null;

  const prov = item.extracted_payload?.provenance;
  const rawUrl = `/api/cases/${caseId}/evidence/${item.id}/raw`;

  const ModalityIcon =
    item.modality === 'image'
      ? ImageIcon
      : item.modality === 'audio'
      ? Mic
      : FileText;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center gap-2.5">
          <ModalityIcon className="w-5 h-5 text-sky-400" />
          <div>
            <h3 className="text-sm font-semibold text-white">
              {item.original_filename}
            </h3>
            <p className="text-xs font-mono text-slate-400">
              ID: {item.id} • Role: {item.document_role}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="px-2.5 py-1 rounded text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200"
        >
          Close [ESC]
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Cryptographic & Perceptual Provenance */}
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Hash className="w-3.5 h-3.5 text-sky-400" />
              Cryptographic & Provenance Metadata
            </span>
            {prov && <EpistemicBadge type={prov.epistemic_type} />}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-slate-500 block">SHA-256 Hash:</span>
              <span className="font-mono text-[11px] text-slate-200 break-all">
                {item.sha256_hash}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Perceptual dHash (64-bit):</span>
              <span className="font-mono text-[11px] text-slate-200">
                {item.perceptual_hash || 'N/A (Non-image modality)'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Extraction Method:</span>
              <span className="font-mono text-[11px] text-sky-300">
                {prov?.extraction_method || item.extraction_metadata?.provider || 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Confidence & Location:</span>
              <span className="font-mono text-[11px] text-slate-200">
                {prov ? `${(prov.confidence * 100).toFixed(1)}% @ ${prov.location}` : 'N/A'}
              </span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-900 flex justify-end">
            <a
              href={rawUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium"
            >
              <span>Open Original Immutable Evidence Artifact</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        {/* Visual Preview for Images */}
        {item.modality === 'image' && (
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              Visual Evidence Preview
            </span>
            <div className="flex justify-center bg-slate-900 rounded p-2 border border-slate-800">
              <img
                src={rawUrl}
                alt={item.original_filename}
                className="max-h-56 rounded object-contain"
              />
            </div>
            {item.extracted_payload?.visual_summary && (
              <p className="text-xs text-slate-300 italic">
                “{item.extracted_payload.visual_summary}”
              </p>
            )}
          </div>
        )}

        {/* Audio Player & Transcript for Voice Reports */}
        {item.modality === 'audio' && (
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              Audio Recording & Extracted Transcript
            </span>
            <audio controls src={rawUrl} className="w-full h-9" />
            {item.extracted_payload?.transcript && (
              <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono">
                "{item.extracted_payload.transcript}"
              </div>
            )}
          </div>
        )}

        {/* Raw Snippet */}
        {prov?.raw_snippet && (
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-1.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              Verbatim Source Snippet
            </span>
            <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap bg-slate-900 p-2.5 rounded border border-slate-800">
              {prov.raw_snippet}
            </pre>
          </div>
        )}

        {/* Full Structured Extraction JSON */}
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-1.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
            Structured Extraction Payload (Validated Schema)
          </span>
          <pre className="text-[11px] font-mono text-emerald-300 overflow-x-auto bg-slate-900 p-3 rounded border border-slate-800">
            {JSON.stringify(item.extracted_payload, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
