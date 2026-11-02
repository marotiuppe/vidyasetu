import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeeHead, FeesApi } from '../../core/api/fees.api';
import { FeeHeads } from './fee-heads';
import { FeeStructure } from './fee-structure';

/** Setup tab: fee heads and the per-class fee structure. */
@Component({
  selector: 'sms-fee-setup',
  imports: [FeeHeads, FeeStructure],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="stack">
      @if (error(); as message) {
        <p class="form-error" role="alert">{{ message }}</p>
      }
      <sms-fee-heads [heads]="heads()" [loading]="loading()" (changed)="load()" />
      <sms-fee-structure [heads]="heads()" />
    </div>
  `,
})
export class FeeSetup {
  private readonly api = inject(FeesApi);

  protected readonly heads = signal<FeeHead[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.load();
  }

  protected load(): void {
    this.api.heads().subscribe({
      next: (h) => {
        this.heads.set(h);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
