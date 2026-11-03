import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';

import { I18n } from '../i18n/i18n';
import { csvDocument, parseCsv } from './csv';
import { saveBlob } from './download';
import { Icon } from './icon';

const DEFAULT_MAX_BYTES = 2 * 1024 * 1024;

/** A CSV file read in the browser: its name and every record (header row included). */
export interface LoadedCsv {
  fileName: string;
  records: string[][];
}

/**
 * File picker for the CSV imports: checks the size, reads the text and hands back the records.
 * Also downloads a header-only template so the columns are known before the file is prepared.
 */
@Component({
  selector: 'sms-import-file',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-file.html',
  styleUrl: './import-file.css',
})
export class ImportFile {
  protected readonly i18n = inject(I18n);

  readonly templateRows = input.required<string[][]>();
  /** File name of the downloaded template, for example `students-template.csv`. */
  readonly templateName = input.required<string>();
  readonly maxBytes = input(DEFAULT_MAX_BYTES);
  readonly loaded = output<LoadedCsv>();
  readonly cleared = output<void>();

  protected readonly error = signal<string | null>(null);
  protected readonly fileName = signal<string | null>(null);

  protected async onFile(event: Event): Promise<void> {
    const field = event.target as HTMLInputElement;
    const file = field.files?.[0];
    this.error.set(null);
    this.fileName.set(file?.name ?? null);
    if (!file) {
      this.cleared.emit();
      return;
    }
    if (file.size > this.maxBytes()) {
      this.error.set(this.i18n.t('import.file.tooLarge'));
      this.cleared.emit();
      return;
    }
    try {
      const records = parseCsv(await file.text());
      this.loaded.emit({ fileName: file.name, records });
    } catch {
      this.error.set(this.i18n.t('import.file.unreadable'));
      this.cleared.emit();
    }
  }

  protected downloadTemplate(): void {
    saveBlob(csvDocument(this.templateRows()), this.templateName());
  }
}
