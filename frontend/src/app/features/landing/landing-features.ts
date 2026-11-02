import { ChangeDetectionStrategy, Component } from '@angular/core';

import { Icon, IconName } from '../../core/ui/icon';
import { Reveal } from '../../core/ui/reveal';

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
    title: 'Students and guardians',
    text: 'Admit students, keep records in one place and link each child to their guardians.',
  },
  {
    icon: 'calendar',
    tone: 'tone-sky',
    title: 'Daily attendance',
    text: 'Mark attendance for a class in a few taps and see summaries for students and staff.',
  },
  {
    icon: 'megaphone',
    tone: 'tone-lavender',
    title: 'Notices and circulars',
    text: 'Publish notices to the whole school or to chosen groups, and see who has read them.',
  },
  {
    icon: 'receipt',
    tone: 'tone-peach',
    title: 'Fees and receipts',
    text: 'Set up fee heads, raise invoices, record payments and hand out receipts.',
  },
  {
    icon: 'user',
    tone: 'tone-green',
    title: 'Parent and student portal',
    text: 'Families sign in to see attendance, notices and fee dues for their own children.',
  },
  {
    icon: 'building',
    tone: 'tone-sky',
    title: 'Many schools and branches',
    text: 'Run several schools or branches on one platform, each isolated from the others.',
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
  protected readonly features = FEATURES;
}
