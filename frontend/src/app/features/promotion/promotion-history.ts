import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  PROMOTION_ACTIONS,
  PromotionAction,
  PromotionApi,
  PromotionBatch,
  PromotionBatchDetail,
} from '../../core/api/promotion.api';
import { I18n } from '../../core/i18n/i18n';
import { formatDateTime } from '../../core/ui/dates';
import { formatPaise } from '../../core/ui/money';
import { actionKey, canUndo, isUndone } from './promotion-model';

const PAGE_SIZE = 10;

/** Past promotion runs, newest first. Each run can be opened for its students and undone in time. */
@Component({
  selector: 'sms-promotion-history',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './promotion-history.html',
  styleUrl: './promotion-history.css',
})
export class PromotionHistory {
  private readonly api = inject(PromotionApi);
  protected readonly i18n = inject(I18n);

  /** Changes when a run is applied or undone elsewhere on the page, which reloads the list. */
  readonly version = input(0);
  /** The run as it is after an undo, so the parent can update its own copy. */
  readonly undone = output<PromotionBatch>();

  protected readonly actions: PromotionAction[] = PROMOTION_ACTIONS;
  protected readonly actionKey = actionKey;
  protected readonly money = formatPaise;
  protected readonly canUndo = canUndo;
  protected readonly isUndone = isUndone;

  protected readonly page = signal(1);
  protected readonly batches = signal<PromotionBatch[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly expanded = signal<number | null>(null);
  protected readonly undoingId = signal<number | null>(null);
  protected readonly details = signal<Record<number, PromotionBatchDetail>>({});

  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  constructor() {
    toObservable(computed(() => ({ v: this.version(), p: this.page() })))
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.batches(s.p, PAGE_SIZE).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.batches.set(res?.items ?? []);
        this.total.set(res?.total ?? 0);
        this.loading.set(false);
      });
  }

  protected formatWhen(value: string): string {
    return formatDateTime(value, this.i18n.lang());
  }

  /** Status badge text: undone, can still be undone (until when), or final. */
  protected stateText(batch: PromotionBatch): string {
    if (isUndone(batch)) return this.i18n.t('promotion.history.undone');
    if (canUndo(batch)) {
      return this.i18n.t('promotion.history.undoUntil', {
        time: this.formatWhen(batch.undo_until),
      });
    }
    return this.i18n.t('promotion.history.final');
  }

  protected stateBadge(batch: PromotionBatch): string {
    if (isUndone(batch)) return 'badge-muted';
    return canUndo(batch) ? 'badge-warn' : 'badge-success';
  }

  protected toggle(batch: PromotionBatch): void {
    if (this.expanded() === batch.id) {
      this.expanded.set(null);
      return;
    }
    this.expanded.set(batch.id);
    if (this.details()[batch.id]) return;
    this.api.batch(batch.id).subscribe({
      next: (detail) => this.details.update((d) => ({ ...d, [batch.id]: detail })),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  protected undo(batch: PromotionBatch): void {
    this.undoingId.set(batch.id);
    this.error.set(null);
    this.api.undo(batch.id).subscribe({
      next: (updated) => {
        const merged: PromotionBatch = { ...batch, ...updated };
        this.undoingId.set(null);
        this.batches.update((list) => list.map((b) => (b.id === batch.id ? merged : b)));
        this.details.update((d) => {
          const next = { ...d };
          delete next[batch.id];
          return next;
        });
        this.undone.emit(merged);
      },
      error: (err: unknown) => {
        this.undoingId.set(null);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.page.update((p) => p + 1);
  }
}
