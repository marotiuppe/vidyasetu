/** Single place for the currency; can become a school setting later. */
export const CURRENCY = { locale: 'en-IN', code: 'INR' } as const;

const formatter = new Intl.NumberFormat(CURRENCY.locale, {
  style: 'currency',
  currency: CURRENCY.code,
});

/** "₹1,23,456.00" from integer paise. Only integer maths; the paise part is written from the remainder. */
export function formatPaise(paise: number): string {
  const negative = paise < 0;
  const abs = Math.abs(Math.trunc(paise));
  const rest = abs % 100;
  const text = formatter
    .formatToParts((abs - rest) / 100)
    .map((p) => (p.type === 'fraction' ? String(rest).padStart(2, '0') : p.value))
    .join('');
  return negative ? `-${text}` : text;
}

/**
 * Parse text such as "1500", "1,500.50" or "₹ 20.5" into integer paise.
 * Works on the digit strings, so there is no floating-point error.
 * Returns null for empty, negative, non-numeric or more than 2 decimals.
 */
export function parseRupeesToPaise(text: string): number | null {
  const cleaned = text.replace(/[\s,₹]/g, '');
  const match = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return null;
  const paise = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0') || '0');
  return Number.isSafeInteger(paise) ? paise : null;
}

/** Plain number text for an input box: 150050 -> "1500.50", 150000 -> "1500". */
export function paiseToInput(paise: number): string {
  const abs = Math.abs(Math.trunc(paise));
  const rest = abs % 100;
  const whole = (abs - rest) / 100;
  return rest === 0 ? String(whole) : `${whole}.${String(rest).padStart(2, '0')}`;
}

/** Whole-number percentage (0-100) of part/total for bar widths, using integer maths. */
export function percentOf(part: number, total: number): number {
  if (total <= 0 || part <= 0) return 0;
  return Math.min(100, Number((BigInt(part) * 100n) / BigInt(total)));
}
