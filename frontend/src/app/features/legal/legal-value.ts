import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { I18n } from '../../core/i18n/i18n';

/**
 * One operator detail on a legal page. `undefined` means not loaded yet; `null` or empty means the
 * operator has not entered it, which is shown as muted text instead of a blank.
 */
@Component({
  selector: 'sms-legal-value',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (value() === undefined) {
      <span class="muted">{{ i18n.t('public.legal.value.loading') }}</span>
    } @else if (!value()) {
      <span class="missing">{{ i18n.t('public.legal.value.missing') }}</span>
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
  protected readonly i18n = inject(I18n);
  readonly value = input<string | null | undefined>();
  readonly kind = input<'text' | 'email' | 'phone'>('text');
  protected readonly dialable = computed(() => (this.value() ?? '').replace(/[^+\d]/g, ''));
}
