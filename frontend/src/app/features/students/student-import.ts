import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

import { AcademicYear, Branch } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { ImportResult, ImportRow, StudentsApi } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { ImportFile, LoadedCsv } from '../../core/ui/import-file';
import { ImportReport } from '../../core/ui/import-report';
import { MAX_IMPORT_ROWS, templateRows, toImportRows } from './csv';

const PREVIEW_ROWS = 5;

@Component({
  selector: 'sms-student-import',
  imports: [ImportFile, ImportReport],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-import.html',
  styleUrl: './student-import.css',
})
export class StudentImport {
  private readonly api = inject(StudentsApi);
  protected readonly i18n = inject(I18n);

  readonly branches = input.required<Branch[]>();
  readonly years = input.required<AcademicYear[]>();
  readonly canPickBranch = input(false);
  readonly imported = output<number>();
  readonly closed = output<void>();

  protected readonly maxRows = MAX_IMPORT_ROWS;
  protected readonly templateRows = templateRows();
  protected readonly rows = signal<ImportRow[]>([]);
  protected readonly fileName = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  /** Outcome of the last dry run for the rows on screen (cleared when the file or options change). */
  protected readonly checked = signal<ImportResult | null>(null);
  protected readonly result = signal<ImportResult | null>(null);
  protected readonly submitting = signal(false);
  protected readonly checking = signal(false);
  protected readonly branchId = signal(0);
  protected readonly yearId = signal<number | null>(null);

  protected readonly preview = computed(() => this.rows().slice(0, PREVIEW_ROWS));
  protected readonly tooMany = computed(() => this.rows().length > MAX_IMPORT_ROWS);
  protected readonly selectedYear = computed(
    () => this.yearId() ?? this.years().find((y) => y.is_current)?.id ?? 0,
  );
  private readonly ready = computed(
    () =>
      this.rows().length > 0 && !this.tooMany() && (!this.canPickBranch() || this.branchId() > 0),
  );
  protected readonly canSend = computed(() => this.ready() && !this.submitting());
  protected readonly canCheck = computed(() => this.ready() && !this.checking());

  protected onLoaded(csv: LoadedCsv): void {
    this.reset();
    this.fileName.set(csv.fileName);
    const parsed = toImportRows(csv.records);
    if (parsed.error) {
      this.error.set(this.i18n.t(parsed.error.key, parsed.error.params));
      return;
    }
    this.rows.set(parsed.rows);
    if (parsed.rows.length > MAX_IMPORT_ROWS) {
      this.error.set(
        this.i18n.t('students.form.import.tooMany', {
          count: parsed.rows.length,
          max: MAX_IMPORT_ROWS,
        }),
      );
    }
  }

  protected onCleared(): void {
    this.reset();
    this.fileName.set(null);
  }

  private reset(): void {
    this.rows.set([]);
    this.error.set(null);
    this.checked.set(null);
    this.result.set(null);
  }

  /** Summary above the preview, with the right plural form for the row count. */
  protected summary(): string {
    const count = this.rows().length;
    return this.i18n.t(
      count === 1 ? 'students.form.import.summary.one' : 'students.form.import.summary.other',
      { count, file: this.fileName() ?? '', shown: this.preview().length },
    );
  }

  /** The student's name for a row number (1-based), for the error report. */
  protected describe = (row: number): string => {
    const r = this.rows()[row - 1];
    return r ? `${r.first_name} ${r.last_name}`.trim() : '';
  };

  protected onBranch(e: Event): void {
    this.branchId.set(Number((e.target as HTMLSelectElement).value));
    this.checked.set(null);
  }

  protected onYear(e: Event): void {
    this.yearId.set(Number((e.target as HTMLSelectElement).value));
    this.checked.set(null);
  }

  /** Validate the file exactly as an import would, without saving anything. */
  protected check(): void {
    if (!this.canCheck()) return;
    this.checking.set(true);
    this.error.set(null);
    this.result.set(null);
    this.api.importRows(this.body(true)).subscribe({
      next: (res) => {
        this.checking.set(false);
        this.checked.set(res);
      },
      error: (err: unknown) => {
        this.checking.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected submit(): void {
    if (!this.canSend()) return;
    this.submitting.set(true);
    this.error.set(null);
    this.api.importRows(this.body(false)).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.result.set(res);
        this.checked.set(null);
        this.rows.set([]);
        this.imported.emit(res.created);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private body(dryRun: boolean) {
    return {
      branch_id: this.canPickBranch() ? this.branchId() : null,
      academic_year_id: this.selectedYear() || null,
      dry_run: dryRun,
      rows: this.rows(),
    };
  }
}
