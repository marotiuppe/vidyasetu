import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AdminApi, School } from '../../core/api/admin.api';
import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { SchoolService } from '../../core/api/school.service';
import { I18n } from '../../core/i18n/i18n';
import { LogoPicker } from '../../core/ui/logo-picker';

@Component({
  selector: 'sms-school-profile',
  imports: [ReactiveFormsModule, LogoPicker, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './school-profile.html',
  styleUrl: './school-profile.css',
})
export class SchoolProfile {
  private readonly api = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly schoolService = inject(SchoolService);
  protected readonly i18n = inject(I18n);
  private readonly picker = viewChild<LogoPicker>('picker');

  protected readonly school = signal<School | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly saving = signal(false);
  protected readonly detailsError = signal<string | null>(null);
  protected readonly detailsNotice = signal<string | null>(null);

  protected readonly logoFile = signal<File | null>(null);
  protected readonly logoBusy = signal(false);
  protected readonly logoError = signal<string | null>(null);
  protected readonly logoNotice = signal<string | null>(null);

  protected readonly form = this.fb.group({
    name: ['', Validators.required],
    board: ['', Validators.required],
  });

  constructor() {
    this.api.mySchool().subscribe({
      next: (s) => {
        this.apply(s);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loadError.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  protected saveDetails(): void {
    if (this.form.invalid || !this.school()) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, board } = this.form.getRawValue();
    this.saving.set(true);
    this.detailsError.set(null);
    this.detailsNotice.set(null);
    this.api
      .updateMySchool({
        name: name.trim(),
        board: board.trim(),
      })
      .subscribe({
        next: (s) => {
          this.apply(s);
          this.saving.set(false);
          this.detailsNotice.set(this.i18n.t('admin.profile.detailsSaved'));
          this.schoolService.load();
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.detailsError.set(placeServerErrors(this.form, err));
        },
      });
  }

  protected uploadLogo(): void {
    const current = this.school();
    const file = this.logoFile();
    if (!current || !file) return;
    this.logoBusy.set(true);
    this.logoError.set(null);
    this.logoNotice.set(null);
    this.api.uploadLogo(current.id, file).subscribe({
      next: (s) => {
        this.school.set(s);
        this.logoFile.set(null);
        this.picker()?.clear();
        this.logoBusy.set(false);
        this.logoNotice.set(this.i18n.t('admin.profile.logoUpdated'));
        this.schoolService.load();
      },
      error: (err: unknown) => {
        this.logoBusy.set(false);
        this.logoError.set(apiErrorMessage(err));
      },
    });
  }

  protected removeLogo(): void {
    const current = this.school();
    if (!current) return;
    this.logoBusy.set(true);
    this.logoError.set(null);
    this.logoNotice.set(null);
    this.api.removeLogo(current.id).subscribe({
      next: () => {
        this.school.set({ ...current, logo_url: null });
        this.picker()?.clear();
        this.logoBusy.set(false);
        this.logoNotice.set(this.i18n.t('admin.profile.logoRemoved'));
        this.schoolService.load();
      },
      error: (err: unknown) => {
        this.logoBusy.set(false);
        this.logoError.set(apiErrorMessage(err));
      },
    });
  }

  private apply(s: School): void {
    this.school.set(s);
    this.form.reset({
      name: s.name,
      board: s.board,
    });
  }
}
