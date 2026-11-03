import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { forkJoin } from 'rxjs';

import { AcademicYear, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import {
  AspectGrade,
  AspectGradeInput,
  AspectSheet,
  ExamTerm,
  ExamsApi,
  ReportAspect,
  TermRemarkRow,
} from '../../core/api/exams.api';
import { AuthService } from '../../core/auth/auth.service';
import { EXAM_MARK_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { FeeLookups } from '../fees/fee-lookups';
import { ExamBranchPicker } from './exam-branch-picker';
import { GRADE_OPTIONS, fieldValue, sectionText } from './exam-labels';
import { ExamsNav } from './exams-nav';

/** One student's aspect grades and remarks, as the grid edits them. */
export interface AspectEntry {
  student_id: number;
  name: string;
  roll_no: number | null;
  grades: Record<number, AspectGrade | ''>;
  remarks: Record<number, string>;
  termRemark: string;
}

/** Grades per aspect and the class teacher's remark, per student, for one term and section. */
@Component({
  selector: 'sms-aspect-grades',
  imports: [ExamsNav, ExamBranchPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './aspect-grades.html',
  styleUrls: ['./exams-table.css', './aspect-grades.css'],
})
export class AspectGradesPage {
  private readonly api = inject(ExamsApi);
  private readonly auth = inject(AuthService);
  private readonly lookups = inject(FeeLookups);
  protected readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly canEnter = this.auth.hasRole(...EXAM_MARK_ROLES);
  protected readonly grades = GRADE_OPTIONS;

  protected readonly years = computed<AcademicYear[]>(() => this.lookups.years());
  private readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());
  protected readonly terms = signal<ExamTerm[]>([]);
  protected readonly termId = signal(0);
  protected readonly sectionId = signal(0);

  /** Sections of the chosen branch only. */
  protected readonly sectionList = computed<Section[]>(() => {
    const branch = this.scope.branch();
    if (!branch) return [];
    const classes = new Map<number, SchoolClass>(
      this.lookups.classesOf(branch).map((c) => [c.id, c]),
    );
    return this.lookups
      .sections()
      .filter((s) => s.branch_id === branch)
      .sort((a, b) => {
        const la = classes.get(a.class_id)?.level ?? 0;
        const lb = classes.get(b.class_id)?.level ?? 0;
        return la - lb || a.class_id - b.class_id || a.name.localeCompare(b.name);
      });
  });
  protected readonly sectionLabel = (section: Section): string => {
    const className = this.lookups.classes().find((c) => c.id === section.class_id)?.name ?? '';
    return `${className} ${section.name}`.trim();
  };
  protected readonly aspectSection = (aspect: ReportAspect) =>
    sectionText(aspect.section, this.i18n.t);

  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly aspects = signal<ReportAspect[]>([]);
  protected readonly rows = signal<AspectEntry[]>([]);

  constructor() {
    this.lookups.load();
    effect(() => {
      const year = this.yearId();
      this.scope.branch();
      untracked(() => this.loadTerms(year));
    });
  }

  protected pickYear(event: Event): void {
    this.yearChoice.set(Number(fieldValue(event)));
  }

  protected pickTerm(event: Event): void {
    this.termId.set(Number(fieldValue(event)));
    this.refresh();
  }

  protected pickSection(event: Event): void {
    this.sectionId.set(Number(fieldValue(event)));
    this.refresh();
  }

  protected setGrade(index: number, aspectId: number, event: Event): void {
    const value = fieldValue(event) as AspectGrade | '';
    this.updateRow(index, (r) => ({ ...r, grades: { ...r.grades, [aspectId]: value } }));
  }

  protected setRemark(index: number, aspectId: number, event: Event): void {
    const value = fieldValue(event);
    this.updateRow(index, (r) => ({ ...r, remarks: { ...r.remarks, [aspectId]: value } }));
  }

  protected setTermRemark(index: number, event: Event): void {
    const value = fieldValue(event);
    this.updateRow(index, (r) => ({ ...r, termRemark: value }));
  }

  protected save(): void {
    const term = this.termId();
    const section = this.sectionId();
    if (!term || !section) return;
    this.error.set(null);
    this.saved.set(false);
    const gradeRows: AspectGradeInput[] = [];
    for (const r of this.rows()) {
      for (const a of this.aspects()) {
        const grade = r.grades[a.id] ?? '';
        const remark = (r.remarks[a.id] ?? '').trim();
        gradeRows.push({
          student_id: r.student_id,
          aspect_id: a.id,
          grade: grade === '' ? null : grade,
          remark: remark || null,
        });
      }
    }
    const remarkRows = this.rows().map((r) => ({
      student_id: r.student_id,
      remark: r.termRemark.trim() || null,
    }));
    this.saving.set(true);
    forkJoin([
      this.api.saveAspectGrades({ term_id: term, section_id: section, rows: gradeRows }),
      this.api.saveTermRemarks({ term_id: term, section_id: section, rows: remarkRows }),
    ]).subscribe({
      next: () => {
        this.saving.set(false);
        this.saved.set(true);
        this.refresh();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private loadTerms(year: number): void {
    this.terms.set([]);
    this.termId.set(0);
    this.sectionId.set(0);
    this.refresh();
    if (!year || this.scope.choiceNeeded()) return;
    this.api.terms(year).subscribe({
      next: (rows) => this.terms.set(rows),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private refresh(): void {
    const term = this.termId();
    const section = this.sectionId();
    this.saved.set(false);
    if (!term || !section) {
      this.rows.set([]);
      this.aspects.set([]);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      sheet: this.api.aspectGrades(term, section),
      remarks: this.api.termRemarks(term, section),
    }).subscribe({
      next: ({ sheet, remarks }) => {
        this.aspects.set(sheet.aspects);
        this.rows.set(this.buildRows(sheet, remarks));
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.rows.set([]);
        this.aspects.set([]);
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private buildRows(sheet: AspectSheet, remarks: TermRemarkRow[]): AspectEntry[] {
    const termRemark = new Map(remarks.map((r) => [r.student_id, r.remark ?? '']));
    return sheet.students.map((s) => {
      const grades: Record<number, AspectGrade | ''> = {};
      const aspectRemarks: Record<number, string> = {};
      for (const c of s.grades) {
        grades[c.aspect_id] = c.grade ?? '';
        aspectRemarks[c.aspect_id] = c.remark ?? '';
      }
      return {
        student_id: s.student_id,
        name: s.name,
        roll_no: s.roll_no,
        grades,
        remarks: aspectRemarks,
        termRemark: termRemark.get(s.student_id) ?? '',
      };
    });
  }

  private updateRow(index: number, change: (r: AspectEntry) => AspectEntry): void {
    this.rows.update((list) => list.map((r, i) => (i === index ? change(r) : r)));
    this.saved.set(false);
  }
}
