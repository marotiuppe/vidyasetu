import { HttpErrorResponse } from '@angular/common/http';

/** Turn a backend error ({ detail: string | [{ msg }] }) into a message for the user. */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail: unknown = err.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d: unknown) => (d as { msg?: unknown })?.msg)
        .filter((m): m is string => typeof m === 'string');
      if (msgs.length) return msgs.join(' ');
    }
    if (err.status === 0) return 'Cannot reach the server. Check your connection.';
    if (err.status === 403) return 'You are not allowed to do this.';
    if (err.status === 404) return 'Not found.';
  }
  return 'Something went wrong. Please try again.';
}

/** Field-level messages from a 422 response (`detail: [{ loc: ['body', 'field'], msg }]`), keyed by field name. */
export function fieldErrorsFrom(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (!(err instanceof HttpErrorResponse) || err.status !== 422) return out;
  const detail: unknown = err.error?.detail;
  if (!Array.isArray(detail)) return out;
  for (const item of detail as unknown[]) {
    const loc: unknown = (item as { loc?: unknown })?.loc;
    const msg: unknown = (item as { msg?: unknown })?.msg;
    if (Array.isArray(loc) && loc.length > 0 && typeof msg === 'string') {
      const field = String(loc[loc.length - 1]);
      out[field] ??= msg;
    }
  }
  return out;
}
