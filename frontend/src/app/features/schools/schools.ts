import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AdminApi, School } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';

@Component({
  selector: 'sms-schools',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schools.html',
  styleUrl: './schools.css',
})
export class Schools {
  private readonly api = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly schools = signal<School[]>([]);
  protected readonly loading = signal(true);
  protected readonly submitting = signal(false);
  protected readonly showForm = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly busyId = signal<number | null>(null);
  protected readonly confirmId = signal<number | null>(null);

  protected readonly form = this.fb.group({
    name: ['', Validators.required],
    code: ['', [Validators.required, Validators.pattern(/^[a-z0-9_-]+$/)]],
    board: ['', Validators.required],
    owner_full_name: ['', Validators.required],
    owner_email: ['', [Validators.required, Validators.email]],
    owner_password: ['', [Validators.required, Validators.minLength(8)]],
  });

  constructor() {
    this.load();
  }

  protected toggleForm(): void {
    this.showForm.update((v) => !v);
    this.formError.set(null);
  }

  protected create(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.submitting.set(true);
    this.formError.set(null);
    this.api.createSchool(this.form.getRawValue()).subscribe({
      next: () => {
        this.submitting.set(false);
        this.form.reset();
        this.showForm.set(false);
        this.load();
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  protected askToggle(id: number): void {
    this.confirmId.set(id);
  }

  protected cancelToggle(): void {
    this.confirmId.set(null);
  }

  protected confirmToggle(school: School): void {
    this.busyId.set(school.id);
    this.error.set(null);
    this.api.updateSchool(school.id, { is_active: !school.is_active }).subscribe({
      next: () => {
        this.busyId.set(null);
        this.confirmId.set(null);
        this.load();
      },
      error: (err: unknown) => {
        this.busyId.set(null);
        this.confirmId.set(null);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private load(): void {
    this.api.schools().subscribe({
      next: (s) => {
        this.schools.set(s);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
