import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';

import { AcademicYear, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { ClassSummary, Exam, ExamsApi } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { FeeLookups } from '../fees/fee-lookups';
import { ExamsNav } from './exams-nav';
import { countText, fieldValue, numberText, percentText } from './exam-labels';

/** Class averages, highest marks and failures for one exam and section (staff only). */
@Component({
  selector: 'sms-class-summary',
  imports: [ExamsNav],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './class-summary.html',
  styleUrl: './exams-table.css',
})
export class ClassSummaryPage {
  private readonly api = inject(ExamsApi);
  private readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly numberText = numberText;
  protected readonly percentText = percentText;
  protected readonly countText = countText;

  protected readonly years = computed<AcademicYear[]>(() => this.lookups.years());
  private readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());
  protected readonly exams = signal<Exam[]>([]);
  protected readonly examId = signal(0);
  protected readonly sectionId = signal(0);

  protected readonly sectionList = computed<Section[]>(() => {
    const classes = new Map<number, SchoolClass>(this.lookups.classes().map((c) => [c.id, c]));
    return [...this.lookups.sections()].sort((a, b) => {
      const la = classes.get(a.class_id)?.level ?? 0;
      const lb = classes.get(b.class_id)?.level ?? 0;
      return la - lb || a.class_id - b.class_id || a.name.localeCompare(b.name);
    });
  });
  protected readonly sectionLabel = (section: Section): string => {
    const className = this.lookups.classes().find((c) => c.id === section.class_id)?.name ?? '';
    return `${className} ${section.name}`.trim();
  };

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<ClassSummary | null>(null);

  constructor() {
    this.lookups.load();
    effect(() => {
      const year = this.yearId();
      untracked(() => this.loadExams(year));
    });
    effect(() => {
      const exam = this.examId();
      const section = this.sectionId();
      untracked(() => {
        if (exam && section) this.load(exam, section);
        else this.summary.set(null);
      });
    });
  }

  protected pickYear(event: Event): void {
    this.yearChoice.set(Number(fieldValue(event)));
    this.examId.set(0);
  }

  protected pickExam(event: Event): void {
    this.examId.set(Number(fieldValue(event)));
  }

  protected pickSection(event: Event): void {
    this.sectionId.set(Number(fieldValue(event)));
  }

  private loadExams(year: number): void {
    this.exams.set([]);
    if (!year) return;
    this.api.exams(year).subscribe({
      next: (rows) => this.exams.set(rows),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private load(exam: number, section: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.classSummary(exam, section).subscribe({
      next: (res) => {
        this.summary.set(res);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.summary.set(null);
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
