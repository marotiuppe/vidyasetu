import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

const API = '/api/v1';

export type PromotionAction = 'promoted' | 'detained' | 'left' | 'passed_out' | 'transferred';

export const PROMOTION_ACTIONS: PromotionAction[] = [
  'promoted',
  'detained',
  'left',
  'passed_out',
  'transferred',
];

/** One active student in the chosen class and year, with the server's suggested move. */
export interface PromotionCandidate {
  student_id: number;
  name: string;
  admission_no: string;
  roll_no: number | null;
  from_class: string | null;
  from_section: string | null;
  suggested_action: PromotionAction;
  suggested_to_class_id: number | null;
  suggested_to_class_name: string | null;
  suggested_to_branch_name: string | null;
  /** The suggested class is in another branch: only the school owner may apply it. */
  needs_owner: boolean;
  dues_paise: number;
  already_enrolled: boolean;
}

/** A class the signed-in user may move students into. */
export interface PromotionClassOption {
  id: number;
  name: string;
  branch_id: number;
  branch_name: string;
  level: number;
}

export interface PromotionSection {
  id: number;
  class_id: number;
  name: string;
}

export interface PromotionPreview {
  candidates: PromotionCandidate[];
  /** More students exist than the server returns in one preview. */
  truncated: boolean;
  class_options: PromotionClassOption[];
  sections: PromotionSection[];
}

export interface PromotionPreviewInput {
  from_year_id: number;
  to_year_id: number;
  class_id: number;
  section_id?: number;
}

export interface PromotionItemInput {
  student_id: number;
  action: PromotionAction;
  to_class_id?: number;
  to_section_id?: number;
}

export interface PromotionApplyInput {
  from_year_id: number;
  to_year_id: number;
  carry_over: boolean;
  due_date?: string;
  items: PromotionItemInput[];
}

export interface PromotionSkip {
  student_id: number;
  reason: string;
}

/** One applied (or undone) promotion run, as the apply and undo calls return it. */
export interface PromotionBatch {
  id: number;
  created_at: string;
  undo_until: string;
  undone_at?: string | null;
  from_year_id?: number;
  to_year_id?: number;
  carry_over?: boolean;
  promoted: number;
  detained: number;
  left: number;
  passed_out: number;
  transferred: number;
  carried_invoices: number;
  carried_paise: number;
  skipped?: PromotionSkip[];
}

export interface PromotionBatchItem {
  student_id: number;
  name: string;
  action: PromotionAction;
  from_class: string | null;
  to_class: string | null;
  carried_paise: number;
}

export interface PromotionBatchDetail extends PromotionBatch {
  items: PromotionBatchItem[];
}

export interface PromotionBatchPage {
  items: PromotionBatch[];
  total: number;
  page: number;
  page_size: number;
}

/** Typed client for the year-end promotion screens (staff roles only). */
@Injectable({ providedIn: 'root' })
export class PromotionApi {
  private readonly http = inject(HttpClient);

  preview(body: PromotionPreviewInput): Observable<PromotionPreview> {
    return this.http.post<PromotionPreview>(`${API}/promotion/preview`, body);
  }

  apply(body: PromotionApplyInput): Observable<PromotionBatch> {
    return this.http.post<PromotionBatch>(`${API}/promotion/apply`, body);
  }

  /**
   * The list endpoint is read as a page. A bare array is accepted too, so the screen works
   * whichever shape the server returns.
   */
  batches(page: number, pageSize: number): Observable<PromotionBatchPage> {
    const params = new HttpParams().set('page', page).set('page_size', pageSize);
    return this.http
      .get<PromotionBatchPage | PromotionBatch[]>(`${API}/promotion/batches`, { params })
      .pipe(
        map((res) =>
          Array.isArray(res) ? { items: res, total: res.length, page, page_size: pageSize } : res,
        ),
      );
  }

  batch(id: number): Observable<PromotionBatchDetail> {
    return this.http.get<PromotionBatchDetail>(`${API}/promotion/batches/${id}`);
  }

  undo(id: number): Observable<PromotionBatch> {
    return this.http.post<PromotionBatch>(`${API}/promotion/batches/${id}/undo`, {});
  }
}
