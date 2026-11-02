import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { LegalService } from '../../core/api/legal.service';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-grievances',
  imports: [LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './grievances.html',
})
export class Grievances {
  protected readonly legal = inject(LegalService).info;
}
