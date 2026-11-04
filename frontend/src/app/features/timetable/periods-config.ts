import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { Period, TimetableApi, shortTime } from '../../core/api/timetable.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError } from '../exams/exam-labels';
import { sortPeriods } from './timetable-labels';

/** Daily periods and breaks of one branch, with their start and end times. */
@Component({
  selector: 'sms-periods-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './periods-config.html',
  styleUrl: '../exams/exams-table.css',
})
export class PeriodsConfig {
  private readonly api = inject(TimetableApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);
  protected readonly shortTime = shortTime;
  protected readonly periods = signal<Period[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editing = signal<Period | null>(null);

  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(40)]],
    sequence: [1, [Validators.required, Validators.min(1)]],
    start_time: ['', Validators.required],
    end_time: ['', Validators.required],
    is_break: [false],
  });

  constructor() {
    effect(() => {
      this.scope.branch();
      untracked(() => this.load());
    });
  }

  protected edit(p: Period): void {
    this.editing.set(p);
    this.form.reset({
      name: p.name,
      sequence: p.sequence,
      start_time: shortTime(p.start_time),
      end_time: shortTime(p.end_time),
      is_break: p.is_break,
    });
    this.error.set(null);
  }

  protected cancel(): void {
    this.editing.set(null);
    this.resetForm();
  }

  protected save(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    if (v.end_time <= v.start_time) {
      this.error.set(this.i18n.t('timetable.periods.endAfterStart'));
      return;
    }
    const body = {
      name: v.name.trim(),
      sequence: v.sequence,
      start_time: `${v.start_time}:00`,
      end_time: `${v.end_time}:00`,
      is_break: v.is_break,
    };
    const current = this.editing();
    const request = current ? this.api.updatePeriod(current.id, body) : this.api.createPeriod(body);
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.editing.set(null);
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.error.set(message);
      },
    });
  }

  protected remove(p: Period): void {
    if (!window.confirm(this.i18n.t('timetable.periods.confirmDelete', { name: p.name }))) return;
    this.error.set(null);
    this.api.deletePeriod(p.id).subscribe({
      next: () => this.load(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private resetForm(): void {
    const last = this.periods().at(-1);
    this.form.reset({
      name: '',
      sequence: this.periods().length + 1,
      start_time: last ? shortTime(last.end_time) : '',
      end_time: '',
      is_break: false,
    });
  }

  private load(): void {
    this.loading.set(true);
    this.editing.set(null);
    this.api.periods().subscribe({
      next: (rows) => {
        this.periods.set(sortPeriods(rows));
        this.resetForm();
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
