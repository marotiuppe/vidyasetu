import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { scrollToId } from './scroll';

@Component({
  selector: 'sms-landing-hero',
  imports: [RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing-hero.html',
  styleUrl: './landing-hero.css',
})
export class LandingHero {
  protected readonly i18n = inject(I18n);

  protected goTo(event: Event, id: string): void {
    scrollToId(event, id);
  }
}
