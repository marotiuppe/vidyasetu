import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { EXAM_CONFIG_ROLES, EXAM_VIEW_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';

interface ExamLink {
  path: string;
  labelKey: string;
}

/** Links between the exam screens. Each link only shows for the roles that may open it. */
@Component({
  selector: 'sms-exams-nav',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './exams-nav.css',
  template: `
    <nav class="tabs exam-tabs" [attr.aria-label]="i18n.t('exams.nav.label')">
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
export class ExamsNav {
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  protected readonly links = computed<ExamLink[]>(() => {
    const list: ExamLink[] = [];
    if (this.auth.hasRole(...EXAM_CONFIG_ROLES))
      list.push({ path: '/exams', labelKey: 'exams.nav.setup' });
    if (this.auth.hasRole(...EXAM_VIEW_ROLES)) {
      list.push({ path: '/exams/marks', labelKey: 'exams.nav.marks' });
      list.push({ path: '/exams/aspects', labelKey: 'exams.nav.aspects' });
      list.push({ path: '/exams/class-summary', labelKey: 'exams.nav.summary' });
    }
    return list;
  });
}
