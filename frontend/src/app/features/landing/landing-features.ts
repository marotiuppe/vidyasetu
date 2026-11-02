import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { I18n } from '../../core/i18n/i18n';
import { Icon, IconName } from '../../core/ui/icon';
import { Reveal } from '../../core/ui/reveal';

/** `title` and `text` are dictionary keys, resolved in the template so the page follows the language. */
interface Feature {
  icon: IconName;
  tone: string;
  title: string;
  text: string;
}

const FEATURES: Feature[] = [
  {
    icon: 'users',
    tone: 'tone-green',
    title: 'public.features.students.title',
    text: 'public.features.students.text',
  },
  {
    icon: 'calendar',
    tone: 'tone-sky',
    title: 'public.features.attendance.title',
    text: 'public.features.attendance.text',
  },
  {
    icon: 'megaphone',
    tone: 'tone-lavender',
    title: 'public.features.notices.title',
    text: 'public.features.notices.text',
  },
  {
    icon: 'receipt',
    tone: 'tone-peach',
    title: 'public.features.fees.title',
    text: 'public.features.fees.text',
  },
  {
    icon: 'user',
    tone: 'tone-green',
    title: 'public.features.portal.title',
    text: 'public.features.portal.text',
  },
  {
    icon: 'building',
    tone: 'tone-sky',
    title: 'public.features.branches.title',
    text: 'public.features.branches.text',
  },
];

@Component({
  selector: 'sms-landing-features',
  imports: [Icon, Reveal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing-features.html',
  styleUrl: './landing-features.css',
})
export class LandingFeatures {
  protected readonly i18n = inject(I18n);
  protected readonly features = FEATURES;
}
