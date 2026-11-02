import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

import { AdminApi } from '../../core/api/admin.api';
import { placeServerErrors } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../../core/auth/password';
import { I18n } from '../../core/i18n/i18n';
import { ROLE_LABEL_KEYS } from '../../core/layout/nav';

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  const next = group.get('new_password')?.value;
  const confirm = group.get('confirm')?.value;
  return next === confirm ? null : { mismatch: true };
}

@Component({
  selector: 'sms-account',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './account.html',
  styleUrl: './account.css',
})
export class Account {
  private readonly api = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);
  protected readonly roleKeys = ROLE_LABEL_KEYS;
  protected readonly minLength = PASSWORD_MIN_LENGTH;

  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

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
    this.done.set(false);
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { current_password, new_password } = this.form.getRawValue();
    this.submitting.set(true);
    this.api.changePassword(current_password, new_password).subscribe({
      // The server ends every session when the password changes: sign in again.
      next: () => this.auth.passwordChanged(),
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(placeServerErrors(this.form, err));
      },
    });
  }
}
