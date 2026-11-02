import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  viewChild,
} from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import { I18n } from '../../core/i18n/i18n';
import { LegalLinks } from '../../core/legal/legal-links';
import { LandingCta } from './landing-cta';
import { LandingFeatures } from './landing-features';
import { LandingHero } from './landing-hero';
import { LandingSteps } from './landing-steps';
import { scrollToId } from './scroll';

/** Public landing page shown at "/" to visitors who are not signed in. */
@Component({
  selector: 'sms-landing',
  imports: [RouterLink, LandingHero, LandingFeatures, LandingSteps, LandingCta, LegalLinks],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing.html',
  styleUrl: './landing.css',
})
export class Landing {
  protected readonly i18n = inject(I18n);
  protected readonly year = new Date().getFullYear();
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('main');

  constructor() {
    const title = inject(Title);
    const previous = title.getTitle();
    effect(() => title.setTitle(this.i18n.t('public.landing.pageTitle')));
    inject(DestroyRef).onDestroy(() => title.setTitle(previous));
  }

  protected goTo(event: Event, id: string): void {
    scrollToId(event, id);
  }

  protected skip(event: Event): void {
    event.preventDefault();
    this.main().nativeElement.focus();
  }
}
