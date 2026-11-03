import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormArray, FormGroup, NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { filter, map, take } from 'rxjs';

import { AcademicYear, SchoolClass } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  PROMOTION_ACTIONS,
  PromotionAction,
  PromotionApi,
  PromotionApplyInput,
  PromotionBatch,
  PromotionCandidate,
  PromotionItemInput,
  PromotionPreview,
} from '../../core/api/promotion.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { formatDate, formatDateTime } from '../../core/ui/dates';
import { formatPaise } from '../../core/ui/money';
import { FeeLookups } from '../fees/fee-lookups';
import { PromotionHistory } from './promotion-history';
import {
  PromotionRowForm,
  PromotionRowView,
  actionKey,
  addDays,
  canUndo,
  isUndone,
  newRowGroup,
  rowViewOf,
} from './promotion-model';
import { PromotionTable } from './promotion-table';

/** Years that start after `fromId`, earliest first. */
function laterYears(years: AcademicYear[], fromId: number): AcademicYear[] {
  const from = years.find((y) => y.id === fromId);
  if (!from) return [];
  return years
    .filter((y) => y.start_date > from.start_date)
    .sort((a, b) => a.start_date.localeCompare(b.start_date));
}

/**
 * Year-end promotion: pick the class and years, review one action per student, then apply the run.
 * The server does the work and checks every rule; this screen only keeps the choices clear.
 */
@Component({
  selector: 'sms-promotion',
  imports: [ReactiveFormsModule, PromotionTable, PromotionHistory],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './promotion.html',
  styleUrl: './promotion.css',
})
export class Promotion {
  private readonly api = inject(PromotionApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);
  private readonly confirm = viewChild<ElementRef<HTMLDialogElement>>('confirm');

  protected readonly money = formatPaise;
  protected readonly actions: PromotionAction[] = PROMOTION_ACTIONS;
  protected readonly actionKey = actionKey;
  protected readonly canUndo = canUndo;
  protected readonly isUndone = isUndone;
  protected readonly isOwner = this.auth.hasRole('school_owner');

  protected readonly setup = this.fb.group({
    fromYearId: [0],
    toYearId: [0],
    classId: [0],
    sectionId: [0],
    carryOver: [false],
    dueDate: [''],
  });
  /** Snapshot of the setup form, for templates and computed values. */
  protected readonly setupValue = toSignal(
    this.setup.valueChanges.pipe(map(() => this.setup.getRawValue())),
    { initialValue: this.setup.getRawValue() },
  );

  /** One row per candidate, index-aligned with `views`. */
  protected readonly rows = new FormArray<FormGroup<PromotionRowForm>>([]);
  private readonly rowsTick = signal(0);

  protected readonly preview = signal<PromotionPreview | null>(null);
  protected readonly views = signal<PromotionRowView[]>([]);
  protected readonly names = signal<Record<number, string>>({});
  protected readonly loading = signal(false);
  protected readonly applying = signal(false);
  protected readonly undoing = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<PromotionBatch | null>(null);
  protected readonly historyVersion = signal(0);

  protected readonly years = computed(() => this.lookups.years());
  protected readonly toYears = computed(() =>
    laterYears(this.lookups.years(), this.setupValue().fromYearId),
  );
  protected readonly toYearName = computed(
    () => this.lookups.years().find((y) => y.id === this.setupValue().toYearId)?.name ?? '',
  );
  protected readonly classes = computed(() => this.lookups.classes());
  protected readonly sectionsOfClass = computed(() =>
    this.lookups.sectionsOf(this.setupValue().classId),
  );
  protected readonly canLoad = computed(() => {
    const v = this.setupValue();
    const toOk = laterYears(this.lookups.years(), v.fromYearId).some((y) => y.id === v.toYearId);
    return toOk && v.classId > 0 && !this.loading();
  });

  /** Counts for the summary and the confirm dialog, from the rows that will be sent. */
  protected readonly plan = computed(() => {
    this.rowsTick();
    const counts: Record<PromotionAction, number> = {
      promoted: 0,
      detained: 0,
      left: 0,
      passed_out: 0,
      transferred: 0,
    };
    let actionable = 0;
    let missingTargets = 0;
    this.views().forEach((view, i) => {
      if (view.locked) return;
      const value = this.rows.at(i).getRawValue();
      actionable += 1;
      counts[value.action] += 1;
      if (value.action === 'promoted' && value.toClassId === 0) missingTargets += 1;
    });
    return { actionable, missingTargets, counts };
  });

  /** Students with unpaid dues in the list (the carry-over estimate). */
  protected readonly dues = computed(() => {
    const withDues = (this.preview()?.candidates ?? []).filter((c) => c.dues_paise > 0);
    return {
      count: withDues.length,
      total: withDues.reduce((sum, c) => sum + c.dues_paise, 0),
    };
  });

  protected readonly canReview = computed(() => {
    const p = this.plan();
    const v = this.setupValue();
    const dueOk = !v.carryOver || v.dueDate !== '';
    return p.actionable > 0 && p.missingTargets === 0 && dueOk && !this.applying();
  });

  constructor() {
    this.lookups.load();
    if (this.isOwner) this.lookups.loadBranches();

    // Keep the dependent fields in step with the choice above them.
    this.setup.controls.fromYearId.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => {
      this.fixToYear();
      this.clearPreview();
    });
    this.setup.controls.toYearId.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => {
      this.fixDueDate();
      this.clearPreview();
    });
    this.setup.controls.classId.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => {
      this.setup.controls.sectionId.setValue(0);
      this.clearPreview();
    });
    this.setup.controls.sectionId.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.clearPreview());
    this.rows.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.rowsTick.update((n) => n + 1));

    toObservable(this.lookups.loaded)
      .pipe(filter(Boolean), take(1), takeUntilDestroyed())
      .subscribe(() => this.setup.controls.fromYearId.setValue(this.lookups.currentYearId()));
  }

  protected classLabel(c: SchoolClass): string {
    if (!this.isOwner) return c.name;
    const branch = this.lookups.branches().find((b) => b.id === c.branch_id)?.name;
    return branch ? `${c.name} · ${branch}` : c.name;
  }

  protected dateText(iso: string): string {
    return formatDate(iso, this.i18n.lang());
  }

  protected formatWhen(value: string): string {
    return formatDateTime(value, this.i18n.lang());
  }

  protected nameOf(studentId: number): string {
    return this.names()[studentId] ?? String(studentId);
  }

  protected load(): void {
    if (!this.canLoad()) return;
    const v = this.setupValue();
    this.loading.set(true);
    this.error.set(null);
    this.result.set(null);
    this.api
      .preview({
        from_year_id: v.fromYearId,
        to_year_id: v.toYearId,
        class_id: v.classId,
        section_id: v.sectionId || undefined,
      })
      .subscribe({
        next: (p) => {
          this.showPreview(p);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.loading.set(false);
        },
      });
  }

  protected openReview(): void {
    if (this.canReview()) this.confirm()?.nativeElement.showModal();
  }

  protected closeReview(): void {
    this.confirm()?.nativeElement.close();
  }

  /** Apply the run. The dialog stays open until the server answers. */
  protected apply(): void {
    const v = this.setupValue();
    const items = this.buildItems();
    if (!this.canReview() || items.length === 0) return;
    const body: PromotionApplyInput = {
      from_year_id: v.fromYearId,
      to_year_id: v.toYearId,
      carry_over: v.carryOver,
      items,
    };
    if (v.carryOver) body.due_date = v.dueDate;

    const names: Record<number, string> = {};
    for (const view of this.views()) names[view.candidate.student_id] = view.candidate.name;

    this.applying.set(true);
    this.error.set(null);
    this.api.apply(body).subscribe({
      next: (batch) => {
        this.applying.set(false);
        this.names.set(names);
        this.result.set(batch);
        this.closeReview();
        this.clearPreview();
        this.historyVersion.update((n) => n + 1);
      },
      error: (err: unknown) => {
        this.applying.set(false);
        this.closeReview();
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected undo(batch: PromotionBatch): void {
    this.undoing.set(true);
    this.error.set(null);
    this.api.undo(batch.id).subscribe({
      next: (updated) => {
        this.undoing.set(false);
        this.result.set({ ...batch, ...updated });
        this.historyVersion.update((n) => n + 1);
      },
      error: (err: unknown) => {
        this.undoing.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  /** The history list undid a run: keep the result card in step if it is the same run. */
  protected onHistoryUndone(batch: PromotionBatch): void {
    const current = this.result();
    if (current && current.id === batch.id) this.result.set({ ...current, ...batch });
  }

  private showPreview(p: PromotionPreview): void {
    this.rows.clear();
    const views = p.candidates.map((c: PromotionCandidate) => {
      const view = rowViewOf(c, this.isOwner);
      const group = newRowGroup(c);
      if (view.locked) group.disable();
      this.rows.push(group);
      return view;
    });
    this.views.set(views);
    this.preview.set(p);
  }

  /** Forget the loaded list (the choices changed, or the run was applied). */
  private clearPreview(): void {
    this.rows.clear();
    this.views.set([]);
    this.preview.set(null);
  }

  /** Rows that are not locked, in the shape the apply call takes. */
  private buildItems(): PromotionItemInput[] {
    const items: PromotionItemInput[] = [];
    this.views().forEach((view, i) => {
      if (view.locked) return;
      const value = this.rows.at(i).getRawValue();
      const item: PromotionItemInput = {
        student_id: view.candidate.student_id,
        action: value.action,
      };
      if (value.action === 'promoted' && value.toClassId) item.to_class_id = value.toClassId;
      if ((value.action === 'promoted' || value.action === 'detained') && value.toSectionId) {
        item.to_section_id = value.toSectionId;
      }
      items.push(item);
    });
    return items;
  }

  /** A user picked another from-year: the to-year must still start after it. */
  private fixToYear(): void {
    const fromId = this.setup.controls.fromYearId.value;
    const later = laterYears(this.lookups.years(), fromId);
    if (!later.some((y) => y.id === this.setup.controls.toYearId.value)) {
      this.setup.controls.toYearId.setValue(later[0]?.id ?? 0);
    }
  }

  /** The carry-over due date starts as 30 days after the new year begins. */
  private fixDueDate(): void {
    const toId = this.setup.controls.toYearId.value;
    const to = this.lookups.years().find((y) => y.id === toId);
    if (to) this.setup.controls.dueDate.setValue(addDays(to.start_date, 30));
  }
}
