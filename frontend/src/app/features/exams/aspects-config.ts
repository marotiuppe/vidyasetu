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
import { EXAM_SECTIONS, ExamSection, ExamsApi, ReportAspect } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError, sectionText } from './exam-labels';

/** The aspects the report card grades per student (co-curricular, behavioural, and so on). */
@Component({
  selector: 'sms-aspects-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './aspects-config.html',
  styleUrl: './exams-table.css',
})
export class AspectsConfig {
  private readonly api = inject(ExamsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly sections = EXAM_SECTIONS;
  protected readonly sectionLabel = (s: ExamSection) => sectionText(s, this.i18n.t);
  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);

  protected readonly aspects = signal<ReportAspect[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editing = signal<ReportAspect | null>(null);

  protected readonly form = this.fb.group({
    section: this.fb.control<ExamSection>('co_curricular'),
    name: ['', [Validators.required, Validators.maxLength(80)]],
    sequence: [1, [Validators.required, Validators.min(0)]],
    active: [true],
  });

  constructor() {
    effect(() => {
      this.scope.branch();
      untracked(() => this.load());
    });
  }

  protected edit(aspect: ReportAspect): void {
    this.editing.set(aspect);
    this.error.set(null);
    this.form.reset({
      section: aspect.section,
      name: aspect.name,
      sequence: aspect.sequence,
      active: aspect.active,
    });
    this.form.controls.section.disable();
  }

  protected cancel(): void {
    this.editing.set(null);
    this.form.controls.section.enable();
    this.form.reset({ section: 'co_curricular', name: '', sequence: 1, active: true });
  }

  protected save(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const body = { name: v.name.trim(), sequence: v.sequence, active: v.active };
    const current = this.editing();
    const request = current
      ? this.api.updateAspect(current.id, body)
      : this.api.createAspect({ section: v.section, ...body });
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.cancel();
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.error.set(message);
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.api.aspects().subscribe({
      next: (rows) => {
        this.aspects.set(rows);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
