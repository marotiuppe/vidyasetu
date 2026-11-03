import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of } from 'rxjs';

import { SettingValue, SettingsApi } from './settings.api';
import { StudentsApi } from './students.api';

const API = '/api/v1/fees';

/** Most students one reminder mark call accepts. */
export const REMINDER_MARK_LIMIT = 200;

/** School settings the late-fee screen explains. */
export const LATE_FEE_KEYS = [
  'fees.late_fee_type',
  'fees.late_fee_amount',
  'fees.late_fee_grace_days',
  'fees.late_fee_max_paise',
] as const;

export const REMINDER_TEMPLATE_KEY = 'fees.reminder_template';

export type ConcessionKind = 'percent' | 'fixed';

export const CONCESSION_KINDS: ConcessionKind[] = ['percent', 'fixed'];

/** `value` is basis points (2500 = 25%) for percent, paise for fixed. */
export interface Concession {
  id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string | null;
  section_name: string | null;
  academic_year_id: number;
  name: string;
  kind: ConcessionKind;
  value: number;
  fee_head_id: number | null;
  fee_head_name: string | null;
  reason: string | null;
  active: boolean;
}

export interface ConcessionPage {
  items: Concession[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConcessionFilters {
  student_id?: number;
  academic_year_id?: number;
}

export interface NewConcession {
  student_id: number;
  academic_year_id: number;
  name: string;
  kind: ConcessionKind;
  value: number;
  fee_head_id?: number | null;
  reason?: string | null;
}

export interface ConcessionUpdate {
  name?: string;
  value?: number;
  reason?: string | null;
  active?: boolean;
}

/** Late-fee preview: `enabled` is false when the school's late-fee rule is off. */
export interface LateFeePreview {
  enabled: boolean;
  late_fee_type: string;
  items: LateFeeCandidate[];
  count: number;
  total_late_fee_paise: number;
}

/** One overdue invoice that has no late-fee invoice yet, with the fee it would get. */
export interface LateFeeCandidate {
  invoice_id: number;
  invoice_no: string;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string | null;
  section_name: string | null;
  title: string;
  due_date: string;
  balance_paise: number;
  late_fee_paise: number;
}

export interface LateFeeApplyInput {
  academic_year_id: number;
  /** Omit to apply to every invoice in the preview. */
  invoice_ids?: number[];
}

export interface LateFeeApplyResult {
  created: number;
  skipped: number;
}

export interface ReminderFilters {
  academic_year_id?: number;
  class_id?: number;
  min_balance_paise?: number;
  overdue_only?: boolean;
  days_before_due?: number;
}

export interface ReminderRow {
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  balance_paise: number;
  overdue_paise: number;
  oldest_due_date: string | null;
  last_reminded_at: string | null;
  reminder_count: number;
}

export interface ReminderPage {
  items: ReminderRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReminderMarkResult {
  marked: number;
}

/** Add only the set values (skips empty strings, zero, false, null). */
function toParams(
  values: Record<string, string | number | boolean | null | undefined>,
): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === '' || value === 0 || value === false)
      continue;
    params = params.set(key, String(value));
  }
  return params;
}

/** Reminder filters; overdue_only defaults to true on the server, so false must be sent explicitly. */
function reminderParams(f: ReminderFilters): HttpParams {
  return toParams({ ...f }).set('overdue_only', String(f.overdue_only ?? true));
}

/** Typed client for concessions, late fees and fee reminders, plus the fee settings they read. */
@Injectable({ providedIn: 'root' })
export class FeeToolsApi {
  private readonly http = inject(HttpClient);
  private readonly settings = inject(SettingsApi);
  private readonly students = inject(StudentsApi);

  concessions(f: ConcessionFilters, page: number, pageSize: number): Observable<ConcessionPage> {
    const params = toParams({ ...f, page, page_size: pageSize });
    return this.http.get<ConcessionPage>(`${API}/concessions`, { params });
  }

  createConcession(body: NewConcession): Observable<Concession> {
    return this.http.post<Concession>(`${API}/concessions`, body);
  }

  updateConcession(id: number, body: ConcessionUpdate): Observable<Concession> {
    return this.http.patch<Concession>(`${API}/concessions/${id}`, body);
  }

  latePreview(academicYearId: number): Observable<LateFeePreview> {
    const params = toParams({ academic_year_id: academicYearId });
    return this.http.post<LateFeePreview>(`${API}/late-fees/preview`, {}, { params });
  }

  lateApply(body: LateFeeApplyInput): Observable<LateFeeApplyResult> {
    return this.http.post<LateFeeApplyResult>(`${API}/late-fees/apply`, body);
  }

  reminders(f: ReminderFilters, page: number, pageSize: number): Observable<ReminderPage> {
    const params = reminderParams(f).set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<ReminderPage>(`${API}/reminders`, { params });
  }

  remindersCsv(f: ReminderFilters): Observable<Blob> {
    return this.http.get(`${API}/reminders/export`, {
      params: reminderParams(f),
      responseType: 'blob',
    });
  }

  markReminded(studentIds: number[]): Observable<ReminderMarkResult> {
    return this.http.post<ReminderMarkResult>(`${API}/reminders/mark`, { student_ids: studentIds });
  }

  saveBlob(blob: Blob, filename: string): void {
    this.students.saveBlob(blob, filename);
  }

  /**
   * Effective values of the given school settings (the school level, or the branch level for branch
   * users). A key that cannot be read is left out, so the caller can fall back to its own default.
   */
  settingValues(keys: readonly string[]): Observable<Partial<Record<string, SettingValue>>> {
    return this.settings.list('school').pipe(
      catchError(() => this.settings.list('branch')),
      map((items) => {
        const out: Partial<Record<string, SettingValue>> = {};
        for (const key of keys) {
          const item = items.find((i) => i.key === key);
          if (item) out[key] = item.value ?? item.default;
        }
        return out;
      }),
      catchError(() => of({} as Partial<Record<string, SettingValue>>)),
    );
  }
}
