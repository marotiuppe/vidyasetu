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
import { MAX_IMPORT_ROWS, parseCsv, templateCsv, toImportRows } from './csv';

const MAX_FILE_BYTES = 2 * 1024 * 1024;
const PREVIEW_ROWS = 5;

@Component({
  selector: 'sms-student-import',
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
  protected readonly rows = signal<ImportRow[]>([]);
  protected readonly fileName = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<ImportResult | null>(null);
  protected readonly submitting = signal(false);
  protected readonly branchId = signal(0);
  protected readonly yearId = signal<number | null>(null);

  protected readonly preview = computed(() => this.rows().slice(0, PREVIEW_ROWS));
  protected readonly tooMany = computed(() => this.rows().length > MAX_IMPORT_ROWS);
  protected readonly selectedYear = computed(
    () => this.yearId() ?? this.years().find((y) => y.is_current)?.id ?? 0,
  );
  protected readonly canSend = computed(
    () =>
      this.rows().length > 0 &&
      !this.tooMany() &&
      !this.submitting() &&
      (!this.canPickBranch() || this.branchId() > 0),
  );

  protected async onFile(e: Event): Promise<void> {
    const file = (e.target as HTMLInputElement).files?.[0];
    this.rows.set([]);
    this.result.set(null);
    this.error.set(null);
    this.fileName.set(file?.name ?? null);
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      this.error.set(this.i18n.t('students.form.import.tooLarge'));
      return;
    }
    try {
      const parsed = toImportRows(parseCsv(await file.text()));
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
    } catch {
      this.error.set(this.i18n.t('students.form.import.unreadable'));
    }
  }

  /** Summary above the preview, with the right plural form for the row count. */
  protected summary(): string {
    const count = this.rows().length;
    return this.i18n.t(
      count === 1 ? 'students.form.import.summary.one' : 'students.form.import.summary.other',
      { count, file: this.fileName() ?? '', shown: this.preview().length },
    );
  }

  protected onBranch(e: Event): void {
    this.branchId.set(Number((e.target as HTMLSelectElement).value));
  }

  protected onYear(e: Event): void {
    this.yearId.set(Number((e.target as HTMLSelectElement).value));
  }

  protected downloadTemplate(): void {
    this.api.saveBlob(new Blob([templateCsv()], { type: 'text/csv' }), 'students-template.csv');
  }

  protected submit(): void {
    if (!this.canSend()) return;
    this.submitting.set(true);
    this.error.set(null);
    this.api
      .importRows({
        branch_id: this.canPickBranch() ? this.branchId() : null,
        academic_year_id: this.selectedYear() || null,
        rows: this.rows(),
      })
      .subscribe({
        next: (res) => {
          this.submitting.set(false);
          this.result.set(res);
          this.rows.set([]);
          this.imported.emit(res.created);
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.error.set(apiErrorMessage(err));
        },
      });
  }
}
