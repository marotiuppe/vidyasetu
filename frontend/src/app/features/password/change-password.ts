import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';

import { AdminApi } from '../../core/api/admin.api';
import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { PASSWORD_HINT, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../../core/auth/password';

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  const next = group.get('new_password')?.value;
  const confirm = group.get('confirm')?.value;
  return next === confirm ? null : { mismatch: true };
}

/**
 * Set a new password. Shown outside the shell when the user must change it first
 * (after an admin reset or the first sign-in); the shell's guard sends everyone else here.
 */
@Component({
  selector: 'sms-change-password',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './change-password.html',
  styleUrl: './change-password.css',
})
export class ChangePassword {
  private readonly api = inject(AdminApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly forced = computed(() => this.auth.user()?.must_change_password === true);
  protected readonly hint = PASSWORD_HINT;
  protected readonly minLength = PASSWORD_MIN_LENGTH;
  protected readonly maxLength = PASSWORD_MAX_LENGTH;
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group(
    {
      current_password: ['', Validators.required],
      new_password: [
        '',
        [
          Validators.required,
          Validators.minLength(PASSWORD_MIN_LENGTH),
          Validators.maxLength(PASSWORD_MAX_LENGTH),
        ],
      ],
      confirm: ['', Validators.required],
    },
    { validators: passwordsMatch },
  );

  protected submit(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { current_password, new_password } = this.form.getRawValue();
    this.submitting.set(true);
    this.api
      .changePassword(current_password, new_password)
      .subscribe({
        // The server ends every session when the password changes: sign in again.
        next: () => this.auth.passwordChanged(),
        error: (err: unknown) => {
          this.submitting.set(false);
          if (err instanceof HttpErrorResponse && err.status === 422) {
            this.error.set(placeServerErrors(this.form, err));
          } else {
            this.error.set(apiErrorMessage(err));
          }
        },
      });
  }

  protected signOut(): void {
    this.auth.logout();
  }
}
