import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, debounceTime, of, switchMap, tap } from 'rxjs';

import { AcademicsApi, Branch } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  ADMISSION_STATUSES,
  AdmissionApp,
  AdmissionFilters,
  AdmissionStatus,
  AdmissionSummary,
  AdmissionsApi,
} from '../../core/api/admissions.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { sourceKey, statusBadge, statusKey } from './admission-labels';

const PAGE_SIZE = 25;

interface Filters {
  status: AdmissionStatus | '';
  q: string;
  branchId: number;
}

@Component({
  selector: 'sms-admission-list',
  imports: [RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admission-list.html',
  styleUrl: './admission-list.css',
})
export class AdmissionList {
  private readonly api = inject(AdmissionsApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  /** Filter tabs: "All" first, then every status. */
  protected readonly tabs: (AdmissionStatus | '')[] = ['', ...ADMISSION_STATUSES];
  protected readonly statusKey = statusKey;
  protected readonly sourceKey = sourceKey;
  protected readonly statusBadge = statusBadge;
  /** A school owner sees every branch and can narrow to one; branch-level staff see their own only. */
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly filters = signal<Filters>({ status: '', q: '', branchId: 0 });
  protected readonly page = signal(1);

  protected readonly items = signal<AdmissionApp[]>([]);
  protected readonly total = signal(0);
  protected readonly summary = signal<AdmissionSummary>({});
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  /** Count shown on the "All" tab: the sum of every status in scope. */
  protected readonly allCount = computed(() =>
    ADMISSION_STATUSES.reduce((sum, s) => sum + (this.summary()[s] ?? 0), 0),
  );
  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  constructor() {
    if (this.canPickBranch) {
      this.academics.branches().subscribe({
        next: (b) => this.branches.set(b),
        error: () => undefined,
      });
    }

    toObservable(computed(() => this.filters().branchId))
      .pipe(
        switchMap((branchId) =>
          this.api.summary(branchId || null).pipe(catchError(() => of({} as AdmissionSummary))),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((counts) => this.summary.set(counts));

    toObservable(computed(() => ({ f: this.filters(), page: this.page() })))
      .pipe(
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.list(this.toApiFilters(s.f), s.page, PAGE_SIZE).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.items.set(res?.items ?? []);
        this.total.set(res?.total ?? 0);
        this.loading.set(false);
      });
  }

  protected setStatus(status: AdmissionStatus | ''): void {
    this.patch({ status });
  }

  protected onSearch(e: Event): void {
    this.patch({ q: (e.target as HTMLInputElement).value });
  }

  protected onBranch(e: Event): void {
    this.patch({ branchId: Number((e.target as HTMLSelectElement).value) });
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.page.update((p) => p + 1);
  }

  protected countOf(status: AdmissionStatus | ''): number {
    return status === '' ? this.allCount() : (this.summary()[status] ?? 0);
  }

  private patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
    this.page.set(1);
  }

  private toApiFilters(f: Filters): AdmissionFilters {
    return {
      status: f.status,
      q: f.q,
      branch_id: f.branchId || null,
    };
  }
}
