import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, of, switchMap, tap } from 'rxjs';

import { AcademicsApi, Branch } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { AttendanceApi, DailySummary } from '../../core/api/attendance.api';
import { AuthService } from '../../core/auth/auth.service';
import { isoDate, percent } from './attendance-labels';

@Component({
  selector: 'sms-attendance-summary',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-summary.html',
  styleUrl: './attendance-summary.css',
})
export class AttendanceSummary {
  private readonly api = inject(AttendanceApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);

  /** Show the "Mark" link on each section. */
  readonly canMark = input(false);

  protected readonly today = isoDate(new Date());
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;
  protected readonly branches = signal<Branch[]>([]);
  protected readonly date = signal(this.today);
  protected readonly branchId = signal(0);

  protected readonly data = signal<DailySummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly presentPercent = percent;
  protected readonly totalPercent = computed(() => {
    const t = this.data()?.totals;
    return t ? percent(t.present, t.total - t.unmarked) : null;
  });

  constructor() {
    if (this.canPickBranch) {
      this.academics.branches().subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
    }
    toObservable(computed(() => ({ date: this.date(), branch: this.branchId() })))
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.dailySummary(s.date, s.branch || null).pipe(
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

  protected pickDate(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    if (value && value <= this.today) this.date.set(value);
    else (event.target as HTMLInputElement).value = this.date();
  }

  protected pickBranch(event: Event): void {
    this.branchId.set(Number((event.target as HTMLSelectElement).value));
  }
}
