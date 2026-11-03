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
import { Exam, ExamTerm, ExamUpdate, ExamsApi } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError, fieldValue } from './exam-labels';

/** Exams inside each term, with marks scale, weight, publishing and locking. */
@Component({
  selector: 'sms-exam-list-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './exam-list-config.html',
  styleUrl: './exams-table.css',
})
export class ExamListConfig {
  private readonly api = inject(ExamsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  readonly yearId = input.required<number>();

  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);

  protected readonly terms = signal<ExamTerm[]>([]);
  protected readonly exams = signal<Exam[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editing = signal<Exam | null>(null);
  protected readonly termName = computed(() => {
    const names = new Map(this.terms().map((t) => [t.id, t.name]));
    return (id: number) => names.get(id) ?? '—';
  });

  protected readonly form = this.fb.group({
    term_id: this.fb.control(0, [Validators.min(1)]),
    name: ['', [Validators.required, Validators.maxLength(80)]],
    max_marks: [100, [Validators.required, Validators.min(1), Validators.max(1000)]],
    weight_percent: [100, [Validators.required, Validators.min(0), Validators.max(100)]],
    published: [false],
    locked: [false],
  });

  constructor() {
    effect(() => {
      const year = this.yearId();
      this.scope.branch();
      untracked(() => this.load(year));
    });
  }

  protected edit(exam: Exam): void {
    this.editing.set(exam);
    this.error.set(null);
    this.form.reset({
      term_id: exam.term_id,
      name: exam.name,
      max_marks: exam.max_marks,
      weight_percent: exam.weight_percent,
      published: exam.published,
      locked: exam.locked,
    });
    this.form.controls.term_id.disable();
  }

  protected cancel(): void {
    this.editing.set(null);
    this.form.controls.term_id.enable();
    this.form.reset({
      term_id: this.terms()[0]?.id ?? 0,
      name: '',
      max_marks: 100,
      weight_percent: 100,
      published: false,
      locked: false,
    });
  }

  protected setTerm(event: Event): void {
    this.form.controls.term_id.setValue(Number(fieldValue(event)));
  }

  protected save(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const body = {
      name: v.name.trim(),
      max_marks: v.max_marks,
      weight_percent: v.weight_percent,
      published: v.published,
      locked: v.locked,
    };
    const current = this.editing();
    const request = current
      ? this.api.updateExam(current.id, body)
      : this.api.createExam({ term_id: v.term_id, ...body });
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.cancel();
        this.reload();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.error.set(message);
      },
    });
  }

  /** Publish or unpublish, or lock or unlock, straight from the table. */
  protected flip(exam: Exam, field: 'published' | 'locked'): void {
    this.error.set(null);
    const body: ExamUpdate =
      field === 'published' ? { published: !exam.published } : { locked: !exam.locked };
    this.api.updateExam(exam.id, body).subscribe({
      next: () => this.reload(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private reload(): void {
    this.load(this.yearId());
  }

  private load(yearId: number): void {
    this.loading.set(true);
    this.editing.set(null);
    this.api.terms(yearId).subscribe({
      next: (terms) => {
        this.terms.set(terms);
        this.form.controls.term_id.setValue(terms[0]?.id ?? 0);
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
    this.api.exams(yearId).subscribe({
      next: (rows) => {
        this.exams.set(rows);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
