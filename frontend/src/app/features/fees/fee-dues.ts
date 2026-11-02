import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Params, Router } from '@angular/router';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, take, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { DuesFilters, Dues, FeesApi } from '../../core/api/fees.api';
import { AuthService } from '../../core/auth/auth.service';
import {
  CREATE_NEW,
  CreateKind,
  FILTER_FIELDS,
  FILTER_KINDS,
  createPermissions,
  isCreateNewChange,
} from '../../core/create/create-new';
import { ReturnStateService, restoreIds } from '../../core/create/return-state.service';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise, parseRupeesToPaise } from '../../core/ui/money';
import { classSection, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';

interface Filters {
  yearId: number;
  branchId: number;
  classId: number;
  sectionId: number;
  minBalance: string;
}

@Component({
  selector: 'sms-fee-dues',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-dues.html',
  styleUrl: './fee-dues.css',
})
export class FeeDues {
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
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly filters = signal<Filters>({
    yearId: 0,
    branchId: 0,
    classId: 0,
    sectionId: 0,
    minBalance: '',
  });
  private readonly ready = signal(false);
  protected readonly data = signal<Dues | null>(null);
  protected readonly loading = signal(true);
  protected readonly exporting = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly classOptions = computed(() => this.lookups.classesOf(this.filters().branchId));
  protected readonly sectionOptions = computed(() =>
    this.lookups.sectionsOf(this.filters().classId),
  );
  protected readonly minBalanceInvalid = computed(() => {
    const text = this.filters().minBalance.trim();
    return text !== '' && parseRupeesToPaise(text) === null;
  });

  constructor() {
    const back = this.returnState.take(this.router.url);
    if (back) this.filters.set(restoreIds(back, this.filters(), FILTER_FIELDS));
    if (back) this.lookups.refresh();
    else this.lookups.load();
    if (this.canPickBranch) this.lookups.loadBranches();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => {
        if (!back) this.filters.update((f) => ({ ...f, yearId: this.lookups.currentYearId() }));
        this.ready.set(true);
      });

    toObservable(computed(() => ({ ready: this.ready(), f: this.filters() })))
      .pipe(
        filter((s) => s.ready),
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) => {
          if (this.minBalanceInvalid()) return of(null);
          return this.api.dues(this.toApi(s.f)).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.data.set(res);
        this.loading.set(false);
      });
  }

  protected patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
  }

  /** "Class - Section", or the translated "Not enrolled" when the student has no class. */
  protected classText(className: string | null, sectionName: string | null): string {
    return className ? classSection(className, sectionName) : this.i18n.t('fees.daily.notEnrolled');
  }

  protected onSelect(key: 'yearId' | 'branchId' | 'classId' | 'sectionId', event: Event): void {
    if (isCreateNewChange(event)) {
      this.createRecord(FILTER_KINDS[key]);
      return;
    }
    const v = Number(value(event));
    if (key === 'branchId') this.patch({ branchId: v, classId: 0, sectionId: 0 });
    else if (key === 'classId') this.patch({ classId: v, sectionId: 0 });
    else this.patch({ [key]: v });
  }

  /** Open the create screen for a missing record; the filters come back with it selected. */
  protected createRecord(kind: CreateKind): void {
    const f = this.filters();
    const extra: Params =
      kind === 'section'
        ? { classId: f.classId }
        : kind === 'class' && f.branchId
          ? { branchId: f.branchId }
          : {};
    this.returnState.openCreate(kind, f, 'Fees', extra);
  }

  protected exportCsv(): void {
    if (this.minBalanceInvalid()) return;
    this.exporting.set(true);
    this.error.set(null);
    this.api.duesCsv(this.toApi(this.filters())).subscribe({
      next: (blob) => {
        this.api.saveBlob(blob, 'fee-dues.csv');
        this.exporting.set(false);
      },
      error: (err: unknown) => {
        this.exporting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
  private toApi(f: Filters): DuesFilters {
    return {
      academic_year_id: f.yearId || undefined,
      branch_id: f.branchId || undefined,
      class_id: f.classId || undefined,
      section_id: f.sectionId || undefined,
      min_balance_paise: parseRupeesToPaise(f.minBalance) || undefined,
    };
  }
}
