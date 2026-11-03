import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { ExamTerm, ExamsApi } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError } from './exam-labels';

/** Exam terms of one academic year (for example Term 1, Term 2) with their weights. */
@Component({
  selector: 'sms-terms-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './terms-config.html',
  styleUrl: './exams-table.css',
})
export class TermsConfig {
  private readonly api = inject(ExamsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  readonly yearId = input.required<number>();

  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);
  protected readonly terms = signal<ExamTerm[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editing = signal<ExamTerm | null>(null);
  protected readonly weightTotal = computed(() =>
    this.terms().reduce((sum, t) => sum + t.weight_percent, 0),
  );

  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(50)]],
    sequence: [1, [Validators.required, Validators.min(1)]],
    weight_percent: [100, [Validators.required, Validators.min(0), Validators.max(100)]],
  });

  constructor() {
    effect(() => {
      const year = this.yearId();
      this.scope.branch();
      untracked(() => this.load(year));
    });
  }

  protected edit(term: ExamTerm): void {
    this.editing.set(term);
    this.form.reset({
      name: term.name,
      sequence: term.sequence,
      weight_percent: term.weight_percent,
    });
    this.error.set(null);
  }

  protected cancel(): void {
    this.editing.set(null);
    this.form.reset({ name: '', sequence: this.terms().length + 1, weight_percent: 100 });
  }

  protected save(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const body = { name: v.name.trim(), sequence: v.sequence, weight_percent: v.weight_percent };
    const current = this.editing();
    const request = current
      ? this.api.updateTerm(current.id, body)
      : this.api.createTerm({ academic_year_id: this.yearId(), ...body });
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.editing.set(null);
        this.form.reset({ name: '', sequence: this.terms().length + 1, weight_percent: 100 });
        this.load(this.yearId());
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.error.set(message);
      },
    });
  }

  private load(yearId: number): void {
    this.loading.set(true);
    this.editing.set(null);
    this.api.terms(yearId).subscribe({
      next: (rows) => {
        this.terms.set(rows);
        this.form.reset({ name: '', sequence: rows.length + 1, weight_percent: 100 });
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
