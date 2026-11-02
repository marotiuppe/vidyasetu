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

  load(): void {
    this.name.set(null);
    this.year.set(null);
    if (this.auth.user()?.school_id == null) {
      return;
    }
    this.http.get<{ name: string }>('/api/v1/schools/me').subscribe((s) => this.name.set(s.name));
    this.http
      .get<AcademicYearInfo[]>('/api/v1/academic-years')
      .subscribe((years) => this.year.set(years.find((y) => y.is_current)?.name ?? null));
  }
}
