import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { AcademicYear } from '../../core/api/academics.api';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { AuthService } from '../../core/auth/auth.service';
import { EXAM_CONFIG_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { FeeLookups } from '../fees/fee-lookups';
import { AspectsConfig } from './aspects-config';
import { ClassSubjectsConfig } from './class-subjects-config';
import { ExamBranchPicker } from './exam-branch-picker';
import { ExamListConfig } from './exam-list-config';
import { fieldValue } from './exam-labels';
import { ExamsNav } from './exams-nav';
import { GradingConfig } from './grading-config';
import { SubjectsConfig } from './subjects-config';
import { TermsConfig } from './terms-config';

type SetupTab = 'terms' | 'subjects' | 'class-subjects' | 'exams' | 'grading' | 'aspects';

const TABS: { id: SetupTab; labelKey: string }[] = [
  { id: 'terms', labelKey: 'exams.setup.terms' },
  { id: 'subjects', labelKey: 'exams.setup.subjects' },
  { id: 'class-subjects', labelKey: 'exams.setup.classSubjects' },
  { id: 'exams', labelKey: 'exams.setup.exams' },
  { id: 'grading', labelKey: 'exams.setup.grading' },
  { id: 'aspects', labelKey: 'exams.setup.aspects' },
];

/** Exam setup landing: academic year and the setup tabs (school owner, management and headmaster). */
@Component({
  selector: 'sms-exams',
  imports: [
    ExamsNav,
    ExamBranchPicker,
    TermsConfig,
    SubjectsConfig,
    ClassSubjectsConfig,
    ExamListConfig,
    GradingConfig,
    AspectsConfig,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './exams.html',
})
export class ExamsPage {
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);
  private readonly lookups = inject(FeeLookups);
  protected readonly scope = inject(ExamBranchService);

  protected readonly tabs = TABS;
  protected readonly canConfigure = this.auth.hasRole(...EXAM_CONFIG_ROLES);
  protected readonly years = computed<AcademicYear[]>(() => this.lookups.years());

  protected readonly current = signal<SetupTab>('terms');
  private readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());

  constructor() {
    this.lookups.load();
  }

  protected pickYear(event: Event): void {
    this.yearChoice.set(Number(fieldValue(event)));
  }

  protected select(id: SetupTab): void {
    this.current.set(id);
  }
}
