import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AdminApi, School } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { LogoPicker } from '../../core/ui/logo-picker';

@Component({
  selector: 'sms-schools',
  imports: [ReactiveFormsModule, LogoPicker],
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
  protected readonly notice = signal<string | null>(null);
  protected readonly newLogo = signal<File | null>(null);
  protected readonly editId = signal<number | null>(null);
  protected readonly editLogo = signal<File | null>(null);
  protected readonly editError = signal<string | null>(null);
  protected readonly editBusy = signal(false);
  protected readonly brokenLogos = signal<ReadonlySet<number>>(new Set());

  private readonly createPicker = viewChild<LogoPicker>('createPicker');
  private readonly editPicker = viewChild<LogoPicker>('editPicker');

  protected readonly editForm = this.fb.group({
    name: ['', Validators.required],
    board: ['', Validators.required],
  });

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
    this.notice.set(null);
    this.error.set(null);
    this.api.createSchool(this.form.getRawValue()).subscribe({
      next: (school) => {
        const logo = this.newLogo();
        this.form.reset();
        this.newLogo.set(null);
        this.createPicker()?.clear();
        if (!logo) {
          this.finishCreate();
          return;
        }
        this.api.uploadLogo(school.id, logo).subscribe({
          next: () => this.finishCreate(),
          error: (err: unknown) => {
            this.finishCreate();
            this.error.set(
              `School created, but the logo could not be uploaded: ${apiErrorMessage(err)} You can retry from the school's edit panel.`,
            );
            this.startEdit(school);
          },
        });
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  private finishCreate(): void {
    this.submitting.set(false);
    this.showForm.set(false);
    this.load();
  }

  protected initials(name: string): string {
    return (
      name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join('') || '?'
    );
  }

  protected logoFailed(id: number): void {
    this.brokenLogos.update((set) => new Set(set).add(id));
  }

  protected startEdit(school: School): void {
    this.editId.set(school.id);
    this.editLogo.set(null);
    this.editError.set(null);
    this.notice.set(null);
    this.editForm.reset({ name: school.name, board: school.board });
  }

  protected cancelEdit(): void {
    this.editId.set(null);
    this.editLogo.set(null);
  }

  protected saveEdit(school: School): void {
    if (this.editForm.invalid) {
      this.editForm.markAllAsTouched();
      return;
    }
    const { name, board } = this.editForm.getRawValue();
    const logo = this.editLogo();
    const changed = name.trim() !== school.name || board.trim() !== school.board;
    if (!changed && !logo) {
      this.cancelEdit();
      return;
    }
    this.editBusy.set(true);
    this.editError.set(null);
    this.error.set(null);
    const upload = () => {
      if (!logo) {
        this.afterEdit('School updated.');
        return;
      }
      this.api.uploadLogo(school.id, logo).subscribe({
        next: () => this.afterEdit('School updated.'),
        error: (err: unknown) => this.failEdit(err),
      });
    };
    if (!changed) {
      upload();
      return;
    }
    this.api.updateSchool(school.id, { name: name.trim(), board: board.trim() }).subscribe({
      next: upload,
      error: (err: unknown) => this.failEdit(err),
    });
  }

  protected removeLogo(school: School): void {
    this.editBusy.set(true);
    this.editError.set(null);
    this.api.removeLogo(school.id).subscribe({
      next: () => this.afterEdit('Logo removed.', false),
      error: (err: unknown) => this.failEdit(err),
    });
  }

  private afterEdit(message: string, close = true): void {
    this.editBusy.set(false);
    this.editLogo.set(null);
    this.editPicker()?.clear();
    this.notice.set(message);
    if (close) this.editId.set(null);
    this.brokenLogos.set(new Set());
    this.load();
  }

  private failEdit(err: unknown): void {
    this.editBusy.set(false);
    this.editError.set(apiErrorMessage(err));
    this.load();
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
