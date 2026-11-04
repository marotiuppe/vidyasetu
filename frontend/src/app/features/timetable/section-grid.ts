import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { SchoolClass, Section } from '../../core/api/academics.api';
import { AdminApi } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { ExamsApi, Subject } from '../../core/api/exams.api';
import {
  GRID_DAYS,
  SectionTimetable,
  TimetableApi,
  TimetableEntry,
  Period,
  shortTime,
} from '../../core/api/timetable.api';
import { User } from '../../core/auth/auth.models';
import { I18n } from '../../core/i18n/i18n';
import { fieldValue } from '../exams/exam-labels';
import { FeeLookups } from '../fees/fee-lookups';
import { dayKey, sortPeriods } from './timetable-labels';

interface CellTarget {
  weekday: number;
  period: Period;
  entry: TimetableEntry | null;
}

/** Weekly grid of one section: pick a class and section, then fill each period of each day. */
@Component({
  selector: 'sms-section-grid',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './section-grid.html',
  styleUrl: './timetable-grid.css',
})
export class SectionGrid {
  private readonly api = inject(TimetableApi);
  private readonly exams = inject(ExamsApi);
  private readonly admin = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly lookups = inject(FeeLookups);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  readonly yearId = input.required<number>();

  protected readonly days = GRID_DAYS;
  protected readonly dayKey = dayKey;
  protected readonly shortTime = shortTime;

  protected readonly classChoice = signal(0);
  protected readonly sectionChoice = signal(0);
  protected readonly classes = computed<SchoolClass[]>(() => {
    const branch = this.scope.branch();
    return branch ? this.lookups.classesOf(branch) : [];
  });
  protected readonly sections = computed<Section[]>(() =>
    this.lookups.sectionsOf(this.classChoice()),
  );

  protected readonly subjects = signal<Subject[]>([]);
  protected readonly teachers = signal<User[]>([]);
  protected readonly data = signal<SectionTimetable | null>(null);
  protected readonly periods = computed(() => sortPeriods(this.data()?.periods ?? []));
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly cellError = signal<string | null>(null);
  protected readonly target = signal<CellTarget | null>(null);

  protected readonly form = this.fb.group({
    subject_id: [0, [Validators.min(1)]],
    teacher_id: [0],
    room: ['', Validators.maxLength(30)],
  });

  constructor() {
    this.lookups.load();
    effect(() => {
      this.scope.branch();
      untracked(() => {
        this.classChoice.set(0);
        this.sectionChoice.set(0);
        this.data.set(null);
        this.target.set(null);
        this.loadChoices();
      });
    });
    effect(() => {
      const section = this.sectionChoice();
      const year = this.yearId();
      untracked(() => this.load(section, year));
    });
  }

  protected pickClass(event: Event): void {
    this.classChoice.set(Number(fieldValue(event)));
    this.sectionChoice.set(0);
  }

  protected pickSection(event: Event): void {
    this.sectionChoice.set(Number(fieldValue(event)));
  }

  protected entryAt(weekday: number, periodId: number): TimetableEntry | null {
    return (
      this.data()?.entries.find((e) => e.weekday === weekday && e.period_id === periodId) ?? null
    );
  }

  protected isTarget(weekday: number, periodId: number): boolean {
    const t = this.target();
    return t !== null && t.weekday === weekday && t.period.id === periodId;
  }

  protected open(weekday: number, period: Period): void {
    const entry = this.entryAt(weekday, period.id);
    this.cellError.set(null);
    this.target.set({ weekday, period, entry });
    this.form.reset({
      subject_id: entry?.subject_id ?? 0,
      teacher_id: entry?.teacher_id ?? 0,
      room: entry?.room ?? '',
    });
  }

  protected close(): void {
    this.target.set(null);
    this.cellError.set(null);
  }

  protected save(): void {
    const t = this.target();
    if (!t) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.cellError.set(null);
    this.api
      .saveEntry({
        section_id: this.sectionChoice(),
        academic_year_id: this.yearId(),
        weekday: t.weekday,
        period_id: t.period.id,
        subject_id: v.subject_id,
        teacher_id: v.teacher_id || null,
        room: v.room.trim() || null,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.target.set(null);
          this.load(this.sectionChoice(), this.yearId());
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.cellError.set(apiErrorMessage(err));
        },
      });
  }

  protected clear(): void {
    const entry = this.target()?.entry;
    if (!entry) return;
    this.saving.set(true);
    this.cellError.set(null);
    this.api.deleteEntry(entry.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.target.set(null);
        this.load(this.sectionChoice(), this.yearId());
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.cellError.set(apiErrorMessage(err));
      },
    });
  }

  private loadChoices(): void {
    if (this.scope.choiceNeeded()) return;
    this.exams.subjects().subscribe({
      next: (rows) => this.subjects.set(rows.filter((s) => s.active)),
      error: () => this.subjects.set([]),
    });
    const branch = this.scope.branch();
    this.admin.users({ role: 'teacher' }).subscribe({
      next: (rows) =>
        this.teachers.set(rows.filter((u) => u.is_active && (!branch || u.branch_id === branch))),
      error: () => this.teachers.set([]),
    });
  }

  private load(sectionId: number, yearId: number): void {
    this.target.set(null);
    this.error.set(null);
    if (!sectionId || !yearId) {
      this.data.set(null);
      return;
    }
    this.loading.set(true);
    this.api.section(sectionId, yearId).subscribe({
      next: (d) => {
        this.data.set(d);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.data.set(null);
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
