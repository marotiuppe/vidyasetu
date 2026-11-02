import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeesApi, InvoiceDetail, PAYMENT_METHODS, Payment, PaymentMethod } from '../../core/api/fees.api';
import { Icon } from '../../core/ui/icon';
import { formatPaise, paiseToInput, parseRupeesToPaise } from '../../core/ui/money';
import {
  classSection,
  invoiceStatusClass,
  invoiceStatusLabel,
  methodLabel,
  todayIso,
} from './fee-labels';

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

  readonly invoiceId = input.required<number>();
  readonly canManage = input(false);
  readonly canPay = input(false);
  readonly changed = output<void>();
  readonly closed = output<void>();

  protected readonly money = formatPaise;
  protected readonly methods = PAYMENT_METHODS;
  protected readonly methodLabel = methodLabel;
  protected readonly statusLabel = invoiceStatusLabel;
  protected readonly statusClass = invoiceStatusClass;
  protected readonly classSection = classSection;
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
  protected readonly canEdit = computed(() => this.canManage() && this.invoice()?.status !== 'cancelled');
  protected readonly canCancel = computed(() => {
    const inv = this.invoice();
    return (
      this.canManage() && !!inv && inv.status !== 'cancelled' && !inv.payments.some((p) => p.status === 'received')
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
        this.payForm.patchValue({ amount: inv.balance_paise > 0 ? paiseToInput(inv.balance_paise) : '' });
        this.editForm.setValue({
          dueDate: inv.due_date,
          discount: paiseToInput(inv.discount_paise),
          reason: inv.discount_reason ?? '',
        });
      });
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
      this.payError.set('Enter an amount in rupees greater than zero, with at most 2 decimals.');
      return;
    }
    if (amount > inv.balance_paise) {
      this.payError.set(`The amount cannot be more than the balance of ${formatPaise(inv.balance_paise)}.`);
      return;
    }
    if (v.paidOn && v.paidOn > this.today) {
      this.payError.set('The payment date cannot be in the future.');
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
          this.done(`Payment recorded. Receipt ${p.receipt_no}.`);
        },
        error: (err: unknown) => this.fail(err, this.payError),
      });
  }

  protected saveEdit(inv: InvoiceDetail): void {
    this.editError.set(null);
    const v = this.editForm.getRawValue();
    const discount = parseRupeesToPaise(v.discount || '0');
    if (discount === null) {
      this.editError.set('Enter the discount in rupees with at most 2 decimals.');
      return;
    }
    if (discount > inv.gross_paise) {
      this.editError.set(`The discount cannot be more than ${formatPaise(inv.gross_paise)}.`);
      return;
    }
    if (!v.dueDate) {
      this.editError.set('Choose a due date.');
      return;
    }
    this.busy.set(true);
    this.api
      .updateInvoice(inv.id, { due_date: v.dueDate, discount_paise: discount, discount_reason: v.reason.trim() })
      .subscribe({
        next: () => this.done('Invoice updated.'),
        error: (err: unknown) => this.fail(err, this.editError),
      });
  }

  protected cancelInvoice(inv: InvoiceDetail): void {
    const reason = this.reasonControl.value.trim();
    if (!reason) {
      this.error.set('Enter a reason for cancelling.');
      return;
    }
    this.busy.set(true);
    this.api.cancelInvoice(inv.id, reason).subscribe({
      next: () => this.done('Invoice cancelled.'),
      error: (err: unknown) => this.fail(err, this.error),
    });
  }

  protected reverse(p: Payment): void {
    const reason = this.reasonControl.value.trim();
    if (!reason) {
      this.error.set('Enter a reason for reversing the payment.');
      return;
    }
    this.busy.set(true);
    this.api.reversePayment(p.id, reason).subscribe({
      next: () => this.done(`Payment ${p.receipt_no} reversed.`),
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
