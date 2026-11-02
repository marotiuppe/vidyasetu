import { StudentStatus } from '../../core/api/students.api';

const STATUS_LABELS: Record<StudentStatus, string> = {
  active: 'Active',
  left: 'Left',
  transferred: 'Transferred',
  passed_out: 'Passed out',
};

export function statusLabel(status: StudentStatus): string {
  return STATUS_LABELS[status];
}

/** Translation key for a student status (English text: `students.list.status.<status>`). */
export function statusKey(status: StudentStatus): string {
  return `students.list.status.${status}`;
}

/** Capitalise a snake_case enum value for display (male -> Male). */
export function titleCase(value: string): string {
  const spaced = value.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join('') || '?'
  );
}

/** Phone numbers: 7-20 characters of digits, plus, minus and spaces. */
export const PHONE_PATTERN = /^[0-9+\- ]{7,20}$/;

export function todayIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
