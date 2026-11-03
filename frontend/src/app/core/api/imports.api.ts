import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Role } from '../auth/auth.models';

const API = '/api/v1';

/** A row that could not be imported. `row` is the 1-based data row (the first row under the header is 1). */
export interface ImportRowError {
  row: number;
  message: string;
}

export interface UserImportRow {
  username: string;
  full_name: string;
  role: Role;
  email?: string;
  mobile?: string;
}

export interface UserImportBody {
  /** Branch for branch-level roles; the signed-in user's own branch is used when omitted. */
  branch_id?: number | null;
  dry_run: boolean;
  rows: UserImportRow[];
}

/** A generated sign-in for an imported user. Returned once, on a real import only. */
export interface UserCredential {
  username: string;
  full_name: string;
  role: Role;
  temporary_password: string;
}

export interface UserImportResult {
  /** Accounts created (real import). */
  created?: number;
  /** Accounts that would be created (dry run). */
  would_create?: number;
  failed: number;
  errors: ImportRowError[];
  credentials?: UserCredential[] | null;
}

/** Amounts are sent as text (rupees, at most two decimals) so no float rounding happens on the way. */
export interface FeeStructureImportRow {
  class: string;
  fee_head: string;
  amount_rupees: string;
}

export interface FeeStructureImportBody {
  academic_year_id: number;
  /** Needed for a school owner (no branch of their own); omitted for branch users. */
  branch_id?: number | null;
  dry_run: boolean;
  rows: FeeStructureImportRow[];
}

/** All-or-nothing: with any row error nothing is saved (`failed` counts the bad rows). */
export interface FeeStructureImportResult {
  created?: number;
  updated?: number;
  would_create?: number;
  would_update?: number;
  failed: number;
  errors: ImportRowError[];
}

/** Typed client for the staff-account and fee-structure CSV imports. */
@Injectable({ providedIn: 'root' })
export class ImportsApi {
  private readonly http = inject(HttpClient);

  importUsers(body: UserImportBody): Observable<UserImportResult> {
    return this.http.post<UserImportResult>(`${API}/users/import`, body);
  }

  importFeeStructure(body: FeeStructureImportBody): Observable<FeeStructureImportResult> {
    return this.http.post<FeeStructureImportResult>(`${API}/fees/structure/import`, body);
  }
}
