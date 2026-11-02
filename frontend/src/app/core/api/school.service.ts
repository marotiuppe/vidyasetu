import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';

import { AuthService } from '../auth/auth.service';

interface AcademicYearInfo {
  name: string;
  is_current: boolean;
}

/** The signed-in user's school: name and current academic year (empty for the platform admin). */
@Injectable({ providedIn: 'root' })
export class SchoolService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  readonly name = signal<string | null>(null);
  readonly year = signal<string | null>(null);
  readonly logoUrl = signal<string | null>(null);
  /** Public school code, used for the school's own legal pages. */
  readonly code = signal<string | null>(null);

  load(): void {
    this.name.set(null);
    this.year.set(null);
    this.logoUrl.set(null);
    this.code.set(null);
    if (this.auth.user()?.school_id == null) {
      return;
    }
    this.http
      .get<{ name: string; code: string; logo_url: string | null }>('/api/v1/schools/me')
      .subscribe((s) => {
        this.name.set(s.name);
        this.logoUrl.set(s.logo_url);
        this.code.set(s.code);
      });
    this.http
      .get<AcademicYearInfo[]>('/api/v1/academic-years')
      .subscribe((years) => this.year.set(years.find((y) => y.is_current)?.name ?? null));
  }
}
