import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  FeesApi,
  InvoiceStatus,
  Payment,
  PaymentMethod,
  StudentFees,
} from '../../core/api/fees.api';
import { Student, StudentsApi } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise } from '../../core/ui/money';
import { invoiceStatusClass, value } from './fee-labels';

/** Parent and student view: summary, invoices (with line items) and payment receipts. */
@Component({
  selector: 'sms-my-fees',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './my-fees.html',
  styleUrl: './my-fees.css',
})
export class MyFees {
  private readonly api = inject(FeesApi);
  private readonly students = inject(StudentsApi);
  protected readonly i18n = inject(I18n);

  protected readonly money = formatPaise;
  protected readonly statusClass = invoiceStatusClass;

  protected readonly children = signal<Student[]>([]);
  protected readonly childId = signal(0);
  protected readonly childrenLoading = signal(true);
  protected readonly fees = signal<StudentFees | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly childName = computed(
    () => this.children().find((c) => c.id === this.childId())?.full_name ?? '',
  );

  constructor() {
    this.students.list({}, 1, 100).subscribe({
      next: (page) => {
        this.children.set(page.items);
        this.childId.set(page.items[0]?.id ?? 0);
        this.childrenLoading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.childrenLoading.set(false);
      },
    });

    toObservable(this.childId)
      .pipe(
        tap(() => this.fees.set(null)),
        switchMap((id) => {
          if (!id) return of(null);
          this.loading.set(true);
          return this.api.studentFees(id).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.fees.set(res);
        this.loading.set(false);
      });
  }

  protected pickChild(event: Event): void {
    this.error.set(null);
    this.childId.set(Number(value(event)));
  }

  protected methodText(method: PaymentMethod): string {
    return this.i18n.t(`fees.daily.method.${method}`);
  }

  protected statusText(status: InvoiceStatus): string {
    return this.i18n.t(`fees.daily.status.${status}`);
  }

  protected receipt(p: Payment): void {
    this.error.set(null);
    this.api
      .downloadReceipt(p)
      .subscribe({ error: (err: unknown) => this.error.set(apiErrorMessage(err)) });
  }
}
