import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Gender, Relation, StudentCredential } from './students.api';

const API = '/api/v1';

export type AdmissionStatus = 'enquiry' | 'applied' | 'admitted' | 'enrolled' | 'rejected';
export type AdmissionSource = 'enquiry' | 'online' | 'walk_in';

export const ADMISSION_STATUSES: AdmissionStatus[] = [
  'enquiry',
  'applied',
  'admitted',
  'enrolled',
  'rejected',
];
export const ADMISSION_SOURCES: AdmissionSource[] = ['enquiry', 'online', 'walk_in'];

/** Document types and the size limit the server enforces (checked again here for a quick message). */
export const DOCUMENT_TYPES = ['application/pdf', 'image/png', 'image/jpeg'] as const;
export const DOCUMENT_MAX_BYTES = 2 * 1024 * 1024;
export const DOCUMENT_MAX_COUNT = 10;

/** One enquiry or application as the staff screens receive it. */
export interface AdmissionApp {
  id: number;
  branch_id: number;
  branch_name: string;
  first_name: string;
  last_name: string;
  gender: Gender | null;
  date_of_birth: string | null;
  class_id: number | null;
  class_name: string | null;
  academic_year_id: number | null;
  guardian_name: string;
  guardian_phone: string;
  guardian_email: string | null;
  guardian_relation: Relation;
  address: string | null;
  previous_school: string | null;
  source: AdmissionSource;
  status: AdmissionStatus;
  notes: string | null;
  rejection_reason: string | null;
  /** Set once the application is converted, when the server returns it. */
  student_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface AdmissionDocument {
  id: number;
  name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface AdmissionDetail extends AdmissionApp {
  documents: AdmissionDocument[];
}

export interface AdmissionPage {
  items: AdmissionApp[];
  total: number;
  page: number;
  page_size: number;
}

/** Count of applications per status (within the caller's scope). */
export type AdmissionSummary = Partial<Record<AdmissionStatus, number>>;

export interface AdmissionFilters {
  status?: AdmissionStatus | '';
  branch_id?: number | null;
  q?: string;
}

/** Fields the staff form sends. `branch_id` is only used when the application is created. */
export interface AdmissionInput {
  first_name: string;
  last_name: string;
  gender: Gender | null;
  date_of_birth: string | null;
  class_id: number | null;
  academic_year_id: number | null;
  guardian_name: string;
  guardian_phone: string;
  guardian_email: string | null;
  guardian_relation: Relation;
  address: string | null;
  previous_school: string | null;
  notes: string | null;
}

export interface AdmissionCreate extends AdmissionInput {
  branch_id?: number | null;
  source?: AdmissionSource;
}

export type AdmissionUpdate = Partial<AdmissionInput>;

export interface ConvertInput {
  class_id: number;
  section_id: number | null;
  academic_year_id: number;
  admission_no: string;
  admission_date: string | null;
}

/** Student created from an admitted application. Logins are shown once, like on the student form. */
export interface ConvertResult {
  student_id: number;
  credentials?: StudentCredential[] | null;
}

/** What the public apply page shows for one school (no personal data). */
export interface PublicAdmissionInfo {
  school_name: string;
  branches: { id: number; name: string }[];
  classes: { id: number; branch_id: number; name: string }[];
  open: boolean;
}

/** Body of the public application form. `website` is a honeypot that must stay empty. */
export interface PublicApplication {
  branch_id: number;
  class_id: number | null;
  first_name: string;
  last_name: string;
  gender: Gender | null;
  date_of_birth: string | null;
  guardian_name: string;
  guardian_phone: string;
  guardian_email: string | null;
  guardian_relation: Relation;
  address: string | null;
  previous_school: string | null;
  consent: true;
  website: string;
}

/** Typed client for the staff admissions screens. */
@Injectable({ providedIn: 'root' })
export class AdmissionsApi {
  private readonly http = inject(HttpClient);

  list(filters: AdmissionFilters, page: number, pageSize: number): Observable<AdmissionPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (filters.status) params = params.set('status', filters.status);
    if (filters.branch_id) params = params.set('branch_id', filters.branch_id);
    if (filters.q?.trim()) params = params.set('q', filters.q.trim());
    return this.http.get<AdmissionPage>(`${API}/admissions/applications`, { params });
  }

  summary(branchId: number | null): Observable<AdmissionSummary> {
    let params = new HttpParams();
    if (branchId) params = params.set('branch_id', branchId);
    return this.http.get<AdmissionSummary>(`${API}/admissions/summary`, { params });
  }

  get(id: number): Observable<AdmissionDetail> {
    return this.http.get<AdmissionDetail>(`${API}/admissions/applications/${id}`);
  }

  create(body: AdmissionCreate): Observable<AdmissionApp> {
    return this.http.post<AdmissionApp>(`${API}/admissions/applications`, body);
  }

  update(id: number, body: AdmissionUpdate): Observable<AdmissionApp> {
    return this.http.patch<AdmissionApp>(`${API}/admissions/applications/${id}`, body);
  }

  setStatus(id: number, status: AdmissionStatus, reason?: string): Observable<AdmissionApp> {
    return this.http.post<AdmissionApp>(`${API}/admissions/applications/${id}/status`, {
      status,
      reason: reason ?? null,
    });
  }

  uploadDocument(id: number, file: File, name: string): Observable<AdmissionDocument> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('name', name);
    return this.http.post<AdmissionDocument>(
      `${API}/admissions/applications/${id}/documents`,
      form,
    );
  }

  downloadDocument(id: number, docId: number): Observable<Blob> {
    return this.http.get(`${API}/admissions/applications/${id}/documents/${docId}`, {
      responseType: 'blob',
    });
  }

  deleteDocument(id: number, docId: number): Observable<void> {
    return this.http.delete<void>(`${API}/admissions/applications/${id}/documents/${docId}`);
  }

  convert(id: number, body: ConvertInput): Observable<ConvertResult> {
    return this.http.post<ConvertResult>(`${API}/admissions/applications/${id}/convert`, body);
  }
}

/** Public, sign-in free calls for the online application form of one school. */
@Injectable({ providedIn: 'root' })
export class PublicAdmissionsApi {
  private readonly http = inject(HttpClient);

  info(code: string): Observable<PublicAdmissionInfo> {
    return this.http.get<PublicAdmissionInfo>(
      `${API}/public/schools/${encodeURIComponent(code)}/admissions`,
    );
  }

  apply(code: string, body: PublicApplication): Observable<{ reference: string }> {
    return this.http.post<{ reference: string }>(
      `${API}/public/schools/${encodeURIComponent(code)}/applications`,
      body,
    );
  }
}
