import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { FEE_MANAGER_ROLES, FEE_VIEW_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';

interface ToolLink {
  path: string;
  labelKey: string;
}

/** Links between the fees screen and the fee tools. Each tool only shows for the roles that may open it. */
@Component({
  selector: 'sms-fee-tools-nav',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './fee-tools-nav.css',
  template: `
    <nav class="tabs tool-tabs" [attr.aria-label]="i18n.t('fees.tools.nav.label')">
      @for (link of links(); track link.path) {
        <a
          class="tab"
          [routerLink]="link.path"
          routerLinkActive
          #rla="routerLinkActive"
          [routerLinkActiveOptions]="{ exact: true, queryParams: 'ignored' }"
          [attr.aria-current]="rla.isActive ? 'page' : null"
        >
          {{ i18n.t(link.labelKey) }}
        </a>
      }
    </nav>
  `,
})
export class FeeToolsNav {
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  protected readonly links = computed<ToolLink[]>(() => {
    const list: ToolLink[] = [{ path: '/fees', labelKey: 'fees.tools.nav.fees' }];
    if (this.auth.hasRole(...FEE_VIEW_ROLES))
      list.push({ path: '/fees/concessions', labelKey: 'fees.tools.nav.concessions' });
    if (this.auth.hasRole(...FEE_MANAGER_ROLES))
      list.push({ path: '/fees/late-fees', labelKey: 'fees.tools.nav.lateFees' });
    if (this.auth.hasRole(...FEE_VIEW_ROLES))
      list.push({ path: '/fees/reminders', labelKey: 'fees.tools.nav.reminders' });
    return list;
  });
}
