import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { StudentsApi } from './students.api';

const API = '/api/v1';

export type PaymentMethod = 'cash' | 'upi' | 'card' | 'bank' | 'cheque' | 'online';
export type InvoiceStatus = 'unpaid' | 'partial' | 'paid' | 'cancelled';
export type PaymentStatus = 'received' | 'reversed';

export const PAYMENT_METHODS: PaymentMethod[] = ['cash', 'upi', 'card', 'bank', 'cheque', 'online'];
export const INVOICE_STATUSES: InvoiceStatus[] = ['unpaid', 'partial', 'paid', 'cancelled'];

export interface FeeHead {
  id: number;
  name: string;
  is_active: boolean;
}

export interface StructureItem {
  id: number;
  academic_year_id: number;
  class_id: number;
  class_name: string;
  fee_head_id: number;
  fee_head_name: string;
  amount_paise: number;
}

export interface StructureInput {
  academic_year_id: number;
  class_id: number;
  items: { fee_head_id: number; amount_paise: number }[];
}

export interface GenerateInput {
  academic_year_id: number;
  title: string;
  due_date: string;
  class_id?: number;
  section_id?: number;
  student_ids?: number[];
  fee_head_ids?: number[];
}

export interface GenerateResult {
  created: number;
  skipped_existing: number;
  skipped_no_structure: number;
}

export interface Invoice {
  id: number;
  invoice_no: string;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string | null;
  section_name: string | null;
  academic_year_id: number;
  title: string;
  due_date: string;
  gross_paise: number;
  discount_paise: number;
  discount_reason: string | null;
  total_paise: number;
  paid_paise: number;
  balance_paise: number;
  /** Part of the balance moved to the next year by a year-end promotion (0 when none). */
  carried_forward_paise?: number;
  status: InvoiceStatus;
  is_overdue: boolean;
}

export interface InvoiceLine {
  id: number;
  fee_head_id: number | null;
  description: string;
  amount_paise: number;
}

export interface Payment {
  id: number;
  receipt_no: string;
  invoice_id: number;
  invoice_no: string;
  student_id: number;
  student_name: string;
  amount_paise: number;
  method: PaymentMethod;
  reference: string | null;
  paid_on: string;
  status: PaymentStatus;
  received_by_name: string;
  note: string | null;
  reversed_reason: string | null;
  created_at: string;
}

export interface InvoiceDetail extends Invoice {
  lines: InvoiceLine[];
  payments: Payment[];
  cancel_reason: string | null;
}

export interface NewInvoice {
  student_id: number;
  academic_year_id: number;
  title: string;
  due_date: string;
  lines: { description: string; fee_head_id?: number | null; amount_paise: number }[];
}

export interface InvoiceUpdate {
  due_date?: string;
  discount_paise?: number;
  discount_reason?: string;
}

export interface NewPayment {
  amount_paise: number;
  method: PaymentMethod;
  reference?: string;
  paid_on?: string;
  note?: string;
}

export interface InvoiceFilters {
  academic_year_id?: number;
  class_id?: number;
  section_id?: number;
  status?: InvoiceStatus | '';
  q?: string;
  overdue?: boolean;
}

export interface InvoicePage {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
  totals: { billed_paise: number; paid_paise: number; balance_paise: number };
}

export interface DuesFilters {
  academic_year_id?: number;
  branch_id?: number;
  class_id?: number;
  section_id?: number;
  min_balance_paise?: number;
}

export interface DueRow {
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string | null;
  section_name: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  billed_paise: number;
  paid_paise: number;
  balance_paise: number;
  overdue_paise: number;
  oldest_due_date: string | null;
}

export interface Dues {
  items: DueRow[];
  totals: {
    billed_paise: number;
    paid_paise: number;
    balance_paise: number;
    overdue_paise: number;
  };
}

export interface Collection {
  from: string;
  to: string;
  total_paise: number;
  count: number;
  by_method: { method: PaymentMethod; total_paise: number; count: number }[];
  by_day: { date: string; total_paise: number }[];
}

export interface StudentFees {
  student_id: number;
  invoices: InvoiceDetail[];
  summary: { billed_paise: number; paid_paise: number; balance_paise: number };
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

/** Typed client for fee heads, structure, invoices, payments, dues and collection. */
@Injectable({ providedIn: 'root' })
export class FeesApi {
  private readonly http = inject(HttpClient);
  private readonly students = inject(StudentsApi);

  heads(): Observable<FeeHead[]> {
    return this.http.get<FeeHead[]>(`${API}/fees/heads`);
  }

  createHead(name: string): Observable<FeeHead> {
    return this.http.post<FeeHead>(`${API}/fees/heads`, { name });
  }

  updateHead(id: number, body: { name?: string; is_active?: boolean }): Observable<FeeHead> {
    return this.http.patch<FeeHead>(`${API}/fees/heads/${id}`, body);
  }

  structure(yearId: number, classId: number): Observable<StructureItem[]> {
    const params = toParams({ academic_year_id: yearId, class_id: classId });
    return this.http.get<StructureItem[]>(`${API}/fees/structure`, { params });
  }

  saveStructure(body: StructureInput): Observable<StructureItem[]> {
    return this.http.put<StructureItem[]>(`${API}/fees/structure`, body);
  }

  generate(body: GenerateInput): Observable<GenerateResult> {
    return this.http.post<GenerateResult>(`${API}/fees/invoices/generate`, body);
  }

  createInvoice(body: NewInvoice): Observable<InvoiceDetail> {
    return this.http.post<InvoiceDetail>(`${API}/fees/invoices`, body);
  }

  invoices(f: InvoiceFilters, page: number, pageSize: number): Observable<InvoicePage> {
    const params = toParams({
      academic_year_id: f.academic_year_id,
      class_id: f.class_id,
      section_id: f.section_id,
      status: f.status,
      q: f.q?.trim(),
      overdue: f.overdue,
      page,
      page_size: pageSize,
    });
    return this.http.get<InvoicePage>(`${API}/fees/invoices`, { params });
  }

  invoice(id: number): Observable<InvoiceDetail> {
    return this.http.get<InvoiceDetail>(`${API}/fees/invoices/${id}`);
  }

  updateInvoice(id: number, body: InvoiceUpdate): Observable<InvoiceDetail> {
    return this.http.patch<InvoiceDetail>(`${API}/fees/invoices/${id}`, body);
  }

  cancelInvoice(id: number, reason: string): Observable<InvoiceDetail> {
    return this.http.post<InvoiceDetail>(`${API}/fees/invoices/${id}/cancel`, { reason });
  }

  recordPayment(invoiceId: number, body: NewPayment): Observable<Payment> {
    return this.http.post<Payment>(`${API}/fees/invoices/${invoiceId}/payments`, body);
  }

  reversePayment(paymentId: number, reason: string): Observable<Payment> {
    return this.http.post<Payment>(`${API}/fees/payments/${paymentId}/reverse`, { reason });
  }

  /** Fetch the receipt PDF and save it as receipt-<receipt_no>.pdf. */
  downloadReceipt(payment: Pick<Payment, 'id' | 'receipt_no'>): Observable<void> {
    return this.http
      .get(`${API}/fees/payments/${payment.id}/receipt.pdf`, { responseType: 'blob' })
      .pipe(map((blob) => this.students.saveBlob(blob, `receipt-${payment.receipt_no}.pdf`)));
  }

  dues(f: DuesFilters): Observable<Dues> {
    return this.http.get<Dues>(`${API}/fees/dues`, { params: toParams({ ...f }) });
  }

  duesCsv(f: DuesFilters): Observable<Blob> {
    return this.http.get(`${API}/fees/dues/export`, {
      params: toParams({ ...f }),
      responseType: 'blob',
    });
  }

  collection(from: string, to: string, branchId: number): Observable<Collection> {
    const params = toParams({ from, to, branch_id: branchId });
    return this.http.get<Collection>(`${API}/fees/collection`, { params });
  }

  studentFees(studentId: number): Observable<StudentFees> {
    return this.http.get<StudentFees>(`${API}/students/${studentId}/fees`);
  }

  saveBlob(blob: Blob, filename: string): void {
    this.students.saveBlob(blob, filename);
  }
}
