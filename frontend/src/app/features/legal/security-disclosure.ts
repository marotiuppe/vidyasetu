import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { LegalService } from '../../core/api/legal.service';
import { I18n } from '../../core/i18n/i18n';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-security-disclosure',
  imports: [LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './security-disclosure.html',
})
export class SecurityDisclosure {
  protected readonly i18n = inject(I18n);
  protected readonly legal = inject(LegalService).info;
}
