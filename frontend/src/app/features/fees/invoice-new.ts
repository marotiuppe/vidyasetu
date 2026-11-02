import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  output,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeesApi, NewInvoice } from '../../core/api/fees.api';
import { Student } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise, parseRupeesToPaise } from '../../core/ui/money';
import { FeeLookups } from './fee-lookups';
import { StudentPicker } from './student-picker';

/** Create one invoice by hand for a student, with free-text lines. */
@Component({
  selector: 'sms-invoice-new',
  imports: [ReactiveFormsModule, Icon, StudentPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './invoice-new.html',
})
export class InvoiceNew {
  private readonly api = inject(FeesApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  readonly created = output<number>();
  readonly closed = output<void>();

  protected readonly money = formatPaise;
  protected readonly student = signal<Student | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group({
    yearId: [this.lookups.currentYearId()],
    title: [''],
    dueDate: [''],
    lines: this.fb.array([this.newLine()]),
  });
  private readonly values = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });

  /** Sum of the valid line amounts in integer paise. */
  protected readonly total = computed(() =>
    (this.values().lines ?? []).reduce(
      (sum, l) => sum + (parseRupeesToPaise(l?.amount ?? '') ?? 0),
      0,
    ),
  );

  protected get lines() {
    return this.form.controls.lines;
  }

  private newLine() {
    return this.fb.group({ description: [''], amount: [''] });
  }

  protected addLine(): void {
    this.lines.push(this.newLine());
  }

  protected removeLine(i: number): void {
    if (this.lines.length > 1) this.lines.removeAt(i);
  }

  protected submit(): void {
    this.error.set(null);
    const v = this.form.getRawValue();
    const student = this.student();
    const title = v.title.trim();
    if (!student) return this.error.set(this.i18n.t('fees.setup.invoice.chooseStudent'));
    if (!v.yearId) return this.error.set(this.i18n.t('fees.setup.common.chooseYear'));
    if (!title) return this.error.set(this.i18n.t('fees.setup.invoice.enterTitle'));
    if (!v.dueDate) return this.error.set(this.i18n.t('fees.setup.common.chooseDue'));

    const lines: NewInvoice['lines'] = [];
    for (const [i, l] of v.lines.entries()) {
      const amount = parseRupeesToPaise(l.amount);
      if (!l.description.trim() || amount === null || amount <= 0) {
        return this.error.set(this.i18n.t('fees.setup.invoice.lineInvalid', { n: i + 1 }));
      }
      lines.push({ description: l.description.trim(), amount_paise: amount });
    }

    this.busy.set(true);
    this.api
      .createInvoice({
        student_id: student.id,
        academic_year_id: v.yearId,
        title,
        due_date: v.dueDate,
        lines,
      })
      .subscribe({
        next: (inv) => {
          this.busy.set(false);
          this.created.emit(inv.id);
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.error.set(apiErrorMessage(err));
        },
      });
  }
}
