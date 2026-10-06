import {
  AuditTrailResponse,
  CaseDetail,
  CaseSummary,
  DecisionOutcome,
  EvaluationReport,
  EvidenceItem,
} from './types';

const API_BASE = '/api';

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errText = res.statusText;
    try {
      const body = await res.json();
      errText = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(errText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listCases: async (): Promise<CaseSummary[]> => {
    const res = await fetch(`${API_BASE}/cases`);
    return handleJson<CaseSummary[]>(res);
  },

  getCaseDetail: async (caseId: string): Promise<CaseDetail> => {
    const res = await fetch(`${API_BASE}/cases/${caseId}`);
    return handleJson<CaseDetail>(res);
  },

  createCase: async (payload: {
    title: string;
    description?: string;
    supplier_name?: string;
    buyer_name?: string;
    po_number?: string;
    max_auto_approve_damage_ratio?: number;
    min_confidence_threshold?: number;
  }): Promise<CaseSummary> => {
    const res = await fetch(`${API_BASE}/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleJson<CaseSummary>(res);
  },

  uploadEvidence: async (
    caseId: string,
    file: File,
    documentRole?: string
  ): Promise<EvidenceItem> => {
    const formData = new FormData();
    formData.append('file', file);
    if (documentRole) {
      formData.append('document_role', documentRole);
    }
    const res = await fetch(`${API_BASE}/cases/${caseId}/evidence`, {
      method: 'POST',
      body: formData,
    });
    return handleJson<EvidenceItem>(res);
  },

  addManualEvidence: async (
    caseId: string,
    payload: { filename: string; document_role: string; text_content: string }
  ): Promise<EvidenceItem> => {
    const res = await fetch(`${API_BASE}/cases/${caseId}/evidence/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleJson<EvidenceItem>(res);
  },

  processCase: async (caseId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/cases/${caseId}/process`, {
      method: 'POST',
    });
    return handleJson<any>(res);
  },

  getAuditTrail: async (caseId: string): Promise<AuditTrailResponse> => {
    const res = await fetch(`${API_BASE}/cases/${caseId}/audit`);
    return handleJson<AuditTrailResponse>(res);
  },

  submitHumanReview: async (
    caseId: string,
    payload: {
      outcome: DecisionOutcome;
      reviewer: string;
      notes: string;
      accepted_quantity?: number;
      verified_damaged_quantity?: number;
    }
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/cases/${caseId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleJson<any>(res);
  },

  seedDemoCases: async (): Promise<{ seeded_cases: number; case_ids: string[] }> => {
    const res = await fetch(`${API_BASE}/demo/seed`, { method: 'POST' });
    return handleJson<{ seeded_cases: number; case_ids: string[] }>(res);
  },

  runEvaluation: async (
    suite: 'heldout_150' | 'extended_60' | 'canonical_5' = 'extended_60'
  ): Promise<EvaluationReport> => {
    const res = await fetch(`${API_BASE}/evaluation/run?suite=${suite}`);
    return handleJson<EvaluationReport>(res);
  },

  rawEvidenceUrl: (caseId: string, evidenceId: string): string =>
    `${API_BASE}/cases/${caseId}/evidence/${evidenceId}/raw`,
};
