import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, take, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  FeeToolsApi,
  REMINDER_MARK_LIMIT,
  REMINDER_TEMPLATE_KEY,
  ReminderFilters,
  ReminderPage,
  ReminderRow,
} from '../../core/api/fee-tools.api';
import { AuthService } from '../../core/auth/auth.service';
import { FEE_MANAGER_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { copyText } from '../../core/ui/clipboard';
import { formatDate } from '../../core/ui/dates';
import { Icon } from '../../core/ui/icon';
import { formatPaise, parseRupeesToPaise } from '../../core/ui/money';
import { classSection, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';
import { FeeToolsNav } from './fee-tools-nav';
import { fillReminderTemplate } from './fee-tools-model';

const PAGE_SIZE = 25;
const MAX_DAYS = 365;

interface Filters {
  yearId: number;
  classId: number;
  minBalance: string;
  overdueOnly: boolean;
  days: string;
}

/** Find families with dues, copy a reminder text and mark them as reminded. Nothing is sent. */
@Component({
  selector: 'sms-reminders-page',
  imports: [FeeToolsNav, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reminders-page.html',
  styleUrl: './reminders-page.css',
})
export class RemindersPage {
  private readonly api = inject(FeeToolsApi);
  private readonly auth = inject(AuthService);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly canMark = this.auth.hasRole(...FEE_MANAGER_ROLES);
  protected readonly money = formatPaise;
  protected readonly onValue = value;
  protected readonly maxDays = MAX_DAYS;
  protected readonly markLimit = REMINDER_MARK_LIMIT;

  protected readonly filters = signal<Filters>({
    yearId: 0,
    classId: 0,
    minBalance: '',
    overdueOnly: true,
    days: '',
  });
  private readonly ready = signal(false);
  protected readonly page = signal(1);
  private readonly reloadTick = signal(0);

  protected readonly data = signal<ReminderPage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly selected = signal<number[]>([]);
  protected readonly exporting = signal(false);
  protected readonly marking = signal(false);

  /** The reminder text the school set in Settings, or the built-in default. */
  private readonly template = signal(this.i18n.t('fees.tools.reminders.defaultTemplate'));
  protected readonly activeRow = signal<ReminderRow | null>(null);
  protected readonly activeText = computed(() => {
    const row = this.activeRow();
    return row ? this.textFor(row) : '';
  });

  protected readonly minBalanceInvalid = computed(() => {
    const text = this.filters().minBalance.trim();
    return text !== '' && parseRupeesToPaise(text) === null;
  });
  protected readonly daysInvalid = computed(() => {
    const text = this.filters().days.trim();
    if (text === '') return false;
    return !/^\d{1,3}$/.test(text) || Number(text) > MAX_DAYS;
  });
  protected readonly invalid = computed(() => this.minBalanceInvalid() || this.daysInvalid());

  protected readonly total = computed(() => this.data()?.total ?? 0);
  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));
  protected readonly pageIds = computed(() => (this.data()?.items ?? []).map((r) => r.student_id));
  protected readonly allOnPage = computed(() => {
    const ids = this.pageIds();
    return ids.length > 0 && ids.every((id) => this.selected().includes(id));
  });

  constructor() {
    this.lookups.load();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => {
        this.filters.update((f) => ({ ...f, yearId: this.lookups.currentYearId() }));
        this.ready.set(true);
      });

    this.api
      .settingValues([REMINDER_TEMPLATE_KEY])
      .pipe(takeUntilDestroyed())
      .subscribe((v) => {
        const text = v[REMINDER_TEMPLATE_KEY];
        if (typeof text === 'string' && text.trim() !== '') this.template.set(text);
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
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) => {
          if (this.invalid()) return of(null);
          return this.api.reminders(this.toApi(s.f), s.page, PAGE_SIZE).pipe(
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

  protected onSelect(key: 'yearId' | 'classId', event: Event): void {
    this.patch({ [key]: Number(value(event)) });
  }

  protected onText(key: 'minBalance' | 'days', event: Event): void {
    this.patch({ [key]: value(event) });
  }

  protected onOverdue(event: Event): void {
    this.patch({ overdueOnly: (event.target as HTMLInputElement).checked });
  }

  protected classText(r: ReminderRow): string {
    return r.class_name ? classSection(r.class_name, null) : this.i18n.t('fees.daily.notEnrolled');
  }

  protected dateText(date: string | null): string {
    return date ? formatDate(date, this.i18n.lang()) : '';
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected toggleOne(id: number, checked: boolean): void {
    this.selected.update((list) =>
      checked ? [...list.filter((x) => x !== id), id] : list.filter((x) => x !== id),
    );
  }

  protected toggleAll(checked: boolean): void {
    this.selected.set(checked ? this.pageIds() : []);
  }

  protected checkedOf(event: Event): boolean {
    return (event.target as HTMLInputElement).checked;
  }

  protected showText(r: ReminderRow): void {
    this.activeRow.set(r);
    this.notice.set(null);
  }

  protected closeText(): void {
    this.activeRow.set(null);
  }

  protected copyActive(): void {
    const text = this.activeText();
    if (text) void this.copy(text, this.i18n.t('fees.tools.reminders.copyDone'));
  }

  protected copySelected(): void {
    const texts = (this.data()?.items ?? [])
      .filter((r) => this.isSelected(r.student_id))
      .map((r) => this.textFor(r));
    if (!texts.length) return;
    void this.copy(
      texts.join('\n\n'),
      this.i18n.t('fees.tools.reminders.copied', { count: texts.length }),
    );
  }

  protected markOne(r: ReminderRow): void {
    this.mark([r.student_id]);
  }

  protected markSelected(): void {
    this.mark(this.selected());
  }

  protected exportCsv(): void {
    if (this.invalid()) return;
    this.exporting.set(true);
    this.error.set(null);
    this.api.remindersCsv(this.toApi(this.filters())).subscribe({
      next: (blob) => {
        this.api.saveBlob(blob, 'fee-reminders.csv');
        this.exporting.set(false);
      },
      error: (err: unknown) => {
        this.exporting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected prev(): void {
    this.setPage(Math.max(1, this.page() - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.setPage(this.page() + 1);
  }

  /** The reminder text for one row, with the school's template filled in. */
  private textFor(r: ReminderRow): string {
    return fillReminderTemplate(this.template(), {
      guardian: r.guardian_name ?? this.i18n.t('fees.tools.reminders.parentFallback'),
      student: r.student_name,
      amount: this.money(r.balance_paise),
      date: this.dateText(r.oldest_due_date),
    });
  }

  private async copy(text: string, doneMessage: string): Promise<void> {
    const ok = await copyText(text);
    this.notice.set(ok ? doneMessage : null);
    this.error.set(ok ? null : this.i18n.t('fees.tools.reminders.copyFailed'));
  }

  private mark(ids: number[]): void {
    if (!ids.length || this.marking()) return;
    if (ids.length > REMINDER_MARK_LIMIT) {
      this.error.set(this.i18n.t('fees.tools.reminders.limit'));
      return;
    }
    this.marking.set(true);
    this.error.set(null);
    this.api.markReminded(ids).subscribe({
      next: (res) => {
        this.marking.set(false);
        this.selected.set([]);
        this.activeRow.set(null);
        this.notice.set(this.i18n.t('fees.tools.reminders.marked', { count: res.marked }));
        this.reloadTick.update((t) => t + 1);
      },
      error: (err: unknown) => {
        this.marking.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
    this.page.set(1);
    this.selected.set([]);
  }

  private setPage(p: number): void {
    this.page.set(p);
    this.selected.set([]);
  }

  private toApi(f: Filters): ReminderFilters {
    const days = Number(f.days.trim());
    return {
      academic_year_id: f.yearId || undefined,
      class_id: f.classId || undefined,
      min_balance_paise: parseRupeesToPaise(f.minBalance) || undefined,
      overdue_only: f.overdueOnly,
      days_before_due: days > 0 ? days : undefined,
    };
  }
}
