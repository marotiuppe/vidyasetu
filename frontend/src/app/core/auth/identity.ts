import { AbstractControl, ValidationErrors } from '@angular/forms';

/** 3 to 50 characters: letters, digits, dot, underscore or hyphen. */
export const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,50}$/;
export const USERNAME_HINT =
  '3 to 50 letters, digits, dots, underscores or hyphens, with at least one letter. Saved in lower case.';
/** A 10-digit mobile number, or a + country code followed by the number. */
export const MOBILE_PATTERN = /^(\d{10}|\+[1-9]\d{7,14})$/;
export const MOBILE_HINT = '10 digits, or + and the country code, for example +919876543210.';

/** Empty values pass; the required rule handles those. */
export function usernameFormat(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value ?? '').trim();
  if (!value) return null;
  return USERNAME_PATTERN.test(value) && /[A-Za-z]/.test(value) ? null : { username: true };
}

export function mobileFormat(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value ?? '').trim();
  if (!value) return null;
  return MOBILE_PATTERN.test(value) ? null : { mobile: true };
}

/**
 * Suggest a username from a name or an email address, e.g. "Ravi Kumar" -> "ravi.kumar".
 * Returns '' when nothing usable is left.
 */
export function suggestUsername(source: string): string {
  const cleaned = source
    .toLowerCase()
    .trim()
    .replace(/@.*$/, '')
    .replace(/\s+/g, '.')
    .replace(/[^a-z0-9._-]/g, '')
    .replace(/[._-]{2,}/g, '.')
    .replace(/^[._-]+|[._-]+$/g, '')
    .slice(0, 50);
  return USERNAME_PATTERN.test(cleaned) && /[a-z]/.test(cleaned) ? cleaned : '';
}
