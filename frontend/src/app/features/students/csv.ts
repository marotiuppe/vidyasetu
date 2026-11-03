import { ImportRow } from '../../core/api/students.api';
import { headerName } from '../../core/ui/csv';

export const MAX_IMPORT_ROWS = 500;

export const IMPORT_FIELDS = [
  'first_name',
  'last_name',
  'gender',
  'date_of_birth',
  'admission_date',
  'admission_no',
  'address',
  'guardian_name',
  'guardian_phone',
  'guardian_relation',
  'class',
  'section',
  'roll_no',
] as const;

const REQUIRED = [
  'first_name',
  'last_name',
  'gender',
  'date_of_birth',
  'guardian_name',
  'guardian_phone',
];

/** A problem to show, as an i18n key with its parameters (translated by the caller). */
export interface ImportIssue {
  key: string;
  params?: Record<string, string | number>;
}

export interface ParsedImport {
  rows: ImportRow[];
  error: ImportIssue | null;
}

/** Turn parsed CSV records into import rows using the header row (case-insensitive names). */
export function toImportRows(records: string[][]): ParsedImport {
  const [header, ...body] = records;
  if (!header) return { rows: [], error: { key: 'students.form.import.empty' } };

  const names = header.map(headerName);
  const missing = REQUIRED.filter((r) => !names.includes(r));
  if (missing.length) {
    return {
      rows: [],
      error: { key: 'students.form.import.missing', params: { columns: missing.join(', ') } },
    };
  }

  const rows: ImportRow[] = [];
  for (const rec of body) {
    if (rec.every((c) => c.trim() === '')) continue;
    const obj: Record<string, string> = {};
    for (const field of IMPORT_FIELDS) {
      const idx = names.indexOf(field);
      const value = idx >= 0 ? (rec[idx] ?? '').trim() : '';
      if (value !== '' || REQUIRED.includes(field)) obj[field] = value;
    }
    rows.push(obj as unknown as ImportRow);
  }
  if (!rows.length) return { rows: [], error: { key: 'students.form.import.noRows' } };
  return { rows, error: null };
}

/** Header-only template: the column names, in the order the importer reads them. */
export function templateRows(): string[][] {
  return [[...IMPORT_FIELDS]];
}
