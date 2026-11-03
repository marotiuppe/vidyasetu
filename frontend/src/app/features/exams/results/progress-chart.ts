import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { Progress, num } from '../../../core/api/exams.api';
import { I18n } from '../../../core/i18n/i18n';
import { percentText } from '../exam-labels';

const WIDTH = 640;
const HEIGHT = 240;
const PAD = 36;
const COLORS = [
  'var(--green)',
  'var(--olive)',
  'var(--amber)',
  'var(--tone-sky-fg)',
  'var(--tone-peach-fg)',
  'var(--tone-lavender-fg)',
];

interface Line {
  name: string;
  color: string;
  path: string;
  dots: { x: number; y: number; label: string }[];
}

/**
 * Percent by term for each subject as an inline SVG line chart (no chart library). The same values
 * are listed in a table below it, so the numbers are readable without the picture.
 */
@Component({
  selector: 'sms-progress-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './progress-chart.html',
  styleUrls: ['./progress-chart.css', '../exams-table.css'],
})
export class ProgressChart {
  protected readonly i18n = inject(I18n);

  readonly data = input.required<Progress>();

  protected readonly width = WIDTH;
  protected readonly height = HEIGHT;
  protected readonly percentText = percentText;
  protected readonly pad = PAD;
  protected readonly gridLines = [0, 50, 100];

  protected readonly yOf = (percent: number): number =>
    HEIGHT - PAD - (Math.min(Math.max(percent, 0), 100) / 100) * (HEIGHT - 2 * PAD);

  protected readonly xOf = (index: number, count: number): number =>
    count <= 1 ? WIDTH / 2 : PAD + (index * (WIDTH - 2 * PAD)) / (count - 1);

  protected readonly termLabels = computed(() =>
    this.data().terms.map((t, i) => ({
      id: t.id,
      name: t.name,
      x: this.xOf(i, this.data().terms.length),
    })),
  );

  protected readonly lines = computed<Line[]>(() => {
    const count = this.data().terms.length;
    return this.data().subjects.map((s, idx) => {
      const dots: Line['dots'] = [];
      s.points.forEach((p, i) => {
        const value = num(p.percent);
        if (value === null) return;
        dots.push({
          x: this.xOf(i, count),
          y: this.yOf(value),
          label: percentText(value),
        });
      });
      return {
        name: s.name,
        color: COLORS[idx % COLORS.length],
        path: dots.map((d) => `${d.x},${d.y}`).join(' '),
        dots,
      };
    });
  });

  protected readonly summary = computed(() => {
    const names = this.data()
      .subjects.map((s) => s.name)
      .join(', ');
    return this.i18n.t('exams.progress.chartSummary', { subjects: names || '—' });
  });
}
