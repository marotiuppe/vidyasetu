import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

import { AdminApi } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { ROLE_LABELS } from '../../core/layout/nav';

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
  protected readonly roleLabels = ROLE_LABELS;

  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

  protected readonly form = this.fb.group(
    {
      current_password: ['', Validators.required],
      new_password: ['', [Validators.required, Validators.minLength(8)]],
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
      next: () => {
        this.submitting.set(false);
        this.form.reset();
        this.done.set(true);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
