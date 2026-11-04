import { Period } from '../../core/api/timetable.api';

/** Translation key of a weekday number (1 = Monday). */
export function dayKey(day: number): string {
  return `timetable.day.${day}`;
}

/** Today as a weekday number (1 = Monday ... 7 = Sunday). */
export function todayWeekday(): number {
  const d = new Date().getDay();
  return d === 0 ? 7 : d;
}

/** Periods in teaching order. */
export function sortPeriods(periods: Period[]): Period[] {
  return [...periods].sort(
    (a, b) => a.sequence - b.sequence || a.start_time.localeCompare(b.start_time),
  );
}
