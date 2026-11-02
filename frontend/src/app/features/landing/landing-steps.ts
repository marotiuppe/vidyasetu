import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { I18n } from '../../core/i18n/i18n';
import { Reveal } from '../../core/ui/reveal';

/** `title` and `text` are dictionary keys, resolved in the template so the page follows the language. */
const STEPS = [
  {
    title: 'public.steps.setup.title',
    text: 'public.steps.setup.text',
  },
  {
    title: 'public.steps.people.title',
    text: 'public.steps.people.text',
  },
  {
    title: 'public.steps.run.title',
    text: 'public.steps.run.text',
  },
];

@Component({
  selector: 'sms-landing-steps',
  imports: [Reveal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing-steps.html',
  styleUrl: './landing-steps.css',
})
export class LandingSteps {
  protected readonly i18n = inject(I18n);
  protected readonly steps = STEPS;
}
