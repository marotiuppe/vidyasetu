import { StaffMark } from '../../core/api/attendance.api';
import { localeOf } from '../../core/ui/dates';

export const STUDENT_MARKS = [
  { value: 'present' },
  { value: 'absent' },
  { value: 'leave' },
] as const;

export const STAFF_MARKS = [...STUDENT_MARKS, { value: 'half_day' }] as const;

export const MARK_CLASS: Record<StaffMark, string> = {
  present: 'st-present',
  absent: 'st-absent',
  leave: 'st-leave',
  half_day: 'st-half',
};

/** Translation key for each mark; resolve with i18n.t at render time. */
export const MARK_KEY: Record<StaffMark, string> = {
  present: 'ops.mark.present',
  absent: 'ops.mark.absent',
  leave: 'ops.mark.leave',
  half_day: 'ops.mark.halfDay',
};

const pad = (n: number) => String(n).padStart(2, '0');

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function monthStartIso(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`;
}

/** Parse YYYY-MM-DD as a local date (no timezone shift). */
export function parseIso(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(value: string, lang = 'en'): string {
  return parseIso(value).toLocaleDateString(localeOf(lang), {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function percent(part: number, whole: number): number | null {
  return whole > 0 ? Math.round((part / whole) * 100) : null;
}
