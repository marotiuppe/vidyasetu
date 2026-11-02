import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage } from '../../core/api/api-error';
import { DataRequest, DataRequestStatus, PrivacyApi } from '../../core/api/privacy.api';
import { I18n } from '../../core/i18n/i18n';
import { formatDate, formatDateTime, todayIst } from '../../core/ui/dates';
import { focusById } from '../../core/ui/download';

const STATUSES: DataRequestStatus[] = ['open', 'in_progress', 'completed', 'rejected'];

/** Staff inbox for data access, correction and erasure requests. */
@Component({
  selector: 'sms-data-requests',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './data-requests.html',
  styleUrl: './data-requests.css',
})
export class DataRequests {
  private readonly api = inject(PrivacyApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly statuses = STATUSES;
  protected readonly filter = signal<DataRequestStatus | ''>('open');
  protected readonly items = signal<DataRequest[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly openId = signal<number | null>(null);
  protected readonly saving = signal(false);
  protected readonly editError = signal<string | null>(null);

  protected readonly form = this.fb.group({
    status: ['in_progress' as DataRequestStatus, Validators.required],
    response_note: ['', Validators.maxLength(2000)],
  });

  private readonly today = todayIst();
  private token = 0;

  constructor() {
    this.load();
  }

  protected onFilter(event: Event): void {
    this.filter.set((event.target as HTMLSelectElement).value as DataRequestStatus | '');
    this.openId.set(null);
    this.load();
  }

  protected isOverdue(r: DataRequest): boolean {
    return (
      r.due_on !== null &&
      r.due_on < this.today &&
      (r.status === 'open' || r.status === 'in_progress')
    );
  }

  protected date(value: string | null): string {
    return formatDate(value, this.i18n.lang());
  }

  protected dateTime(value: string): string {
    return formatDateTime(value, this.i18n.lang());
  }

  protected open(r: DataRequest): void {
    this.openId.set(r.id);
    this.editError.set(null);
    this.notice.set(null);
    this.form.reset({
      status: r.status === 'open' ? 'in_progress' : r.status,
      response_note: r.response_note ?? '',
    });
    focusById('request-status');
  }

  protected close(): void {
    this.openId.set(null);
  }

  protected save(r: DataRequest): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    const { status, response_note } = this.form.getRawValue();
    if ((status === 'completed' || status === 'rejected') && !response_note.trim()) {
      this.editError.set(this.i18n.t('requests.noteRequired'));
      return;
    }
    this.saving.set(true);
    this.editError.set(null);
    this.api.updateRequest(r.id, { status, response_note: response_note.trim() }).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.openId.set(null);
        this.items.update((list) => list.map((x) => (x.id === updated.id ? updated : x)));
        this.notice.set(this.i18n.t('requests.saved'));
        this.load(true);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.editError.set(apiErrorMessage(err));
      },
    });
  }

  private load(quiet = false): void {
    const token = ++this.token;
    if (!quiet) this.loading.set(true);
    this.error.set(null);
    this.api.requests(this.filter()).subscribe({
      next: (items) => {
        if (token !== this.token) return;
        this.items.set(items);
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
