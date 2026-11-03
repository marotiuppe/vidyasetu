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
import { ExamsApi, SUBJECT_KINDS, Subject, SubjectKind } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { fieldError, kindText } from './exam-labels';

/** The school's subjects for this branch: scholastic and co-scholastic. */
@Component({
  selector: 'sms-subjects-config',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './subjects-config.html',
  styleUrl: './exams-table.css',
})
export class SubjectsConfig {
  private readonly api = inject(ExamsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly kinds = SUBJECT_KINDS;
  protected readonly kindLabel = (kind: SubjectKind) => kindText(kind, this.i18n.t);
  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);

  protected readonly subjects = signal<Subject[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editing = signal<Subject | null>(null);

  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(80)]],
    code: ['', [Validators.maxLength(20)]],
    kind: this.fb.control<SubjectKind>('scholastic'),
    active: [true],
  });

  constructor() {
    effect(() => {
      this.scope.branch();
      untracked(() => this.load());
    });
  }

  protected edit(subject: Subject): void {
    this.editing.set(subject);
    this.error.set(null);
    this.form.reset({
      name: subject.name,
      code: subject.code ?? '',
      kind: subject.kind,
      active: subject.active,
    });
  }

  protected cancel(): void {
    this.editing.set(null);
    this.form.reset({ name: '', code: '', kind: 'scholastic', active: true });
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
      code: v.code.trim() || null,
      kind: v.kind,
      active: v.active,
    };
    const current = this.editing();
    const request = current
      ? this.api.updateSubject(current.id, body)
      : this.api.createSubject(body);
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

  protected toggleActive(subject: Subject): void {
    this.error.set(null);
    this.api.updateSubject(subject.id, { active: !subject.active }).subscribe({
      next: () => this.load(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.api.subjects().subscribe({
      next: (rows) => {
        this.subjects.set(rows);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
