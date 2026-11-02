import { ROLE_LABELS } from '../../core/layout/nav';
import { Role } from '../../core/auth/auth.models';
import { NoticeCategory } from '../../core/api/notices.api';

export const CATEGORY_LABELS: Record<NoticeCategory, string> = {
  general: 'General',
  academic: 'Academic',
  event: 'Event',
  holiday: 'Holiday',
  urgent: 'Urgent',
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role as Role] ?? role;
}

/** Backend timestamps are UTC; treat a value without an offset as UTC. */
export function parseTimestamp(value: string): Date {
  return new Date(/(Z|[+-]\d\d:?\d\d)$/.test(value) ? value : `${value}Z`);
}

/** "Today", "Yesterday", "3 days ago", otherwise a short date. */
export function relativeDate(value: string, now = new Date()): string {
  const d = parseTimestamp(value);
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86_400_000);
  if (diff <= 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function todayIso(): string {
  const n = new Date();
  const p = (v: number) => String(v).padStart(2, '0');
  return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}`;
}
