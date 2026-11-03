import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  FeeStructureImportResult,
  FeeStructureImportRow,
  ImportsApi,
} from '../../core/api/imports.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { headerName } from '../../core/ui/csv';
import { ImportFile, LoadedCsv } from '../../core/ui/import-file';
import { ImportReport } from '../../core/ui/import-report';
import { FeeLookups } from './fee-lookups';

export const FEE_IMPORT_MAX_ROWS = 500;
const PREVIEW_ROWS = 5;
const COLUMNS = ['class', 'fee_head', 'amount_rupees'];

/** Bulk fee structure from a CSV file. A file is saved only when every row is valid. */
@Component({
  selector: 'sms-fee-import',
  imports: [RouterLink, ImportFile, ImportReport],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-import.html',
  styleUrl: './fee-import.css',
})
export class FeeImport {
  private readonly api = inject(ImportsApi);
  private readonly auth = inject(AuthService);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly columns = COLUMNS;
  protected readonly templateRows = [COLUMNS];
  protected readonly maxRows = FEE_IMPORT_MAX_ROWS;
  /** A school owner has no branch of their own, so the branch is chosen here. */
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly branchId = signal(0);
  protected readonly pickedYear = signal<number | null>(null);
  protected readonly yearId = computed(() => this.pickedYear() ?? this.lookups.currentYearId());

  protected readonly rows = signal<FeeStructureImportRow[]>([]);
  protected readonly fileName = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly checked = signal<FeeStructureImportResult | null>(null);
  protected readonly result = signal<FeeStructureImportResult | null>(null);
  protected readonly checking = signal(false);
  protected readonly submitting = signal(false);

  protected readonly preview = computed(() => this.rows().slice(0, PREVIEW_ROWS));
  protected readonly tooMany = computed(() => this.rows().length > FEE_IMPORT_MAX_ROWS);
  private readonly ready = computed(
    () =>
      this.rows().length > 0 &&
      !this.tooMany() &&
      this.yearId() > 0 &&
      (!this.canPickBranch || this.branchId() > 0),
  );
  protected readonly canCheck = computed(() => this.ready() && !this.checking());
  /** All-or-nothing: a check with any bad row blocks the import until the file is fixed. */
  protected readonly blocked = computed(() => (this.checked()?.failed ?? 0) > 0);
  protected readonly canImport = computed(
    () => this.ready() && !this.submitting() && !this.blocked(),
  );

  constructor() {
    this.lookups.load();
    if (this.canPickBranch) this.lookups.loadBranches();
  }

  protected onLoaded(csv: LoadedCsv): void {
    this.reset();
    this.fileName.set(csv.fileName);
    const parsed = this.parse(csv);
    if (parsed.error) {
      this.error.set(parsed.error);
      return;
    }
    this.rows.set(parsed.rows);
    if (parsed.rows.length > FEE_IMPORT_MAX_ROWS) {
      this.error.set(
        this.i18n.t('fees.import.tooMany', {
          count: parsed.rows.length,
          max: FEE_IMPORT_MAX_ROWS,
        }),
      );
    }
  }

  protected onCleared(): void {
    this.reset();
    this.fileName.set(null);
  }

  protected onBranch(e: Event): void {
    this.branchId.set(Number((e.target as HTMLSelectElement).value));
    this.checked.set(null);
  }

  protected onYear(e: Event): void {
    this.pickedYear.set(Number((e.target as HTMLSelectElement).value));
    this.checked.set(null);
  }

  /** "Class 3 · Tuition" for a row number (1-based), for the error report. */
  protected describe = (row: number): string => {
    const r = this.rows()[row - 1];
    return r ? `${r.class} · ${r.fee_head}` : '';
  };

  protected check(): void {
    if (!this.canCheck()) return;
    this.checking.set(true);
    this.error.set(null);
    this.result.set(null);
    this.api.importFeeStructure(this.body(true)).subscribe({
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
    if (!this.canImport()) return;
    this.submitting.set(true);
    this.error.set(null);
    this.api.importFeeStructure(this.body(false)).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.checked.set(null);
        this.rows.set([]);
        this.result.set(res);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected wouldChange(res: FeeStructureImportResult): number {
    return (res.would_create ?? 0) + (res.would_update ?? 0);
  }

  protected changed(res: FeeStructureImportResult): number {
    return (res.created ?? 0) + (res.updated ?? 0);
  }

  private reset(): void {
    this.rows.set([]);
    this.error.set(null);
    this.checked.set(null);
    this.result.set(null);
  }

  private parse(csv: LoadedCsv): { rows: FeeStructureImportRow[]; error: string | null } {
    const [header, ...body] = csv.records;
    if (!header) return { rows: [], error: this.i18n.t('import.file.empty') };
    const names = header.map(headerName);
    const missing = COLUMNS.filter((c) => !names.includes(c));
    if (missing.length) {
      return {
        rows: [],
        error: this.i18n.t('import.file.missing', { columns: missing.join(', ') }),
      };
    }
    const rows: FeeStructureImportRow[] = [];
    for (const rec of body) {
      if (rec.every((c) => c.trim() === '')) continue;
      const cell = (name: string): string => {
        const idx = names.indexOf(name);
        return idx >= 0 ? (rec[idx] ?? '').trim() : '';
      };
      rows.push({
        class: cell('class'),
        fee_head: cell('fee_head'),
        amount_rupees: cell('amount_rupees'),
      });
    }
    if (!rows.length) return { rows: [], error: this.i18n.t('import.file.noRows') };
    return { rows, error: null };
  }

  private body(dryRun: boolean) {
    return {
      academic_year_id: this.yearId(),
      branch_id: this.canPickBranch ? this.branchId() : null,
      dry_run: dryRun,
      rows: this.rows(),
    };
  }
}
