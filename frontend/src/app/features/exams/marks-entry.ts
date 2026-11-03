import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';

import { AcademicYear, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import {
  Exam,
  ExamsApi,
  MarkInputRow,
  MarkRow,
  MarkSheet,
  Subject,
  num,
} from '../../core/api/exams.api';
import { AuthService } from '../../core/auth/auth.service';
import { EXAM_MARK_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { focusById } from '../../core/ui/download';
import { FeeLookups } from '../fees/fee-lookups';
import { ExamBranchPicker } from './exam-branch-picker';
import { fieldValue, parseMarks } from './exam-labels';
import { ExamsNav } from './exams-nav';

/** Most rows one marks save accepts. */
const ROW_LIMIT = 200;

/** One student's line in the entry grid. `text` is what the teacher typed. */
export interface EntryRow {
  student_id: number;
  name: string;
  roll_no: number | null;
  text: string;
  absent: boolean;
}

/** Row-level problem from a 422 response: row number (1-based) or position in the rows list. */
function rowErrorsFrom(err: unknown): Map<number, string> {
  const out = new Map<number, string>();
  if (!(err instanceof HttpErrorResponse) || err.status !== 422) return out;
  const detail: unknown = err.error?.detail;
  if (!Array.isArray(detail)) return out;
  for (const item of detail as unknown[]) {
    const msg: unknown = (item as { msg?: unknown })?.msg;
    const rowNo: unknown = (item as { row?: unknown })?.row;
    const loc: unknown = (item as { loc?: unknown })?.loc;
    let index: number | null = null;
    if (typeof rowNo === 'number') index = rowNo - 1;
    else if (Array.isArray(loc)) {
      const hit = loc.find((p: unknown) => typeof p === 'number');
      if (typeof hit === 'number') index = hit;
    }
    if (index !== null && typeof msg === 'string') out.set(index, msg);
  }
  return out;
}

/**
 * Enter marks for one exam, section and subject. Keyboard friendly: Enter moves to the next
 * student. Absent is a separate tick, so an absent student never gets a mark.
 */
@Component({
  selector: 'sms-marks-entry',
  imports: [ExamsNav, ExamBranchPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './marks-entry.html',
  styleUrls: ['./exams-table.css', './marks-entry.css'],
})
export class MarksEntry {
  private readonly api = inject(ExamsApi);
  private readonly auth = inject(AuthService);
  private readonly lookups = inject(FeeLookups);
  protected readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly canEnter = this.auth.hasRole(...EXAM_MARK_ROLES);

  protected readonly years = computed<AcademicYear[]>(() => this.lookups.years());
  protected readonly yearChoice = signal<number | null>(null);
  protected readonly yearId = computed(() => this.yearChoice() ?? this.lookups.currentYearId());

  protected readonly exams = signal<Exam[]>([]);
  protected readonly subjects = signal<Subject[]>([]);
  protected readonly classSubjectIds = signal<number[]>([]);
  protected readonly examId = signal(0);
  protected readonly sectionId = signal(0);
  protected readonly subjectId = signal(0);

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
  protected readonly classNameOf = computed(() => {
    const names = new Map(this.lookups.classes().map((c) => [c.id, c.name]));
    return (classId: number) => names.get(classId) ?? '';
  });
  protected readonly sectionLabel = (section: Section): string =>
    `${this.classNameOf()(section.class_id)} ${section.name}`.trim();

  /** Subjects the chosen section's class studies. */
  protected readonly subjectOptions = computed<Subject[]>(() => {
    const ids = new Set(this.classSubjectIds());
    return this.subjects().filter((s) => ids.has(s.id));
  });

  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly saved = signal<number | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly sheet = signal<MarkSheet | null>(null);
  protected readonly rows = signal<EntryRow[]>([]);
  protected readonly serverErrors = signal<Map<number, string>>(new Map());

  protected readonly editable = computed(() => {
    const s = this.sheet();
    return !!s && this.canEnter && !s.exam.locked;
  });
  protected readonly tooMany = computed(() => this.rows().length > ROW_LIMIT);

  /** Rows with a value that is not a valid mark for this exam. */
  protected readonly problemCount = computed(() => {
    const max = this.sheet()?.exam.max_marks ?? 0;
    return this.rows().filter((r) => this.problemKey(r, max) !== null).length;
  });

  constructor() {
    this.lookups.load();
    effect(() => {
      const branch = this.scope.branch();
      untracked(() => this.switchBranch(branch));
    });
    effect(() => {
      const year = this.yearId();
      this.scope.branch();
      untracked(() => this.loadExams(year));
    });
    effect(() => {
      const sectionId = this.sectionId();
      untracked(() => this.loadClassSubjects(sectionId));
    });
    effect(() => {
      const exam = this.examId();
      const section = this.sectionId();
      const subject = this.subjectId();
      untracked(() => {
        if (exam && section && subject) this.load(exam, section, subject);
        else this.sheet.set(null);
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
    this.subjectId.set(0);
  }

  protected pickSubject(event: Event): void {
    this.subjectId.set(Number(fieldValue(event)));
  }

  protected setText(index: number, event: Event): void {
    const text = fieldValue(event);
    this.updateRow(index, (r) => ({ ...r, text }));
  }

  protected setAbsent(index: number, event: Event): void {
    const absent = (event.target as HTMLInputElement).checked;
    this.updateRow(index, (r) => ({ ...r, absent, text: absent ? '' : r.text }));
  }

  /** Enter moves to the next student's marks box. */
  protected next(index: number, event: Event): void {
    event.preventDefault();
    focusById(`mark-${index + 1}`);
  }

  /** Problem text for one row (client check), or null. */
  protected problem(row: EntryRow): string | null {
    const max = this.sheet()?.exam.max_marks ?? 0;
    const key = this.problemKey(row, max);
    if (key) return this.i18n.t(key, { max });
    const server = this.serverErrors().get(this.rows().indexOf(row));
    return server ?? null;
  }

  protected save(): void {
    const s = this.sheet();
    if (!s || !this.editable() || this.problemCount() > 0 || this.tooMany()) return;
    this.error.set(null);
    this.saved.set(null);
    this.serverErrors.set(new Map());
    const body: MarkInputRow[] = this.rows().map((r) => ({
      student_id: r.student_id,
      marks: r.absent ? null : parseMarks(r.text),
      absent: r.absent,
    }));
    this.saving.set(true);
    this.api
      .saveMarks({
        exam_id: s.exam.id,
        subject_id: s.subject.id,
        section_id: this.sectionId(),
        rows: body,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.saved.set(body.length);
          this.load(s.exam.id, this.sectionId(), s.subject.id);
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.serverErrors.set(rowErrorsFrom(err));
          this.error.set(
            rowErrorsFrom(err).size ? this.i18n.t('exams.marks.rowErrors') : apiErrorMessage(err),
          );
        },
      });
  }

  private problemKey(row: EntryRow, max: number): string | null {
    if (row.absent || row.text.trim() === '') return null;
    const value = parseMarks(row.text);
    if (value === null) return 'exams.marks.invalid';
    if (value > max) return 'exams.marks.range';
    return null;
  }

  private updateRow(index: number, change: (r: EntryRow) => EntryRow): void {
    this.rows.update((list) => list.map((r, i) => (i === index ? change(r) : r)));
    if (this.serverErrors().has(index)) {
      const next = new Map(this.serverErrors());
      next.delete(index);
      this.serverErrors.set(next);
    }
    this.saved.set(null);
  }

  /** Another branch: its subjects, and no exam, section or subject carried over. */
  private switchBranch(branch: number | null): void {
    this.examId.set(0);
    this.sectionId.set(0);
    this.subjectId.set(0);
    this.subjects.set([]);
    if (!branch) return;
    this.api.subjects().subscribe({
      next: (rows) => this.subjects.set(rows),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private loadExams(yearId: number): void {
    this.exams.set([]);
    if (!yearId || this.scope.choiceNeeded()) return;
    this.api.exams(yearId).subscribe({
      next: (rows) => this.exams.set(rows),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private loadClassSubjects(sectionId: number): void {
    this.classSubjectIds.set([]);
    const section = this.lookups.sections().find((s) => s.id === sectionId);
    if (!section) return;
    this.api.classSubjects(section.class_id).subscribe({
      next: (res) => this.classSubjectIds.set(res.subject_ids),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private load(examId: number, sectionId: number, subjectId: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.marks(examId, sectionId, subjectId).subscribe({
      next: (sheet) => {
        this.sheet.set(sheet);
        this.rows.set(sheet.students.map((s: MarkRow) => this.rowOf(s)));
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.sheet.set(null);
        this.rows.set([]);
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private rowOf(s: MarkRow): EntryRow {
    const value = num(s.marks);
    return {
      student_id: s.student_id,
      name: s.name,
      roll_no: s.roll_no,
      text: value === null ? '' : String(value),
      absent: s.absent,
    };
  }
}
