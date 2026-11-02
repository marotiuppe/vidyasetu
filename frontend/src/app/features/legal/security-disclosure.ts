import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { LegalService } from '../../core/api/legal.service';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-security-disclosure',
  imports: [LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './security-disclosure.html',
})
export class SecurityDisclosure {
  protected readonly legal = inject(LegalService).info;
}
