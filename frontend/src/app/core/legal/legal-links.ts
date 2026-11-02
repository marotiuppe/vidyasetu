import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

export const LEGAL_LINKS: readonly { label: string; path: string }[] = [
  { label: 'Privacy policy', path: '/privacy' },
  { label: 'Terms of use', path: '/terms' },
  { label: "Children's privacy", path: '/children' },
  { label: 'Cookies and storage', path: '/cookies' },
  { label: 'Accessibility', path: '/accessibility' },
  { label: 'Grievances', path: '/grievance' },
  { label: 'Security', path: '/security' },
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
  readonly variant = input<'list' | 'disclosure'>('list');
  /** School code: links then open that school's own legal pages (`/s/<code>/...`). */
  readonly schoolCode = input<string | null>(null);
  protected readonly links = computed(() => {
    const code = this.schoolCode();
    return LEGAL_LINKS.map((l) => ({
      label: l.label,
      path: code ? `/s/${encodeURIComponent(code)}${l.path}` : l.path,
    }));
  });
}
