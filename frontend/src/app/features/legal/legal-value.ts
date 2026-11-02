import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/**
 * One operator detail on a legal page. `undefined` means not loaded yet; `null` or empty means the
 * operator has not entered it, which is shown as muted text instead of a blank.
 */
@Component({
  selector: 'sms-legal-value',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (value() === undefined) {
      <span class="muted">Loading…</span>
    } @else if (!value()) {
      <span class="missing">Not yet provided by the operator</span>
    } @else if (kind() === 'email') {
      <a [href]="'mailto:' + value()">{{ value() }}</a>
    } @else if (kind() === 'phone') {
      <a [href]="'tel:' + dialable()">{{ value() }}</a>
    } @else {
      {{ value() }}
    }
  `,
  styles: `
    :host {
      display: inline;
      overflow-wrap: anywhere;
    }

    .missing,
    .muted {
      color: var(--text-soft);
      font-style: italic;
    }

    a {
      color: var(--green);
    }
  `,
})
export class LegalValue {
  readonly value = input<string | null | undefined>();
  readonly kind = input<'text' | 'email' | 'phone'>('text');
  protected readonly dialable = computed(() => (this.value() ?? '').replace(/[^+\d]/g, ''));
}
