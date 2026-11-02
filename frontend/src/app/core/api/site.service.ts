import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';

/** Platform-wide notices from the public site settings. Every field is optional: absent means "show nothing". */
export interface SiteNotices {
  platform_name?: string | null;
  support_contact?: string | null;
  maintenance_message?: string | null;
  announcement_banner?: string | null;
}

const SITE_URL = '/api/v1/public/site';

/** Loads the public platform notices once (announcement banner and maintenance message). */
@Injectable({ providedIn: 'root' })
export class SiteService {
  private readonly http = inject(HttpClient);
  private requested = false;

  /** Null until loaded, or when loading failed: the notices then stay hidden. */
  readonly notices = signal<SiteNotices | null>(null);

  load(): void {
    if (this.requested) {
      return;
    }
    this.requested = true;
    this.http.get<SiteNotices>(SITE_URL).subscribe({
      next: (site) => this.notices.set(site),
      error: () => this.notices.set(null),
    });
  }
}
