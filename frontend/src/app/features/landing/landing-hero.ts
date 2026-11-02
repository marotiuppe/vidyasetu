import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

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
  protected goTo(event: Event, id: string): void {
    scrollToId(event, id);
  }
}
