const ZONE = 'Asia/Kolkata';

/** Browser locale for the active language: Marathi uses Marathi month and day names. */
export function localeOf(lang: string): string {
  return lang === 'mr' ? 'mr-IN' : 'en-IN';
}

/** "02 Nov 2026, 8:51 pm" in Indian time. Returns an empty string for a missing or bad value. */
export function formatDateTime(value: string | null | undefined, lang = 'en'): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(lang === 'mr' ? 'mr-IN' : 'en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: ZONE,
  }).format(date);
}

/** "02 Nov 2026" from an ISO date or timestamp. */
export function formatDate(value: string | null | undefined, lang = 'en'): string {
  if (!value) return '';
  // A plain date (YYYY-MM-DD) is shown as is, without a time-zone shift.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00+05:30`)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(lang === 'mr' ? 'mr-IN' : 'en-IN', {
    dateStyle: 'medium',
    timeZone: ZONE,
  }).format(date);
}

/** Today's date (YYYY-MM-DD) in Indian time. */
export function todayIst(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONE }).format(new Date());
}
