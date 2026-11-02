import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';

import { apiErrorMessage } from '../../core/api/api-error';
import { AuditEntry, AuditFilters, PrivacyApi } from '../../core/api/privacy.api';
import { I18n } from '../../core/i18n/i18n';
import { formatDateTime } from '../../core/ui/dates';
import { saveBlob } from '../../core/ui/download';
import { Icon } from '../../core/ui/icon';

const PAGE_SIZE = 25;

/** Audit log viewer: who did what and when, with filters and a CSV export. */
@Component({
  selector: 'sms-audit',
  imports: [ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './audit.html',
  styleUrl: './audit.css',
})
export class Audit {
  private readonly api = inject(PrivacyApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly form = this.fb.group({
    from: [''],
    to: [''],
    action: [''],
    entity_type: [''],
    actor_id: [''],
  });

  protected readonly items = signal<AuditEntry[]>([]);
  protected readonly total = signal(0);
  protected readonly page = signal(1);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly exporting = signal(false);
  protected readonly dateError = signal(false);

  protected readonly from = computed(() =>
    this.total() === 0 ? 0 : (this.page() - 1) * PAGE_SIZE + 1,
  );
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  /** Filters as last applied (typing in the form does not reload until "Apply"). */
  private applied: AuditFilters = {};
  private token = 0;

  constructor() {
    this.load();
  }

  protected apply(): void {
    const value = this.form.getRawValue();
    this.dateError.set(Boolean(value.from && value.to && value.from > value.to));
    if (this.dateError()) return;
    this.applied = value;
    this.page.set(1);
    this.load();
  }

  protected clear(): void {
    this.form.reset();
    this.dateError.set(false);
    this.applied = {};
    this.page.set(1);
    this.load();
  }

  protected prev(): void {
    if (this.page() > 1) {
      this.page.update((p) => p - 1);
      this.load();
    }
  }

  protected next(): void {
    if (this.to() < this.total()) {
      this.page.update((p) => p + 1);
      this.load();
    }
  }

  protected exportCsv(): void {
    this.exporting.set(true);
    this.error.set(null);
    this.api.auditCsv(this.applied).subscribe({
      next: (blob) => {
        saveBlob(blob, 'audit-log.csv');
        this.exporting.set(false);
      },
      error: (err: unknown) => {
        this.exporting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected when(value: string): string {
    return formatDateTime(value, this.i18n.lang());
  }

  protected outcomeClass(outcome: string): string {
    if (outcome === 'ok') return 'badge-success';
    if (outcome === 'failed' || outcome === 'denied') return 'badge-danger';
    return 'badge-warn';
  }

  protected outcomeLabel(outcome: string): string {
    const key = 'audit.outcome.' + outcome;
    const text = this.i18n.t(key);
    return text === key ? outcome : text;
  }

  /** The free-form detail as short text; never rendered as HTML. */
  protected detail(entry: AuditEntry): string {
    const d = entry.detail;
    if (d === null || d === undefined || d === '') return '';
    return typeof d === 'string' ? d : JSON.stringify(d);
  }

  private load(): void {
    const token = ++this.token;
    this.loading.set(true);
    this.error.set(null);
    this.api.audit(this.applied, this.page(), PAGE_SIZE).subscribe({
      next: (res) => {
        if (token !== this.token) return;
        this.items.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        if (token !== this.token) return;
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
