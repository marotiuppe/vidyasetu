import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Icon } from '../../core/ui/icon';
import { Reveal } from '../../core/ui/reveal';

@Component({
  selector: 'sms-landing-cta',
  imports: [RouterLink, Icon, Reveal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing-cta.html',
  styleUrl: './landing-cta.css',
})
export class LandingCta {}
