import { ChangeDetectionStrategy, Component } from '@angular/core';

import { Reveal } from '../../core/ui/reveal';

const STEPS = [
  {
    title: 'Set up your school and branches',
    text: 'Create the school, its branches, classes and academic year.',
  },
  {
    title: 'Add students, guardians and staff',
    text: 'Bring in student records, link guardians and invite your team with the right roles.',
  },
  {
    title: 'Run the day: attendance, notices, fees',
    text: 'Mark attendance, publish notices and collect fees while families stay informed.',
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
  protected readonly steps = STEPS;
}
