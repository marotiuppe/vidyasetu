import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { I18n } from '../i18n/i18n';

/** `key` is a dictionary key for the link label; the label follows the active language. */
export const LEGAL_LINKS: readonly { key: string; path: string }[] = [
  { key: 'public.legal.link.privacy', path: '/privacy' },
  { key: 'public.legal.link.terms', path: '/terms' },
  { key: 'public.legal.link.children', path: '/children' },
  { key: 'public.legal.link.cookies', path: '/cookies' },
  { key: 'public.legal.link.accessibility', path: '/accessibility' },
  { key: 'public.legal.link.grievance', path: '/grievance' },
  { key: 'public.legal.link.security', path: '/security' },
];

/**
 * Links to every legal page. `list` shows them all; `disclosure` folds them under a "Legal" button
 * (used in the sidebar). The colour is inherited from the container.
 */
@Component({
  selector: 'sms-legal-links',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './legal-links.html',
  styleUrl: './legal-links.css',
})
export class LegalLinks {
  protected readonly i18n = inject(I18n);
  readonly variant = input<'list' | 'disclosure'>('list');
  /** School code: links then open that school's own legal pages (`/s/<code>/...`). */
  readonly schoolCode = input<string | null>(null);
  protected readonly links = computed(() => {
    const code = this.schoolCode();
    return LEGAL_LINKS.map((l) => ({
      label: this.i18n.t(l.key),
      path: code ? `/s/${encodeURIComponent(code)}${l.path}` : l.path,
    }));
  });
}
