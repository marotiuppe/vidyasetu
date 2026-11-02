import { Injectable, inject, signal } from '@angular/core';

import { AuthService } from '../auth/auth.service';
import { NoticesApi } from './notices.api';

/** Shared unread-notices count (sidebar badge, top bar bell). */
@Injectable({ providedIn: 'root' })
export class NoticesService {
  private readonly api = inject(NoticesApi);
  private readonly auth = inject(AuthService);

  readonly unread = signal(0);

  /** The platform admin has no school data, so no noticeboard. */
  enabled(): boolean {
    const user = this.auth.user();
    return user !== null && user.role !== 'super_admin' && user.school_id != null;
  }

  refresh(): void {
    if (!this.enabled()) {
      this.unread.set(0);
      return;
    }
    this.api.unreadCount().subscribe({
      next: (r) => this.unread.set(r.count),
      error: () => undefined,
    });
  }
}
