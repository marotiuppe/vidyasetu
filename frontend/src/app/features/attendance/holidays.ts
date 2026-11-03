import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { catchError, of, switchMap, tap } from 'rxjs';

import { AcademicsApi, Branch } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { AttendanceApi, Holiday } from '../../core/api/attendance.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { localeOf } from '../../core/ui/dates';
import { Icon } from '../../core/ui/icon';
import { formatDate, isoDate, parseIso } from './attendance-labels';

@Component({
  selector: 'sms-holidays',
  imports: [ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './holidays.html',
  styleUrl: './holidays.css',
})
export class Holidays {
  private readonly api = inject(AttendanceApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);

  private readonly user = this.auth.user();
  protected readonly isOwner = this.auth.hasRole('school_owner');
  protected readonly canWrite = this.auth.hasRole('school_owner', 'management', 'headmaster');
  protected readonly formatDate = formatDate;
  protected readonly i18n = inject(I18n);

  protected readonly branches = signal<Branch[]>([]);
  protected readonly holidays = signal<Holiday[]>([]);
  /** `year` is the academic year name, or null for the next 12 months. */
  protected readonly range = signal<{ from: string; to: string; year: string | null } | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  private readonly reloadTick = signal(0);

  protected readonly form = this.fb.group({
    date: ['', Validators.required],
    name: ['', [Validators.required, Validators.maxLength(120)]],
    scope: [0],
  });

  protected readonly groups = computed(() => {
    const locale = localeOf(this.i18n.lang());
    const names = new Map(this.branches().map((b) => [b.id, b.name]));
    const out: { key: string; label: string; items: (Holiday & { scopeLabel: string })[] }[] = [];
    for (const h of [...this.holidays()].sort((a, b) => a.date.localeCompare(b.date))) {
      const key = h.date.slice(0, 7);
      let group = out.find((g) => g.key === key);
      if (!group) {
        const label = parseIso(h.date).toLocaleDateString(locale, {
          month: 'long',
          year: 'numeric',
        });
        group = { key, label, items: [] };
        out.push(group);
      }
      const scopeLabel =
        h.branch_id === null
          ? this.i18n.t('ops.common.wholeSchool')
          : (names.get(h.branch_id) ?? this.i18n.t('ops.common.branch'));
      group.items.push({ ...h, scopeLabel });
    }
    return out;
  });

  constructor() {
    if (this.isOwner) {
      this.academics
        .branches()
        .subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
    }
    this.academics
      .years()
      .pipe(
        catchError(() => of([])),
        tap((years) => {
          const current = years.find((y) => y.is_current);
          const now = new Date();
          const end = new Date(now.getFullYear() + 1, now.getMonth(), now.getDate());
          this.range.set(
            current
              ? {
                  from: current.start_date,
                  to: current.end_date,
                  year: current.name,
                }
              : { from: isoDate(now), to: isoDate(end), year: null },
          );
        }),
        switchMap(() => this.loadStream()),
        takeUntilDestroyed(),
      )
      .subscribe();
  }

  private loadStream() {
    const r = this.range();
    this.loading.set(true);
    return this.api.holidays(r!.from, r!.to).pipe(
      tap((list) => {
        this.holidays.set(list);
        this.loading.set(false);
      }),
      catchError((err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
        return of([]);
      }),
    );
  }

  private reload(): void {
    this.loadStream().subscribe();
  }

  /** Heading for the period shown above the list. */
  protected rangeLabel(year: string | null): string {
    return year
      ? this.i18n.t('ops.hol.academicYear', { name: year })
      : this.i18n.t('ops.hol.next12');
  }

  protected canDelete(h: Holiday): boolean {
    return (
      this.isOwner ||
      (this.canWrite && h.branch_id !== null && h.branch_id === this.user?.branch_id)
    );
  }

  protected add(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.busy()) return;
    const v = this.form.getRawValue();
    const branchId = this.isOwner ? v.scope || null : (this.user?.branch_id ?? null);
    this.busy.set(true);
    this.error.set(null);
    this.notice.set(null);
    this.api.addHoliday({ date: v.date, name: v.name.trim(), branch_id: branchId }).subscribe({
      next: () => {
        this.busy.set(false);
        this.notice.set(this.i18n.t('ops.hol.added'));
        this.form.reset({ date: '', name: '', scope: v.scope });
        this.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected dateText(value: string): string {
    return formatDate(value, this.i18n.lang());
  }

  protected remove(h: Holiday): void {
    const prompt = this.i18n.t('ops.hol.deleteConfirm', {
      name: h.name,
      date: this.dateText(h.date),
    });
    if (!window.confirm(prompt)) return;
    this.error.set(null);
    this.notice.set(null);
    this.api.deleteHoliday(h.id).subscribe({
      next: () => {
        this.notice.set(this.i18n.t('ops.hol.deleted'));
        this.reload();
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }
}
