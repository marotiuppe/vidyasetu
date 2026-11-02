import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { Collection, FeesApi } from '../../core/api/fees.api';
import { AuthService } from '../../core/auth/auth.service';
import { formatPaise, percentOf } from '../../core/ui/money';
import { methodLabel, monthStartIso, todayIso, value } from './fee-labels';
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

  protected readonly money = formatPaise;
  protected readonly methodLabel = methodLabel;
  protected readonly onValue = value;
  protected readonly today = todayIso();
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly from = signal(monthStartIso());
  protected readonly to = signal(todayIso());
  protected readonly branchId = signal(0);
  protected readonly data = signal<Collection | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly rangeInvalid = computed(() => !this.from() || !this.to() || this.from() > this.to());
  protected readonly maxDay = computed(() => Math.max(0, ...(this.data()?.by_day.map((d) => d.total_paise) ?? [])));

  constructor() {
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
}
