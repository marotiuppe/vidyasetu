import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { Collection, FeesApi, PaymentMethod } from '../../core/api/fees.api';
import { AuthService } from '../../core/auth/auth.service';
import { CREATE_NEW, createPermissions, isCreateNewChange } from '../../core/create/create-new';
import { ReturnStateService } from '../../core/create/return-state.service';
import { I18n } from '../../core/i18n/i18n';
import { formatPaise, percentOf } from '../../core/ui/money';
import { monthStartIso, todayIso, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';

@Component({
  selector: 'sms-fee-collection',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-collection.html',
  styleUrl: './fee-collection.css',
})
export class FeeCollection {
  private readonly api = inject(FeesApi);
  private readonly auth = inject(AuthService);
  protected readonly lookups = inject(FeeLookups);
  private readonly router = inject(Router);
  private readonly returnState = inject(ReturnStateService);
  protected readonly i18n = inject(I18n);
  protected readonly createNew = CREATE_NEW;
  protected readonly canCreate = createPermissions(this.auth);

  protected readonly money = formatPaise;
  protected readonly onValue = value;
  protected readonly today = todayIso();
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly from = signal(monthStartIso());
  protected readonly to = signal(todayIso());
  protected readonly branchId = signal(0);
  protected readonly data = signal<Collection | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  /** Branch picked: "Create new..." opens the Branches screen and brings the page back. */
  protected onBranch(event: Event): void {
    if (isCreateNewChange(event)) {
      this.returnState.openCreate('branch', { from: this.from(), to: this.to() }, 'Fees');
      return;
    }
    this.branchId.set(+this.onValue(event));
  }

  protected readonly rangeInvalid = computed(
    () => !this.from() || !this.to() || this.from() > this.to(),
  );
  protected readonly maxDay = computed(() =>
    Math.max(0, ...(this.data()?.by_day.map((d) => d.total_paise) ?? [])),
  );

  constructor() {
    const back = this.returnState.take(this.router.url);
    if (back) {
      const draft = back.draft as { from: string; to: string };
      this.from.set(draft.from);
      this.to.set(draft.to);
      this.branchId.set(back.createdId ?? 0);
      this.lookups.refresh();
    }
    if (this.canPickBranch) this.lookups.loadBranches();
    toObservable(computed(() => ({ from: this.from(), to: this.to(), branch: this.branchId() })))
      .pipe(
        debounceTime(200),
        filter(() => !this.rangeInvalid()),
        tap(() => {
          this.error.set(null);
          this.loading.set(true);
        }),
        switchMap((s) =>
          this.api.collection(s.from, s.to, s.branch).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.data.set(res);
        this.loading.set(false);
      });
  }

  protected pct(part: number, total: number): number {
    return percentOf(part, total);
  }

  protected methodText(method: PaymentMethod): string {
    return this.i18n.t(`fees.daily.method.${method}`);
  }

  protected paymentCount(count: number): string {
    return this.i18n.t(
      count === 1 ? 'fees.daily.count.payment.one' : 'fees.daily.count.payment.other',
      { count },
    );
  }
}
