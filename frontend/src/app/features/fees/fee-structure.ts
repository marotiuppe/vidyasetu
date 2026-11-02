import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Params, Router } from '@angular/router';
import { catchError, filter, of, switchMap, take, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeeHead, FeesApi, StructureItem } from '../../core/api/fees.api';
import { AuthService } from '../../core/auth/auth.service';
import {
  CREATE_NEW,
  CREATE_NEW_LABEL,
  CreateKind,
  createPermissions,
  isCreateNewChange,
} from '../../core/create/create-new';
import { ReturnStateService, restoreIds } from '../../core/create/return-state.service';
import { Icon } from '../../core/ui/icon';
import { formatPaise, paiseToInput, parseRupeesToPaise } from '../../core/ui/money';
import { FeeLookups } from './fee-lookups';

/** Edit the fee heads and amounts for one class and academic year. Save replaces the structure. */
@Component({
  selector: 'sms-fee-structure',
  imports: [ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-structure.html',
})
export class FeeStructure {
  private readonly api = inject(FeesApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly lookups = inject(FeeLookups);
  private readonly router = inject(Router);
  private readonly returnState = inject(ReturnStateService);
  protected readonly createNew = CREATE_NEW;
  protected readonly createNewLabel = CREATE_NEW_LABEL;
  protected readonly canCreate = createPermissions(this.auth);

  readonly heads = input.required<FeeHead[]>();

  protected readonly money = formatPaise;
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly picker = this.fb.group({ branchId: [0], yearId: [0], classId: [0] });
  private readonly picked = toSignal(this.picker.valueChanges, {
    initialValue: this.picker.getRawValue(),
  });
  protected readonly rows = this.fb.array([this.newRow(0, '')]);
  private readonly rowValues = toSignal(this.rows.valueChanges, {
    initialValue: this.rows.getRawValue(),
  });

  protected readonly loading = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly classOptions = computed(() =>
    this.lookups.classesOf(Number(this.picked().branchId)),
  );
  protected readonly ready = computed(() => !!this.picked().yearId && !!this.picked().classId);
  protected readonly total = computed(() =>
    (this.rowValues() ?? []).reduce(
      (sum, r) => sum + (parseRupeesToPaise(r?.amount ?? '') ?? 0),
      0,
    ),
  );

  constructor() {
    // Back from a create screen: the branch, year and class picked before the create come back.
    const back = this.returnState.take(this.router.url);
    if (back) {
      const d = back.draft as { picker: { branchId: number; yearId: number; classId: number } };
      this.picker.patchValue(
        restoreIds(back, d.picker, {
          branch: 'branchId',
          academic_year: 'yearId',
          class: 'classId',
        }),
      );
      this.lookups.refresh();
    } else {
      this.lookups.load();
    }
    if (this.canPickBranch) this.lookups.loadBranches();
    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => {
        if (!back) this.picker.controls.yearId.setValue(this.lookups.currentYearId());
      });
    this.watchCreate(this.picker.controls.branchId, 'branch');
    this.watchCreate(this.picker.controls.yearId, 'academic_year');
    this.watchCreate(this.picker.controls.classId, 'class');

    toObservable(
      computed(() => ({ y: Number(this.picked().yearId), c: Number(this.picked().classId) })),
    )
      .pipe(
        tap(() => {
          this.error.set(null);
          this.notice.set(null);
        }),
        switchMap((s) => {
          if (!s.y || !s.c) return of(null);
          this.loading.set(true);
          return this.api.structure(s.y, s.c).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((items) => {
        this.loading.set(false);
        this.fill(items ?? []);
      });
  }

  private newRow(headId: number, amount: string) {
    return this.fb.group({ headId: [headId], amount: [amount] });
  }

  private fill(items: StructureItem[]): void {
    this.rows.clear();
    for (const i of items) this.rows.push(this.newRow(i.fee_head_id, paiseToInput(i.amount_paise)));
    if (!items.length) this.rows.push(this.newRow(0, ''));
  }

  /** Active heads, plus the one already chosen on this row (it may have been deactivated). */
  protected optionsFor(rowIndex: number): FeeHead[] {
    const current = this.rows.at(rowIndex).controls.headId.value;
    return this.heads().filter((h) => h.is_active || h.id === current);
  }

  protected addRow(): void {
    this.rows.push(this.newRow(0, ''));
  }

  protected removeRow(i: number): void {
    this.rows.removeAt(i);
    if (!this.rows.length) this.addRow();
  }

  /** "+ Create new..." in the picker: keep the picks and open the create screen. */
  private watchCreate(
    control: { valueChanges: import('rxjs').Observable<number> },
    kind: CreateKind,
  ): void {
    control.valueChanges
      .pipe(
        filter((v) => v === CREATE_NEW),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        const extra: Params = {};
        const branchId = Number(this.picker.controls.branchId.value);
        if (kind === 'class' && branchId > 0) extra['branchId'] = branchId;
        this.returnState.openCreate(
          kind,
          { picker: this.picker.getRawValue() },
          'Fee setup',
          extra,
        );
      });
  }

  protected pickBranch(): void {
    this.picker.controls.classId.setValue(0);
  }

  protected save(): void {
    this.error.set(null);
    this.notice.set(null);
    const p = this.picker.getRawValue();
    if (!p.yearId || !p.classId) return this.error.set('Choose an academic year and a class.');

    const items: { fee_head_id: number; amount_paise: number }[] = [];
    const seen = new Set<number>();
    for (const [i, r] of this.rows.getRawValue().entries()) {
      if (!r.headId && !r.amount.trim()) continue; // untouched empty row
      const amount = parseRupeesToPaise(r.amount);
      if (!r.headId || amount === null || amount <= 0) {
        return this.error.set(
          `Row ${i + 1} needs a fee head and an amount in rupees above zero (up to 2 decimals).`,
        );
      }
      if (seen.has(r.headId)) return this.error.set('Each fee head can appear only once.');
      seen.add(r.headId);
      items.push({ fee_head_id: r.headId, amount_paise: amount });
    }

    this.busy.set(true);
    this.api.saveStructure({ academic_year_id: p.yearId, class_id: p.classId, items }).subscribe({
      next: (saved) => {
        this.busy.set(false);
        this.fill(saved);
        this.notice.set('Fee structure saved.');
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
