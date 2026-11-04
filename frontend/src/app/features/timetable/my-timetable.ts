import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';

import { apiErrorMessage } from '../../core/api/api-error';
import { Student, StudentsApi } from '../../core/api/students.api';
import {
  GRID_DAYS,
  Period,
  TimetableApi,
  WeekEntry,
  WeekTimetable,
  shortTime,
} from '../../core/api/timetable.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { fieldValue } from '../exams/exam-labels';
import { dayKey, sortPeriods, todayWeekday } from './timetable-labels';

/** Read-only week: the teacher's own lessons, or a child's timetable for parents and students. */
@Component({
  selector: 'sms-my-timetable',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './my-timetable.html',
  styleUrl: './timetable-grid.css',
})
export class MyTimetable {
  private readonly api = inject(TimetableApi);
  private readonly auth = inject(AuthService);
  private readonly students = inject(StudentsApi);
  protected readonly i18n = inject(I18n);

  protected readonly selfService = this.auth.hasRole('parent', 'student');
  protected readonly days = GRID_DAYS;
  protected readonly today = todayWeekday();
  protected readonly dayKey = dayKey;
  protected readonly shortTime = shortTime;

  protected readonly children = signal<Student[]>([]);
  protected readonly childrenLoaded = signal(!this.selfService);
  private readonly childChoice = signal<number | null>(null);
  protected readonly studentId = computed(() => this.childChoice() ?? this.children()[0]?.id ?? 0);

  protected readonly week = signal<WeekTimetable | null>(null);
  protected readonly periods = computed(() => sortPeriods(this.week()?.periods ?? []));
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    if (this.selfService) {
      this.students.list({}, 1, 100).subscribe({
        next: (page) => {
          this.children.set(page.items);
          this.childrenLoaded.set(true);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.childrenLoaded.set(true);
        },
      });
    }
    effect(() => {
      const student = this.studentId();
      const ready = this.childrenLoaded();
      untracked(() => this.load(student, ready));
    });
  }

  protected pickChild(event: Event): void {
    this.childChoice.set(Number(fieldValue(event)));
  }

  protected entryAt(weekday: number, period: Period): WeekEntry[] {
    return (this.week()?.entries ?? []).filter(
      (e) => e.weekday === weekday && e.period_id === period.id,
    );
  }

  /** Class and section of a lesson, shown on a teacher's week. */
  protected where(e: WeekEntry): string {
    const place = [e.class_name, e.section_name].filter(Boolean).join(' ');
    return [place, e.room].filter(Boolean).join(' · ');
  }

  private load(studentId: number, ready: boolean): void {
    this.week.set(null);
    if (!ready || (this.selfService && !studentId)) return;
    this.loading.set(true);
    this.error.set(null);
    const request = this.selfService ? this.api.student(studentId) : this.api.mine();
    request.subscribe({
      next: (w) => {
        this.week.set(w);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
