import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';

/** Operator and grievance details from GET /public/legal. Null means "not yet entered". */
export interface LegalInfo {
  configured: boolean;
  operator_name: string | null;
  operator_address: string | null;
  operator_email: string | null;
  operator_phone: string | null;
  grievance_officer_name: string | null;
  grievance_officer_email: string | null;
  grievance_officer_phone: string | null;
  grievance_response_days: number;
  security_contact_email: string | null;
  privacy_contact_email: string | null;
  hosting_region: string | null;
  policy_effective_date: string | null;
  data_retention_note: string | null;
}

const LEGAL_URL = '/api/v1/public/legal';

/** Loads the public legal details once and keeps them for every legal page. */
@Injectable({ providedIn: 'root' })
export class LegalService {
  private readonly http = inject(HttpClient);
  private loading = false;

  /** Null until loaded (or when loading failed). */
  readonly info = signal<LegalInfo | null>(null);
  readonly failed = signal(false);

  load(): void {
    if (this.info() !== null || this.loading) {
      return;
    }
    this.loading = true;
    this.failed.set(false);
    this.http.get<LegalInfo>(LEGAL_URL).subscribe({
      next: (info) => {
        this.info.set(info);
        this.loading = false;
      },
      error: () => {
        this.failed.set(true);
        this.loading = false;
      },
    });
  }
}
