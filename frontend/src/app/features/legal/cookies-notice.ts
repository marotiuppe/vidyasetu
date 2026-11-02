import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { LegalService } from '../../core/api/legal.service';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-cookies-notice',
  imports: [LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cookies-notice.html',
})
export class CookiesNotice {
  protected readonly legal = inject(LegalService).info;
}
