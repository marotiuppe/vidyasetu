import { HttpErrorResponse } from '@angular/common/http';
import { AbstractControl } from '@angular/forms';

type Translator = (key: string) => string;

let translate: Translator | null = null;

/** Registered by the I18n service so error codes are shown in the active language. */
export function setErrorTranslator(fn: Translator): void {
  translate = fn;
}

/** Backend error codes that have a clear, translated message (keys live in core/i18n). */
const CODE_KEYS: Record<string, string> = {
  portal_hidden: 'error.portal_hidden',
  attendance_locked: 'error.attendance_locked',
  student_logins_disabled: 'error.student_logins_disabled',
};

/** Turn a backend error ({ detail: string | [{ msg }], code? }) into a message for the user. */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const code: unknown = err.error?.code;
    const key = typeof code === 'string' ? CODE_KEYS[code] : undefined;
    if (key !== undefined && translate !== null) return translate(key);
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

/**
 * Put 422 messages on their form controls (as a `server` error) and return the message to show
 * elsewhere, or null when every problem sat on a field.
 */
export function placeServerErrors(
  form: { get(name: string): AbstractControl | null },
  err: unknown,
): string | null {
  let placed = false;
  for (const [name, message] of Object.entries(fieldErrorsFrom(err))) {
    const control = form.get(name);
    if (control) {
      control.setErrors({ server: message });
      control.markAsTouched();
      placed = true;
    }
  }
  return placed ? null : apiErrorMessage(err);
}
