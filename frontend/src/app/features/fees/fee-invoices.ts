import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { Params, Router } from '@angular/router';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, filter, of, switchMap, take, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import {
  CREATE_NEW,
  CREATE_NEW_LABEL,
  CreateKind,
  FILTER_KINDS,
  createPermissions,
  isCreateNewChange,
} from '../../core/create/create-new';
import { ReturnStateService, restoreIds } from '../../core/create/return-state.service';
import {
  FeesApi,
  INVOICE_STATUSES,
  Invoice,
  InvoiceFilters,
  InvoicePage,
  InvoiceStatus,
} from '../../core/api/fees.api';
import { Icon } from '../../core/ui/icon';
import { formatPaise } from '../../core/ui/money';
import { classSection, invoiceStatusClass, invoiceStatusLabel, value } from './fee-labels';
import { FeeLookups } from './fee-lookups';
import { InvoiceGenerate } from './invoice-generate';
import { InvoiceNew } from './invoice-new';
import { InvoicePanel } from './invoice-panel';

const PAGE_SIZE = 25;

interface Filters {
  yearId: number;
  classId: number;
  sectionId: number;
  status: InvoiceStatus | '';
  overdue: boolean;
  q: string;
}

type Mode = 'none' | 'generate' | 'new';

@Component({
  selector: 'sms-fee-invoices',
  imports: [Icon, InvoicePanel, InvoiceGenerate, InvoiceNew],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-invoices.html',
  styleUrl: './fee-invoices.css',
})
export class FeeInvoices {
  private readonly api = inject(FeesApi);
  protected readonly lookups = inject(FeeLookups);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly returnState = inject(ReturnStateService);
  protected readonly createNew = CREATE_NEW;
  protected readonly createNewLabel = CREATE_NEW_LABEL;
  protected readonly canCreate = createPermissions(this.auth);

  readonly canManage = input(false);
  readonly canPay = input(false);

  protected readonly statuses = INVOICE_STATUSES;
  protected readonly statusLabel = invoiceStatusLabel;
  protected readonly statusClass = invoiceStatusClass;
  protected readonly classSection = classSection;
  protected readonly money = formatPaise;
  protected readonly onValue = value;

  protected readonly filters = signal<Filters>({
    yearId: 0,
    classId: 0,
    sectionId: 0,
    status: '',
    overdue: false,
    q: '',
  });
  protected readonly page = signal(1);
  private readonly ready = signal(false);
  private readonly reloadTick = signal(0);

  protected readonly data = signal<InvoicePage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly selectedId = signal(0);
  protected readonly mode = signal<Mode>('none');

  protected readonly sectionOptions = computed(() =>
    this.lookups.sectionsOf(this.filters().classId),
  );
  protected readonly total = computed(() => this.data()?.total ?? 0);
  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  constructor() {
    const back = this.returnState.take(this.router.url);
    if (back)
      this.filters.set(
        restoreIds(back, this.filters(), {
          academic_year: 'yearId',
          class: 'classId',
          section: 'sectionId',
        }),
      );
    if (back) this.lookups.refresh();
    else this.lookups.load();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => {
        if (!back) this.filters.update((f) => ({ ...f, yearId: this.lookups.currentYearId() }));
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
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.invoices(this.toApi(s.f), s.page, PAGE_SIZE).pipe(
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

  protected onSelect(key: 'yearId' | 'classId' | 'sectionId', event: Event): void {
    if (isCreateNewChange(event)) {
      this.createRecord(FILTER_KINDS[key]);
      return;
    }
    const v = Number(value(event));
    this.patch(key === 'classId' ? { classId: v, sectionId: 0 } : { [key]: v });
  }

  /** Open the create screen for a missing record; the filters come back with it selected. */
  protected createRecord(kind: CreateKind): void {
    const f = this.filters();
    const extra: Params = kind === 'section' ? { classId: f.classId } : {};
    this.returnState.openCreate(kind, f, 'Fees', extra);
  }

  protected onStatus(event: Event): void {
    this.patch({ status: value(event) as InvoiceStatus | '' });
  }

  protected onOverdue(event: Event): void {
    this.patch({ overdue: (event.target as HTMLInputElement).checked });
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.page.update((p) => p + 1);
  }

  protected open(inv: Invoice): void {
    this.mode.set('none');
    this.selectedId.set(inv.id);
    queueMicrotask(() =>
      document.getElementById('invoice-detail')?.scrollIntoView({ block: 'nearest' }),
    );
  }

  protected setMode(mode: Mode): void {
    this.selectedId.set(0);
    this.mode.set(this.mode() === mode ? 'none' : mode);
  }

  protected reload(): void {
    this.reloadTick.update((t) => t + 1);
  }

  protected generated(): void {
    this.page.set(1);
    this.reload();
  }

  protected created(id: number): void {
    this.mode.set('none');
    this.selectedId.set(id);
    this.page.set(1);
    this.reload();
  }

  protected patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
    this.page.set(1);
  }

  private toApi(f: Filters): InvoiceFilters {
    return {
      academic_year_id: f.yearId || undefined,
      class_id: f.classId || undefined,
      section_id: f.sectionId || undefined,
      status: f.status,
      q: f.q,
      overdue: f.overdue,
    };
  }
}
