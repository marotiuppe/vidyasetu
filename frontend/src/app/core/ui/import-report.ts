import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { ImportRowError } from '../api/imports.api';
import { I18n } from '../i18n/i18n';
import { csvDocument } from './csv';
import { saveBlob } from './download';
import { Icon } from './icon';

/**
 * Row problems from a dry run or an import: a table, and a CSV report that opens safely in a
 * spreadsheet. Shows nothing when there are no errors.
 */
@Component({
  selector: 'sms-import-report',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-report.html',
  styleUrl: './import-report.css',
})
export class ImportReport {
  protected readonly i18n = inject(I18n);

  readonly errors = input.required<ImportRowError[]>();
  /** Base name of the downloaded report, for example `students-import`. */
  readonly fileBase = input.required<string>();
  /** Short label of the record on a row (a name or a username), for the table and the report. */
  readonly describe = input<(row: number) => string>(() => '');

  protected readonly count = computed(() => this.errors().length);

  protected label(row: number): string {
    return this.describe()(row);
  }

  protected download(): void {
    const rows: (string | number)[][] = [
      [
        this.i18n.t('import.report.row'),
        this.i18n.t('import.report.record'),
        this.i18n.t('import.report.problem'),
      ],
      ...this.errors().map((e) => [e.row, this.label(e.row), e.message]),
    ];
    saveBlob(csvDocument(rows), `${this.fileBase()}-errors.csv`);
  }
}
