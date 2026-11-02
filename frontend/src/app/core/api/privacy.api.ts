import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { saveBlob } from '../ui/download';

const API = '/api/v1';

// ---- Audit log -------------------------------------------------------------------------------

export interface AuditEntry {
  id: number;
  at: string;
  actor_user_id: number | null;
  actor_name: string | null;
  actor_role: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | number | null;
  outcome: string;
  ip: string | null;
  detail: unknown;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilters {
  from?: string;
  to?: string;
  action?: string;
  actor_id?: string;
  entity_type?: string;
}

// ---- Policies and consent --------------------------------------------------------------------

export type PolicyName = 'privacy' | 'terms';

export interface PolicyStatus {
  policy: PolicyName;
  version: string;
  accepted: boolean;
  accepted_at: string | null;
}

export interface PoliciesResponse {
  policies: PolicyStatus[];
  pending: boolean;
}

export const CONSENT_PURPOSES = [
  'data_processing',
  'communication',
  'photos',
  'government_ids',
] as const;
export type ConsentPurpose = (typeof CONSENT_PURPOSES)[number];
export type ConsentStatus = 'granted' | 'refused' | 'withdrawn' | 'none';
export type ConsentMethod = 'online' | 'paper' | 'in_person';

export interface CurrentConsent {
  purpose: ConsentPurpose;
  status: ConsentStatus;
  method: ConsentMethod | null;
  recorded_at: string | null;
}

export interface ConsentHistoryItem {
  id: number;
  purpose: ConsentPurpose;
  status: ConsentStatus;
  method: ConsentMethod | null;
  note: string | null;
  recorded_by_name: string | null;
  recorded_at: string;
}

export interface ConsentOverview {
  current: CurrentConsent[];
  history: ConsentHistoryItem[];
}

export interface ConsentInput {
  purpose: ConsentPurpose;
  status: 'granted' | 'refused' | 'withdrawn';
  method?: ConsentMethod;
  note?: string;
}

// ---- Data-rights requests --------------------------------------------------------------------

export type DataRequestType = 'access' | 'correction' | 'erasure';
export type DataRequestStatus = 'open' | 'in_progress' | 'completed' | 'rejected';

export interface DataRequest {
  id: number;
  type: DataRequestType;
  status: DataRequestStatus;
  message: string;
  response_note: string | null;
  student_id: number | null;
  student_name: string | null;
  requester_name: string | null;
  created_at: string;
  updated_at: string;
  due_on: string | null;
}

export interface DataRequestInput {
  type: DataRequestType;
  message: string;
  student_id?: number | null;
}

// ---- Two-factor sign-in ----------------------------------------------------------------------

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
}

export interface RecoveryCodes {
  recovery_codes: string[];
}

/** Typed client for audit, consent, data rights, exports and two-factor management. */
@Injectable({ providedIn: 'root' })
export class PrivacyApi {
  private readonly http = inject(HttpClient);

  audit(filters: AuditFilters, page: number, pageSize: number): Observable<AuditPage> {
    return this.http.get<AuditPage>(`${API}/audit`, {
      params: auditParams(filters).set('page', page).set('page_size', pageSize),
    });
  }

  auditCsv(filters: AuditFilters): Observable<Blob> {
    return this.http.get(`${API}/audit/export.csv`, {
      params: auditParams(filters),
      responseType: 'blob',
    });
  }

  policies(): Observable<PoliciesResponse> {
    return this.http.get<PoliciesResponse>(`${API}/consent/policies`);
  }

  acceptPolicy(policy: PolicyName, version: string): Observable<unknown> {
    return this.http.post(`${API}/consent/policies/accept`, { policy, version });
  }

  consents(studentId: number): Observable<ConsentOverview> {
    return this.http.get<ConsentOverview>(`${API}/students/${studentId}/consents`);
  }

  recordConsent(studentId: number, body: ConsentInput): Observable<unknown> {
    return this.http.post(`${API}/students/${studentId}/consents`, body);
  }

  createRequest(body: DataRequestInput): Observable<DataRequest> {
    return this.http.post<DataRequest>(`${API}/data-requests`, body);
  }

  myRequests(): Observable<DataRequest[]> {
    return this.http
      .get<DataRequest[] | { items: DataRequest[] }>(`${API}/data-requests/mine`)
      .pipe(map((res) => (Array.isArray(res) ? res : res.items)));
  }

  requests(status: DataRequestStatus | ''): Observable<DataRequest[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    return this.http
      .get<DataRequest[] | { items: DataRequest[] }>(`${API}/data-requests`, { params })
      .pipe(map((res) => (Array.isArray(res) ? res : res.items)));
  }

  updateRequest(
    id: number,
    body: { status: DataRequestStatus; response_note: string },
  ): Observable<DataRequest> {
    return this.http.patch<DataRequest>(`${API}/data-requests/${id}`, body);
  }

  /** Download the signed-in user's own data as a JSON file. */
  downloadMyData(): Observable<void> {
    return this.http
      .get(`${API}/me/export`, { responseType: 'blob' })
      .pipe(map((blob) => saveBlob(blob, 'my-data.json')));
  }

  downloadStudentData(studentId: number): Observable<void> {
    return this.http
      .get(`${API}/students/${studentId}/export`, { responseType: 'blob' })
      .pipe(map((blob) => saveBlob(blob, `student-${studentId}-data.json`)));
  }

  mfaSetup(password: string): Observable<MfaSetup> {
    return this.http.post<MfaSetup>(`${API}/auth/mfa/setup`, { password });
  }

  mfaEnable(code: string): Observable<RecoveryCodes> {
    return this.http.post<RecoveryCodes>(`${API}/auth/mfa/enable`, { code });
  }

  mfaDisable(password: string, code: string): Observable<unknown> {
    return this.http.post(`${API}/auth/mfa/disable`, { password, code });
  }

  mfaRecoveryCodes(password: string, code: string): Observable<RecoveryCodes> {
    return this.http.post<RecoveryCodes>(`${API}/auth/mfa/recovery-codes`, { password, code });
  }

  resetUserMfa(userId: number): Observable<unknown> {
    return this.http.post(`${API}/users/${userId}/mfa/reset`, {});
  }
}

function auditParams(filters: AuditFilters): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(filters)) {
    if (typeof value === 'string' && value.trim() !== '') params = params.set(key, value.trim());
  }
  return params;
}
