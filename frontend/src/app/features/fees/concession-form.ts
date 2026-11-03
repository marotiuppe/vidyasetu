import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { filter, take } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeeHead, FeesApi } from '../../core/api/fees.api';
import {
  CONCESSION_KINDS,
  ConcessionKind,
  FeeToolsApi,
  NewConcession,
} from '../../core/api/fee-tools.api';
import { Student } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { parseRupeesToPaise } from '../../core/ui/money';
import { parsePercentToBps } from './fee-tools-model';
import { FeeLookups } from './fee-lookups';
import { StudentPicker } from './student-picker';

/** Add one concession for a student and an academic year. */
@Component({
  selector: 'sms-concession-form',
  imports: [ReactiveFormsModule, StudentPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './concession-form.html',
})
export class ConcessionForm {
  private readonly api = inject(FeeToolsApi);
  private readonly feesApi = inject(FeesApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  readonly created = output<void>();

  protected readonly kinds = CONCESSION_KINDS;

  protected readonly form = this.fb.group({
    yearId: [0],
    name: ['', [Validators.maxLength(100)]],
    kind: ['percent' as ConcessionKind],
    value: [''],
    headId: [0],
    reason: ['', [Validators.maxLength(200)]],
  });

  protected readonly student = signal<Student | null>(null);
  protected readonly heads = signal<FeeHead[]>([]);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  constructor() {
    this.lookups.load();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => this.form.controls.yearId.setValue(this.lookups.currentYearId()));
    this.feesApi.heads().subscribe({
      next: (h) => this.heads.set(h.filter((x) => x.is_active)),
      error: () => this.heads.set([]),
    });
  }

  protected pickStudent(s: Student): void {
    this.student.set(s);
    this.error.set(null);
  }

  protected submit(): void {
    this.error.set(null);
    this.notice.set(null);
    const v = this.form.getRawValue();
    const name = v.name.trim();
    const student = this.student();
    if (!student) return this.error.set(this.i18n.t('fees.tools.concessions.errorStudent'));
    if (!v.yearId) return this.error.set(this.i18n.t('fees.tools.concessions.errorYear'));
    if (!name) return this.error.set(this.i18n.t('fees.tools.concessions.errorName'));

    const value = v.kind === 'percent' ? parsePercentToBps(v.value) : parseRupeesToPaise(v.value);
    if (value === null || value <= 0) {
      const key =
        v.kind === 'percent'
          ? 'fees.tools.concessions.errorPercent'
          : 'fees.tools.concessions.errorFixed';
      return this.error.set(this.i18n.t(key));
    }

    const body: NewConcession = {
      student_id: student.id,
      academic_year_id: v.yearId,
      name,
      kind: v.kind,
      value,
      fee_head_id: v.headId || null,
      reason: v.reason.trim() || null,
    };
    this.busy.set(true);
    this.api.createConcession(body).subscribe({
      next: () => {
        this.busy.set(false);
        this.notice.set(this.i18n.t('fees.tools.concessions.created'));
        this.form.patchValue({ name: '', value: '', reason: '' });
        this.created.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
