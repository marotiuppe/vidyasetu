import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { AttendanceApi, StudentAttendanceReport, StudentMark } from '../../core/api/attendance.api';
import { Icon } from '../../core/ui/icon';
import { MARK_CLASS, MARK_LABEL, isoDate } from './attendance-labels';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const LETTER: Record<StudentMark, string> = { present: 'P', absent: 'A', leave: 'L' };

interface Cell {
  date: string;
  day: number;
  status: StudentMark | null;
  sunday: boolean;
  future: boolean;
  label: string;
}

/** Month calendar and summary of one student's attendance. Reusable (page and student profile). */
@Component({
  selector: 'sms-student-attendance',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-attendance.html',
  styleUrl: './student-attendance.css',
})
export class StudentAttendance {
  private readonly api = inject(AttendanceApi);

  readonly studentId = input.required<number>();

  protected readonly weekdays = WEEKDAYS;
  protected readonly letter = LETTER;
  protected readonly markClass = MARK_CLASS;
  protected readonly markLabel = MARK_LABEL;
  private readonly now = new Date();
  private readonly today = isoDate(this.now);

  /** First day of the month on show. */
  protected readonly month = signal(new Date(this.now.getFullYear(), this.now.getMonth(), 1));
  protected readonly report = signal<StudentAttendanceReport | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly monthLabel = computed(() =>
    this.month().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }),
  );
  protected readonly isCurrentMonth = computed(() => {
    const m = this.month();
    return m.getFullYear() === this.now.getFullYear() && m.getMonth() === this.now.getMonth();
  });

  protected readonly blanks = computed(() =>
    Array.from({ length: (this.month().getDay() + 6) % 7 }, (_, i) => i),
  );

  protected readonly cells = computed<Cell[]>(() => {
    const m = this.month();
    const records = new Map((this.report()?.records ?? []).map((r) => [r.date, r.status]));
    const days = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
    const out: Cell[] = [];
    for (let day = 1; day <= days; day++) {
      const d = new Date(m.getFullYear(), m.getMonth(), day);
      const date = isoDate(d);
      const status = records.get(date) ?? null;
      const sunday = d.getDay() === 0;
      const text = d.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
      const state = status ? MARK_LABEL[status] : sunday ? 'Sunday, no school' : 'Not marked';
      out.push({ date, day, status, sunday, future: date > this.today, label: `${text}: ${state}` });
    }
    return out;
  });

  constructor() {
    toObservable(computed(() => ({ id: this.studentId(), month: this.month() })))
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(({ id, month }) => {
          const first = isoDate(month);
          const last = isoDate(new Date(month.getFullYear(), month.getMonth() + 1, 0));
          return this.api.studentReport(id, first, last > this.today ? this.today : last).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((r) => {
        this.report.set(r);
        this.loading.set(false);
      });
  }

  protected shift(delta: number): void {
    const m = this.month();
    this.month.set(new Date(m.getFullYear(), m.getMonth() + delta, 1));
  }
}
