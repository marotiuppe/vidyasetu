import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LegalService } from '../../core/api/legal.service';
import { LegalValue } from './legal-value';

@Component({
  selector: 'sms-children-privacy',
  imports: [RouterLink, LegalValue],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './children-privacy.html',
})
export class ChildrenPrivacy {
  protected readonly legal = inject(LegalService).info;
}
