import {
  AspectGrade,
  Decimal,
  ExamSection,
  PassResult,
  SubjectKind,
  num,
} from '../../core/api/exams.api';

/** Translation lookup, as `I18n.t` (pass `i18n.t` so labels follow the language). */
export type Translate = (key: string, params?: Record<string, string | number>) => string;

const SECTION_KEYS: Record<ExamSection, string> = {
  co_curricular: 'exams.section.co_curricular',
  behavioural: 'exams.section.behavioural',
  self_awareness: 'exams.section.self_awareness',
  health: 'exams.section.health',
};

const KIND_KEYS: Record<SubjectKind, string> = {
  scholastic: 'exams.kind.scholastic',
  co_scholastic: 'exams.kind.co_scholastic',
};

const numberFormat = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

/** Translated name of an aspect section. */
export function sectionText(section: ExamSection, t: Translate): string {
  return t(SECTION_KEYS[section]);
}

/** Translated subject kind. */
export function kindText(kind: SubjectKind, t: Translate): string {
  return t(KIND_KEYS[kind]);
}

/** Pass / fail label, or a dash when the result is not known yet. */
export function resultText(result: PassResult | null, t: Translate): string {
  if (result === 'pass') return t('exams.result.pass');
  if (result === 'fail') return t('exams.result.fail');
  return t('exams.none');
}

/** Badge class for a pass / fail result. */
export function resultClass(result: PassResult | null): string {
  if (result === 'pass') return 'badge-success';
  if (result === 'fail') return 'badge-danger';
  return 'badge-muted';
}

/** A server decimal as text with at most two decimals, or a dash. */
export function numberText(value: Decimal | null | undefined): string {
  const n = num(value);
  return n === null ? '—' : numberFormat.format(n);
}

/** A server percent as text such as "72.5%", or a dash. */
export function percentText(value: Decimal | null | undefined): string {
  const n = num(value);
  return n === null ? '—' : `${numberFormat.format(n)}%`;
}

/** Whole-number text for counts and ranks. */
export function countText(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : numberFormat.format(value);
}

/** Letters the aspect grade select offers. */
export const GRADE_OPTIONS: AspectGrade[] = ['A', 'B', 'C', 'D', 'E'];

/** Read the value of an input or select in a form event. */
export function fieldValue(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value;
}

/** Read the checked state of a checkbox in an event. */
export function fieldChecked(event: Event): boolean {
  return (event.target as HTMLInputElement).checked;
}

/** Whole-number text for an input, or null when the text is not a plain number. */
export function parseWhole(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

/** Decimal text (up to two places) as a number, or null for empty or invalid text. */
export function parseMarks(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d{1,4}(\.\d{1,2})?$/.test(trimmed)) return null;
  return Number(trimmed);
}

/** Message for the first problem on a form control (server message first), or null. */
export function fieldError(
  control: { errors: Record<string, unknown> | null; touched: boolean; dirty: boolean },
  t: Translate,
): string | null {
  const errors = control.errors;
  if (!errors || (!control.touched && !control.dirty)) return null;
  if (typeof errors['server'] === 'string') return errors['server'];
  if (errors['required']) return t('exams.form.required');
  if (errors['maxlength']) return t('exams.form.tooLong');
  if (errors['min'] || errors['max']) return t('exams.form.range');
  return t('exams.form.invalid');
}
