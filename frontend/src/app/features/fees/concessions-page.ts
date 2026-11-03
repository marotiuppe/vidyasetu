import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, take, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  Concession,
  ConcessionFilters,
  ConcessionPage,
  FeeToolsApi,
} from '../../core/api/fee-tools.api';
import { Student } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { FEE_MANAGER_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise, paiseToInput } from '../../core/ui/money';
import { classSection, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';
import { ConcessionForm } from './concession-form';
import { FeeToolsNav } from './fee-tools-nav';
import { StudentPicker } from './student-picker';

const PAGE_SIZE = 25;

interface Filters {
  yearId: number;
  student: Student | null;
}

/** Concessions and scholarships by year, with add and deactivate for fee managers. */
@Component({
  selector: 'sms-concessions-page',
  imports: [Icon, FeeToolsNav, ConcessionForm, StudentPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './concessions-page.html',
})
export class ConcessionsPage {
  private readonly api = inject(FeeToolsApi);
  private readonly auth = inject(AuthService);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly canManage = this.auth.hasRole(...FEE_MANAGER_ROLES);
  protected readonly money = formatPaise;
  protected readonly onValue = value;

  protected readonly filters = signal<Filters>({ yearId: 0, student: null });
  protected readonly pickerOpen = signal(false);
  protected readonly page = signal(1);
  private readonly ready = signal(false);
  private readonly reloadTick = signal(0);

  protected readonly data = signal<ConcessionPage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly togglingId = signal(0);

  protected readonly total = computed(() => this.data()?.total ?? 0);
  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  constructor() {
    this.lookups.load();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => {
        this.filters.update((f) => ({ ...f, yearId: this.lookups.currentYearId() }));
        this.ready.set(true);
      });

    toObservable(
      computed(() => ({
        ready: this.ready(),
        f: this.filters(),
        page: this.page(),
        tick: this.reloadTick(),
      })),
    )
      .pipe(
        filter((s) => s.ready),
        debounceTime(200),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.concessions(this.toApi(s.f), s.page, PAGE_SIZE).pipe(
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

  protected onYear(event: Event): void {
    this.patch({ yearId: Number(value(event)) });
  }

  protected pickStudent(s: Student): void {
    this.patch({ student: s });
    this.pickerOpen.set(false);
  }

  protected clearStudent(): void {
    this.patch({ student: null });
  }

  protected togglePicker(): void {
    this.pickerOpen.update((open) => !open);
  }

  /** "Class - Section", or the translated "Not enrolled" when the student has no class. */
  protected classText(className: string | null, sectionName: string | null): string {
    return className ? classSection(className, sectionName) : this.i18n.t('fees.daily.notEnrolled');
  }

  /** Percent shows as "25% of the fee"; a fixed amount as "₹500.00 off". */
  protected valueText(c: Concession): string {
    if (c.kind === 'percent')
      return this.i18n.t('fees.tools.concessions.percentValue', { value: paiseToInput(c.value) });
    return this.i18n.t('fees.tools.concessions.fixedValue', { amount: this.money(c.value) });
  }

  protected toggleAria(c: Concession): string {
    return this.i18n.t(
      c.active ? 'fees.tools.concessions.deactivateAria' : 'fees.tools.concessions.reactivateAria',
      { name: c.name, student: c.student_name },
    );
  }

  protected toggle(c: Concession): void {
    this.togglingId.set(c.id);
    this.error.set(null);
    this.api.updateConcession(c.id, { active: !c.active }).subscribe({
      next: () => {
        this.togglingId.set(0);
        this.reload();
      },
      error: (err: unknown) => {
        this.togglingId.set(0);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected reload(): void {
    this.reloadTick.update((t) => t + 1);
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.page.update((p) => p + 1);
  }

  protected created(): void {
    this.page.set(1);
    this.reload();
  }

  private patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
    this.page.set(1);
  }

  private toApi(f: Filters): ConcessionFilters {
    return {
      academic_year_id: f.yearId || undefined,
      student_id: f.student?.id,
    };
  }
}
