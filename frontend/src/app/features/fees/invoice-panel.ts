import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  FeesApi,
  InvoiceDetail,
  InvoiceStatus,
  PAYMENT_METHODS,
  Payment,
  PaymentMethod,
} from '../../core/api/fees.api';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise, paiseToInput, parseRupeesToPaise } from '../../core/ui/money';
import { classSection, invoiceStatusClass, todayIso } from './fee-labels';

/** One invoice: lines, discount, payments (record, reverse, receipt) and cancel. */
@Component({
  selector: 'sms-invoice-panel',
  imports: [ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './invoice-panel.html',
  styleUrl: './invoice-panel.css',
})
export class InvoicePanel {
  private readonly api = inject(FeesApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  readonly invoiceId = input.required<number>();
  readonly canManage = input(false);
  readonly canPay = input(false);
  readonly changed = output<void>();
  readonly closed = output<void>();

  protected readonly money = formatPaise;
  protected readonly methods = PAYMENT_METHODS;
  protected readonly statusClass = invoiceStatusClass;
  protected readonly today = todayIso();

  protected readonly invoice = signal<InvoiceDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  private readonly tick = signal(0);

  protected readonly editOpen = signal(false);
  protected readonly cancelOpen = signal(false);
  protected readonly reversingId = signal(0);

  protected readonly payError = signal<string | null>(null);
  protected readonly editError = signal<string | null>(null);

  protected readonly payForm = this.fb.group({
    amount: [''],
    method: ['cash' as PaymentMethod],
    reference: [''],
    paidOn: [todayIso()],
    note: [''],
  });
  protected readonly editForm = this.fb.group({ dueDate: [''], discount: ['0'], reason: [''] });
  protected readonly reasonControl = this.fb.control('');

  protected readonly canRecord = computed(() => {
    const inv = this.invoice();
    return this.canPay() && !!inv && inv.status !== 'cancelled' && inv.balance_paise > 0;
  });
  protected readonly canEdit = computed(
    () => this.canManage() && this.invoice()?.status !== 'cancelled',
  );
  protected readonly canCancel = computed(() => {
    const inv = this.invoice();
    return (
      this.canManage() &&
      !!inv &&
      inv.status !== 'cancelled' &&
      !inv.payments.some((p) => p.status === 'received')
    );
  });

  constructor() {
    toObservable(computed(() => ({ id: this.invoiceId(), tick: this.tick() })))
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.invoice(s.id).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((inv) => {
        this.loading.set(false);
        if (!inv) return;
        this.invoice.set(inv);
        this.payForm.patchValue({
          amount: inv.balance_paise > 0 ? paiseToInput(inv.balance_paise) : '',
        });
        this.editForm.setValue({
          dueDate: inv.due_date,
          discount: paiseToInput(inv.discount_paise),
          reason: inv.discount_reason ?? '',
        });
      });
  }

  /** "Class - Section", or the translated "Not enrolled" when the student has no class. */
  protected classText(className: string | null, sectionName: string | null): string {
    return className ? classSection(className, sectionName) : this.i18n.t('fees.daily.notEnrolled');
  }

  protected methodText(method: PaymentMethod): string {
    return this.i18n.t(`fees.daily.method.${method}`);
  }

  protected statusText(status: InvoiceStatus): string {
    return this.i18n.t(`fees.daily.status.${status}`);
  }

  protected openEdit(): void {
    this.closeForms();
    this.editOpen.set(true);
  }

  protected openCancel(): void {
    this.closeForms();
    this.cancelOpen.set(true);
  }

  protected openReverse(p: Payment): void {
    this.closeForms();
    this.reversingId.set(p.id);
  }

  protected closeForms(): void {
    this.editOpen.set(false);
    this.cancelOpen.set(false);
    this.reversingId.set(0);
    this.reasonControl.reset('');
    this.editError.set(null);
    this.error.set(null);
  }

  protected recordPayment(inv: InvoiceDetail): void {
    this.payError.set(null);
    this.notice.set(null);
    const v = this.payForm.getRawValue();
    const amount = parseRupeesToPaise(v.amount);
    if (amount === null || amount <= 0) {
      this.payError.set(this.i18n.t('fees.daily.err.amountInvalid'));
      return;
    }
    if (amount > inv.balance_paise) {
      this.payError.set(
        this.i18n.t('fees.daily.err.amountOverBalance', {
          amount: formatPaise(inv.balance_paise),
        }),
      );
      return;
    }
    if (v.paidOn && v.paidOn > this.today) {
      this.payError.set(this.i18n.t('fees.daily.err.paidOnFuture'));
      return;
    }
    this.busy.set(true);
    this.api
      .recordPayment(inv.id, {
        amount_paise: amount,
        method: v.method,
        reference: v.reference.trim() || undefined,
        paid_on: v.paidOn || undefined,
        note: v.note.trim() || undefined,
      })
      .subscribe({
        next: (p) => {
          this.payForm.patchValue({ reference: '', note: '' });
          this.done(this.i18n.t('fees.daily.msg.paymentRecorded', { no: p.receipt_no }));
        },
        error: (err: unknown) => this.fail(err, this.payError),
      });
  }

  protected saveEdit(inv: InvoiceDetail): void {
    this.editError.set(null);
    const v = this.editForm.getRawValue();
    const discount = parseRupeesToPaise(v.discount || '0');
    if (discount === null) {
      this.editError.set(this.i18n.t('fees.daily.err.discountInvalid'));
      return;
    }
    if (discount > inv.gross_paise) {
      this.editError.set(
        this.i18n.t('fees.daily.err.discountOverGross', { amount: formatPaise(inv.gross_paise) }),
      );
      return;
    }
    if (!v.dueDate) {
      this.editError.set(this.i18n.t('fees.daily.err.dueDateRequired'));
      return;
    }
    this.busy.set(true);
    this.api
      .updateInvoice(inv.id, {
        due_date: v.dueDate,
        discount_paise: discount,
        discount_reason: v.reason.trim(),
      })
      .subscribe({
        next: () => this.done(this.i18n.t('fees.daily.msg.invoiceUpdated')),
        error: (err: unknown) => this.fail(err, this.editError),
      });
  }

  protected cancelInvoice(inv: InvoiceDetail): void {
    const reason = this.reasonControl.value.trim();
    if (!reason) {
      this.error.set(this.i18n.t('fees.daily.err.cancelReasonRequired'));
      return;
    }
    this.busy.set(true);
    this.api.cancelInvoice(inv.id, reason).subscribe({
      next: () => this.done(this.i18n.t('fees.daily.msg.invoiceCancelled')),
      error: (err: unknown) => this.fail(err, this.error),
    });
  }

  protected reverse(p: Payment): void {
    const reason = this.reasonControl.value.trim();
    if (!reason) {
      this.error.set(this.i18n.t('fees.daily.err.reverseReasonRequired'));
      return;
    }
    this.busy.set(true);
    this.api.reversePayment(p.id, reason).subscribe({
      next: () => this.done(this.i18n.t('fees.daily.msg.paymentReversed', { no: p.receipt_no })),
      error: (err: unknown) => this.fail(err, this.error),
    });
  }

  protected receipt(p: Payment): void {
    this.error.set(null);
    this.api.downloadReceipt(p).subscribe({
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private done(message: string): void {
    this.busy.set(false);
    this.closeForms();
    this.notice.set(message);
    this.tick.update((t) => t + 1);
    this.changed.emit();
  }

  private fail(err: unknown, target: { set(v: string | null): void }): void {
    this.busy.set(false);
    target.set(apiErrorMessage(err));
  }
}
