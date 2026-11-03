import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map } from 'rxjs';

import { AcademicYear } from '../../../core/api/academics.api';
import { apiErrorMessage } from '../../../core/api/api-error';
import {
  AnnualResult,
  Progress,
  RESULT_FORMATS,
  ResultFormat,
  ResultReport,
  ExamsApi,
  TermResult,
} from '../../../core/api/exams.api';
import { Student, StudentsApi } from '../../../core/api/students.api';
import { AuthService } from '../../../core/auth/auth.service';
import { EXAM_VIEW_ROLES } from '../../../core/auth/permissions';
import { I18n } from '../../../core/i18n/i18n';
import { Icon } from '../../../core/ui/icon';
import { FeeLookups } from '../../fees/fee-lookups';
import {
  countText,
  fieldValue,
  numberText,
  percentText,
  resultClass,
  resultText,
} from '../exam-labels';
import { ProgressChart } from './progress-chart';
import { TermResultTable } from './term-result-table';

/**
 * Report card for one student and academic year. Parents and students see their own children only
 * (after the school shows results); staff open it from a student's profile with `?student=`.
 */
@Component({
  selector: 'sms-results-page',
  imports: [Icon, TermResultTable, ProgressChart],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './results-page.html',
  styleUrl: './results-page.css',
})
export class ResultsPage {
  private readonly api = inject(ExamsApi);
  private readonly students = inject(StudentsApi);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  protected readonly selfService = this.auth.hasRole('parent', 'student');
  protected readonly canSeeUnpublished = this.auth.hasRole(...EXAM_VIEW_ROLES);
  protected readonly formats = RESULT_FORMATS;
  protected readonly countText = countText;
  protected readonly percentText = percentText;
  protected readonly numberText = numberText;
  protected readonly resultLabel = (r: TermResult['result']) => resultText(r, this.i18n.t);
  protected readonly resultBadge = resultClass;

  private readonly staffStudent = toSignal(
    this.route.queryParamMap.pipe(map((p) => Number(p.get('student')) || 0)),
    { initialValue: 0 },
  );

  protected readonly children = signal<Student[]>([]);
  private readonly childChoice = signal<number | null>(null);
  protected readonly studentId = computed(() => {
    if (!this.selfService) return this.staffStudent();
    return this.childChoice() ?? this.children()[0]?.id ?? 0;
  });

  protected readonly years = computed<AcademicYear[]>(() => this.lookups.years());
  private readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());

  protected readonly includeUnpublished = signal(false);
  protected readonly format = signal<ResultFormat | ''>('');

  protected readonly loading = signal(false);
  protected readonly downloading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly report = signal<ResultReport | null>(null);
  protected readonly progress = signal<Progress | null>(null);
  private readonly termChoice = signal<number | null>(null);
  protected readonly activeTerm = computed<TermResult | null>(() => {
    const terms = this.report()?.terms ?? [];
    const chosen = terms.find((t) => t.term_id === this.termChoice());
    return chosen ?? terms[terms.length - 1] ?? null;
  });
  protected readonly annual = computed<AnnualResult | null>(() => this.report()?.annual ?? null);

  constructor() {
    this.lookups.load();
    if (this.selfService) {
      this.students.list({}, 1, 100).subscribe({
        next: (page) => this.children.set(page.items),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
    }
    effect(() => {
      const student = this.studentId();
      const year = this.yearId();
      const unpublished = this.includeUnpublished();
      untracked(() => this.load(student, year, unpublished));
    });
  }

  protected pickChild(event: Event): void {
    this.childChoice.set(Number(fieldValue(event)));
  }

  protected pickYear(event: Event): void {
    this.yearChoice.set(Number(fieldValue(event)));
  }

  protected pickFormat(event: Event): void {
    this.format.set(fieldValue(event) as ResultFormat | '');
  }

  protected toggleUnpublished(event: Event): void {
    this.includeUnpublished.set((event.target as HTMLInputElement).checked);
  }

  protected selectTerm(termId: number): void {
    this.termChoice.set(termId);
  }

  protected isSelectedTerm(term: TermResult): boolean {
    return this.activeTerm()?.term_id === term.term_id;
  }

  protected downloadPdf(): void {
    const report = this.report();
    if (!report) return;
    this.downloading.set(true);
    this.error.set(null);
    this.api
      .downloadReportCard({
        student_id: this.studentId(),
        academic_year_id: report.academic_year.id,
        include_unpublished: this.includeUnpublished(),
        format: this.format() || undefined,
      })
      .subscribe({
        next: () => this.downloading.set(false),
        error: (err: unknown) => {
          this.downloading.set(false);
          this.error.set(apiErrorMessage(err));
        },
      });
  }

  private load(studentId: number, yearId: number, unpublished: boolean): void {
    this.report.set(null);
    this.progress.set(null);
    this.termChoice.set(null);
    if (!studentId || !yearId) return;
    this.loading.set(true);
    this.error.set(null);
    this.api
      .result({
        student_id: studentId,
        academic_year_id: yearId,
        include_unpublished: unpublished,
      })
      .subscribe({
        next: (report) => {
          this.report.set(report);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.loading.set(false);
        },
      });
    this.api.progress(studentId, yearId).subscribe({
      next: (p) => this.progress.set(p),
      error: () => this.progress.set(null),
    });
  }
}
