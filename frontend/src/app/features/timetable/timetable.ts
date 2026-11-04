import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ExamBranchService } from '../../core/api/exam-branch.service';
import { I18n } from '../../core/i18n/i18n';
import { ExamBranchPicker } from '../exams/exam-branch-picker';
import { fieldValue } from '../exams/exam-labels';
import { FeeLookups } from '../fees/fee-lookups';
import { PeriodsConfig } from './periods-config';
import { SectionGrid } from './section-grid';

type Tab = 'grid' | 'periods';

const TABS: { id: Tab; labelKey: string }[] = [
  { id: 'grid', labelKey: 'timetable.tab.grid' },
  { id: 'periods', labelKey: 'timetable.tab.periods' },
];

/** Timetable setup for the school owner, management and headmaster: periods and section grids. */
@Component({
  selector: 'sms-timetable',
  imports: [ExamBranchPicker, PeriodsConfig, SectionGrid],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './timetable.html',
})
export class TimetablePage {
  private readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);
  protected readonly scope = inject(ExamBranchService);

  protected readonly tabs = TABS;
  protected readonly current = signal<Tab>('grid');
  protected readonly years = computed(() => this.lookups.years());
  private readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());

  constructor() {
    this.lookups.load();
  }

  protected pickYear(event: Event): void {
    this.yearChoice.set(Number(fieldValue(event)));
  }

  protected select(id: Tab): void {
    this.current.set(id);
  }
}
