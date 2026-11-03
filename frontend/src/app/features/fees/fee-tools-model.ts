/**
 * Pure helpers for the fee tools: percent parsing into basis points and reminder text filling.
 * Integer maths only, so there is no floating-point drift in stored values.
 */

/** "25" -> 2500, "12.5" -> 1250, "0.01" -> 1. Null for empty, above 100 or more than 2 decimals. */
export function parsePercentToBps(text: string): number | null {
  const match = /^(\d{1,3})(?:\.(\d{1,2}))?$/.exec(text.trim());
  if (!match) return null;
  const bps = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0') || '0');
  return bps > 0 && bps <= 10000 ? bps : null;
}

export interface ReminderVars {
  guardian: string;
  student: string;
  amount: string;
  date: string;
}

/** Fill {guardian}, {student}, {amount} and {date}. Unknown placeholders are left as written. */
export function fillReminderTemplate(template: string, vars: ReminderVars): string {
  return template.replace(/\{(guardian|student|amount|date)\}/g, (_m, key: keyof ReminderVars) => {
    return vars[key];
  });
}
