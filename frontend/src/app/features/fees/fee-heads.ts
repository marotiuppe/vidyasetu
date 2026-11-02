import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeeHead, FeesApi } from '../../core/api/fees.api';

/** Fee heads (tuition, transport, ...): add, rename, activate or deactivate. */
@Component({
  selector: 'sms-fee-heads',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fee-heads.html',
})
export class FeeHeads {
  private readonly api = inject(FeesApi);
  private readonly fb = inject(NonNullableFormBuilder);

  readonly heads = input.required<FeeHead[]>();
  readonly loading = input(false);
  readonly changed = output<void>();

  protected readonly addControl = this.fb.control('');
  protected readonly renameControl = this.fb.control('');
  protected readonly renamingId = signal(0);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected add(): void {
    const name = this.addControl.value.trim();
    if (!name) return this.error.set('Enter a name for the fee head.');
    this.run(this.api.createHead(name), `Added ${name}.`, () => this.addControl.reset(''));
  }

  protected startRename(h: FeeHead): void {
    this.renamingId.set(h.id);
    this.renameControl.setValue(h.name);
  }

  protected rename(h: FeeHead): void {
    const name = this.renameControl.value.trim();
    if (!name) return this.error.set('Enter a name for the fee head.');
    this.run(this.api.updateHead(h.id, { name }), 'Fee head renamed.', () => this.renamingId.set(0));
  }

  protected toggle(h: FeeHead): void {
    this.run(
      this.api.updateHead(h.id, { is_active: !h.is_active }),
      `${h.name} ${h.is_active ? 'deactivated' : 'activated'}.`,
    );
  }

  private run(call: ReturnType<FeesApi['createHead']>, message: string, after?: () => void): void {
    this.error.set(null);
    this.notice.set(null);
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        this.notice.set(message);
        after?.();
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
