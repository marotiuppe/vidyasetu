import { ImportRow } from '../../core/api/students.api';

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

const REQUIRED = ['first_name', 'last_name', 'gender', 'date_of_birth', 'guardian_name', 'guardian_phone'];

const EXAMPLE = [
  'Asha',
  'Patil',
  'female',
  '2015-06-14',
  '2026-04-01',
  '',
  '12 Main Road',
  'Ravi Patil',
  '9876543210',
  'father',
  'Class 3',
  'A',
  '',
];

/** Minimal RFC 4180 parser: quoted fields, escaped quotes, commas and newlines inside quotes, CRLF, BOM. */
export function parseCsv(input: string): string[][] {
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          quoted = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      row.push(field);
      field = '';
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else {
      field += ch;
    }
  }
  if (field !== '' || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

export interface ParsedImport {
  rows: ImportRow[];
  error: string | null;
}

/** Turn parsed CSV records into import rows using the header row (case-insensitive names). */
export function toImportRows(records: string[][]): ParsedImport {
  const [header, ...body] = records;
  if (!header) return { rows: [], error: 'The file is empty.' };

  const names = header.map((h) => h.trim().toLowerCase().replace(/[\s-]+/g, '_'));
  const missing = REQUIRED.filter((r) => !names.includes(r));
  if (missing.length) {
    return { rows: [], error: `Missing required column(s): ${missing.join(', ')}.` };
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
  if (!rows.length) return { rows: [], error: 'The file has no data rows.' };
  return { rows, error: null };
}

function cell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** CSV text for the template: header plus one example row. */
export function templateCsv(): string {
  return [IMPORT_FIELDS.join(','), EXAMPLE.map(cell).join(',')].join('\r\n') + '\r\n';
}
