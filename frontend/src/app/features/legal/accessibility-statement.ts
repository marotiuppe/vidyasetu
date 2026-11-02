import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LegalService } from '../../core/api/legal.service';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-accessibility-statement',
  imports: [RouterLink, LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './accessibility-statement.html',
})
export class AccessibilityStatement {
  protected readonly legal = inject(LegalService).info;
}
