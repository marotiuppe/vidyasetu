import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { catchError, of } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { focusById } from '../../core/ui/download';
import { LegalLinks } from '../../core/legal/legal-links';
import { Icon } from '../../core/ui/icon';

const DEFAULT_RETRY_SECONDS = 60;

@Component({
  selector: 'sms-login',
  imports: [ReactiveFormsModule, Icon, LegalLinks],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly i18n = inject(I18n);

  protected readonly form = inject(NonNullableFormBuilder).group({
    identifier: ['', [Validators.required]],
    password: ['', [Validators.required]],
    rememberMe: [false],
  });
  protected readonly codeForm = inject(NonNullableFormBuilder).group({
    code: ['', [Validators.required]],
  });
  /** 'password' is the first step; 'code' asks for the two-factor code. */
  protected readonly step = signal<'password' | 'code'>('password');
  protected readonly useRecovery = signal(false);
  private mfaToken: string | null = null;
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly showPassword = signal(false);
  protected readonly passwordChanged = inject(ActivatedRoute).snapshot.queryParamMap.has('changed');
  protected readonly resetEnabled = signal(false);
  protected readonly resetInfo = signal(false);
  /** Seconds left before another sign-in attempt is allowed (rate limit). */
  protected readonly retryIn = signal(0);
  protected readonly blocked = computed(() => this.retryIn() > 0);
  private retryTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => this.stopRetryTimer());
    this.auth
      .options()
      .pipe(
        catchError(() => of({ password_reset_enabled: false })),
        takeUntilDestroyed(),
      )
      .subscribe((options) => this.resetEnabled.set(options.password_reset_enabled));
  }

  protected togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  /** Self-service reset is not built yet; until it is, the school administrator resets passwords. */
  protected forgotPassword(): void {
    if (!this.resetEnabled()) {
      this.resetInfo.set(true);
    }
  }

  protected submit(): void {
    if (this.form.invalid || this.loading() || this.blocked()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    const { identifier, password, rememberMe } = this.form.getRawValue();
    this.auth.login(identifier.trim(), password, rememberMe).subscribe({
      next: (result) => {
        if (result.kind === 'mfa') {
          this.mfaToken = result.mfaToken;
          this.loading.set(false);
          this.codeForm.reset();
          this.useRecovery.set(false);
          this.step.set('code');
          focusById('mfa-heading');
          return;
        }
        void this.router.navigate(['/']);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && err.status === 429) {
          this.startRetryCountdown(retryAfterSeconds(err));
          return;
        }
        this.error.set(
          err instanceof HttpErrorResponse && err.status === 401
            ? 'Invalid credentials. Check your username, mobile or email and password.'
            : 'Could not sign in. Please try again.',
        );
      },
    });
  }

  protected toggleRecovery(): void {
    this.useRecovery.update((v) => !v);
    this.codeForm.reset();
    this.error.set(null);
    focusById('mfa-code');
  }

  /** Back to the password step (also used when the short-lived token has expired). */
  protected backToPassword(): void {
    this.mfaToken = null;
    this.error.set(null);
    this.step.set('password');
    focusById('password');
  }

  protected submitCode(): void {
    const token = this.mfaToken;
    if (this.codeForm.invalid || this.loading() || this.blocked() || token === null) {
      this.codeForm.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    const raw = this.codeForm.getRawValue().code.trim();
    const payload = this.useRecovery() ? { recovery_code: raw } : { code: raw.replace(/\s+/g, '') };
    this.auth.loginMfa(token, payload, this.form.getRawValue().rememberMe).subscribe({
      next: () => void this.router.navigate(['/']),
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && err.status === 429) {
          this.startRetryCountdown(retryAfterSeconds(err));
          return;
        }
        const code: unknown = err instanceof HttpErrorResponse ? err.error?.code : null;
        if (code === 'mfa_token_expired' || code === 'mfa_token_invalid') {
          this.backToPassword();
          this.error.set(this.i18n.t('mfa.login.expired'));
          return;
        }
        this.error.set(
          err instanceof HttpErrorResponse && err.status === 401
            ? this.i18n.t(this.useRecovery() ? 'mfa.login.badRecovery' : 'mfa.login.badCode')
            : this.i18n.t('mfa.login.failed'),
        );
      },
    });
  }

  private startRetryCountdown(seconds: number): void {
    this.stopRetryTimer();
    this.error.set(null);
    this.retryIn.set(Math.max(1, seconds));
    this.retryTimer = setInterval(() => {
      this.retryIn.update((n) => n - 1);
      if (this.retryIn() <= 0) {
        this.stopRetryTimer();
      }
    }, 1000);
  }

  private stopRetryTimer(): void {
    if (this.retryTimer !== null) {
      clearInterval(this.retryTimer);
      this.retryTimer = null;
    }
  }
}

/** Seconds from the Retry-After header; a default when it is missing or not a number. */
function retryAfterSeconds(err: HttpErrorResponse): number {
  const seconds = Number(err.headers.get('Retry-After'));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : DEFAULT_RETRY_SECONDS;
}
