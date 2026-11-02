import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { concatMap, from } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { PolicyStatus, PrivacyApi } from '../../core/api/privacy.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';

/** Blocking page shown after sign-in while a policy version is not yet accepted. */
@Component({
  selector: 'sms-accept-policies',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './accept-policies.html',
  styleUrl: './accept-policies.css',
})
export class AcceptPolicies {
  private readonly api = inject(PrivacyApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly i18n = inject(I18n);

  protected readonly pending = signal<PolicyStatus[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly agreed = signal(false);

  constructor() {
    this.api.policies().subscribe({
      next: (res) => {
        const open = res.policies.filter((p) => !p.accepted);
        if (!res.pending || open.length === 0) {
          this.finish(false);
          return;
        }
        this.pending.set(open);
        this.loading.set(false);
      },
      // Fail open: a broken check must not lock people out of the portal.
      error: () => this.finish(false),
    });
  }

  protected toggle(event: Event): void {
    this.agreed.set((event.target as HTMLInputElement).checked);
  }

  protected accept(): void {
    if (!this.agreed() || this.saving()) return;
    this.saving.set(true);
    this.error.set(null);
    // One request at a time: the second acceptance starts only after the first one succeeded.
    from(this.pending())
      .pipe(concatMap((p) => this.api.acceptPolicy(p.policy, p.version)))
      .subscribe({
        complete: () => this.finish(false),
        error: (err: unknown) => {
          this.saving.set(false);
          this.error.set(apiErrorMessage(err));
        },
      });
  }

  protected signOut(): void {
    this.auth.logout();
  }

  private finish(pending: boolean): void {
    this.auth.setPoliciesPending(pending);
    void this.router.navigate(['/']);
  }
}
