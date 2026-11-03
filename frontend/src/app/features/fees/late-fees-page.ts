import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { filter, take } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { LATE_FEE_KEYS, LateFeeCandidate, FeeToolsApi } from '../../core/api/fee-tools.api';
import { SettingValue } from '../../core/api/settings.api';
import { I18n } from '../../core/i18n/i18n';
import { formatPaise, paiseToInput } from '../../core/ui/money';
import { classSection, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';
import { FeeToolsNav } from './fee-tools-nav';

/** Late-fee rule as the school set it in Settings. Missing values fall back to "off". */
interface Rule {
  type: string;
  amount: number;
  graceDays: number;
  maxPaise: number;
}

function num(v: SettingValue | undefined): number {
  return typeof v === 'number' ? v : Number(v) || 0;
}

/** Preview overdue invoices and apply late fees to the ones you pick. The server checks every rule. */
@Component({
  selector: 'sms-late-fees-page',
  imports: [RouterLink, FeeToolsNav],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './late-fees-page.html',
})
export class LateFeesPage {
  private readonly api = inject(FeeToolsApi);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly money = formatPaise;

  protected readonly yearId = signal(0);
  /** Null until the settings are read; then the school's rule. */
  protected readonly rule = signal<Rule | null>(null);
  /** The server said late fees are off (409), even if the setting could not be read. */
  protected readonly offFromServer = signal(false);
  protected readonly off = computed(
    () => this.offFromServer() || (this.rule()?.type ?? '') === 'none',
  );
  protected readonly ruleLines = computed(() => this.describeRule(this.rule()));

  protected readonly candidates = signal<LateFeeCandidate[] | null>(null);
  protected readonly selected = signal<number[]>([]);
  protected readonly finding = signal(false);
  protected readonly applying = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly allSelected = computed(() => {
    const list = this.candidates() ?? [];
    return list.length > 0 && list.every((c) => this.selected().includes(c.invoice_id));
  });
  protected readonly chosenTotal = computed(() =>
    (this.candidates() ?? [])
      .filter((c) => this.selected().includes(c.invoice_id))
      .reduce((sum, c) => sum + c.late_fee_paise, 0),
  );

  constructor() {
    this.lookups.load();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => this.yearId.set(this.lookups.currentYearId()));

    this.api
      .settingValues(LATE_FEE_KEYS)
      .pipe(takeUntilDestroyed())
      .subscribe((v) => {
        if (v['fees.late_fee_type'] === undefined) return;
        this.rule.set({
          type: String(v['fees.late_fee_type']),
          amount: num(v['fees.late_fee_amount']),
          graceDays: num(v['fees.late_fee_grace_days']),
          maxPaise: num(v['fees.late_fee_max_paise']),
        });
      });
  }

  protected classText(c: LateFeeCandidate): string {
    return c.class_name ? classSection(c.class_name, c.section_name) : '';
  }

  protected checkedOf(event: Event): boolean {
    return (event.target as HTMLInputElement).checked;
  }

  protected onYear(event: Event): void {
    this.yearId.set(Number(value(event)));
    this.clearList();
  }

  protected find(): void {
    if (!this.yearId()) return;
    this.finding.set(true);
    this.error.set(null);
    this.notice.set(null);
    this.api.latePreview(this.yearId()).subscribe({
      next: (res) => {
        if (!res.enabled) this.offFromServer.set(true);
        const list = res.items;
        this.candidates.set(list);
        this.selected.set(list.map((c) => c.invoice_id));
        this.finding.set(false);
      },
      error: (err: unknown) => {
        this.finding.set(false);
        if (isLateFeeOff(err)) this.offFromServer.set(true);
        else this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected toggleAll(checked: boolean): void {
    this.selected.set(checked ? (this.candidates() ?? []).map((c) => c.invoice_id) : []);
  }

  protected toggleOne(invoiceId: number, checked: boolean): void {
    this.selected.update((list) =>
      checked
        ? [...list.filter((id) => id !== invoiceId), invoiceId]
        : list.filter((id) => id !== invoiceId),
    );
  }

  protected isSelected(invoiceId: number): boolean {
    return this.selected().includes(invoiceId);
  }

  protected apply(): void {
    this.error.set(null);
    this.notice.set(null);
    const ids = this.selected();
    if (!ids.length) return this.error.set(this.i18n.t('fees.tools.late.pickOne'));
    this.applying.set(true);
    this.api.lateApply({ academic_year_id: this.yearId(), invoice_ids: ids }).subscribe({
      next: (res) => {
        this.applying.set(false);
        this.notice.set(
          this.i18n.t('fees.tools.late.result', { created: res.created, skipped: res.skipped }),
        );
        this.find();
      },
      error: (err: unknown) => {
        this.applying.set(false);
        if (isLateFeeOff(err)) this.offFromServer.set(true);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private clearList(): void {
    this.candidates.set(null);
    this.selected.set([]);
    this.error.set(null);
    this.notice.set(null);
  }

  /** One line per part of the rule, in the current language; empty when the rule is unknown. */
  private describeRule(rule: Rule | null): string[] {
    if (!rule || rule.type === 'none') return [];
    const lines: string[] = [];
    if (rule.type === 'flat') {
      lines.push(this.i18n.t('fees.tools.late.ruleFlat', { amount: this.money(rule.amount) }));
    } else if (rule.type === 'percent') {
      lines.push(
        this.i18n.t('fees.tools.late.rulePercent', { percent: paiseToInput(rule.amount) }),
      );
    }
    lines.push(
      rule.graceDays > 0
        ? this.i18n.t('fees.tools.late.ruleGrace', { days: rule.graceDays })
        : this.i18n.t('fees.tools.late.ruleGraceNone'),
    );
    lines.push(
      rule.maxPaise > 0
        ? this.i18n.t('fees.tools.late.ruleCap', { amount: this.money(rule.maxPaise) })
        : this.i18n.t('fees.tools.late.ruleNoCap'),
    );
    return lines;
  }
}

/** The server answers 409 with code late_fee_disabled while the school has no late-fee type. */
function isLateFeeOff(err: unknown): boolean {
  return (
    err instanceof HttpErrorResponse &&
    err.status === 409 &&
    (err.error as { code?: unknown } | null)?.code === 'late_fee_disabled'
  );
}
