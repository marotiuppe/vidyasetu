import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { LegalService } from '../../core/api/legal.service';
import { I18n } from '../../core/i18n/i18n';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-cookies-notice',
  imports: [LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cookies-notice.html',
})
export class CookiesNotice {
  protected readonly i18n = inject(I18n);
  protected readonly legal = inject(LegalService).info;
}
