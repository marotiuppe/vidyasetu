import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { catchError, of } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { Icon } from '../../core/ui/icon';

@Component({
  selector: 'sms-login',
  imports: [ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly form = inject(NonNullableFormBuilder).group({
    identifier: ['', [Validators.required]],
    password: ['', [Validators.required]],
    rememberMe: [false],
  });
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly showPassword = signal(false);
  protected readonly resetEnabled = signal(false);
  protected readonly resetInfo = signal(false);

  constructor() {
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
    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    const { identifier, password, rememberMe } = this.form.getRawValue();
    this.auth.login(identifier.trim(), password, rememberMe).subscribe({
      next: () => void this.router.navigate(['/']),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(
          err instanceof HttpErrorResponse && err.status === 401
            ? 'Invalid credentials. Check your username, mobile or email and password.'
            : 'Could not sign in. Please try again.',
        );
      },
    });
  }
}
