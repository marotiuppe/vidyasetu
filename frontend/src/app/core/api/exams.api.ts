import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { ExamBranchService } from './exam-branch.service';
import { StudentsApi } from './students.api';

const API = '/api/v1/exams';

/**
 * Decimal values (marks, percents, grade points) may arrive as JSON numbers or as strings.
 * Read them with `num()` so the screens never do string maths.
 */
export type Decimal = number | string;

/** Number from a server decimal, or null when there is no value. */
export function num(value: Decimal | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export type ExamSection = 'co_curricular' | 'behavioural' | 'self_awareness' | 'health';
export type SubjectKind = 'scholastic' | 'co_scholastic';
export type AspectGrade = 'A' | 'B' | 'C' | 'D' | 'E';
export type ResultFormat = 'cbse' | 'hpc';
export type PassResult = 'pass' | 'fail';

export const EXAM_SECTIONS: ExamSection[] = [
  'co_curricular',
  'behavioural',
  'self_awareness',
  'health',
];
export const SUBJECT_KINDS: SubjectKind[] = ['scholastic', 'co_scholastic'];
export const ASPECT_GRADES: AspectGrade[] = ['A', 'B', 'C', 'D', 'E'];
export const RESULT_FORMATS: ResultFormat[] = ['cbse', 'hpc'];

export interface ExamTerm {
  id: number;
  academic_year_id: number;
  name: string;
  sequence: number;
  weight_percent: number;
}

export interface TermInput {
  academic_year_id: number;
  name: string;
  sequence: number;
  weight_percent: number;
}

export interface Subject {
  id: number;
  name: string;
  code: string | null;
  kind: SubjectKind;
  active: boolean;
}

export interface SubjectInput {
  name: string;
  code: string | null;
  kind: SubjectKind;
  active: boolean;
}

export interface ClassSubjects {
  class_id: number;
  subject_ids: number[];
}

export interface Exam {
  id: number;
  term_id: number;
  name: string;
  max_marks: number;
  weight_percent: number;
  published: boolean;
  locked: boolean;
}

export interface ExamInput {
  term_id: number;
  name: string;
  max_marks: number;
  weight_percent: number;
  published: boolean;
  locked: boolean;
}

export type ExamUpdate = Partial<Omit<ExamInput, 'term_id'>>;

export interface GradeBand {
  id?: number;
  min_percent: number;
  grade: string;
  grade_point: Decimal | null;
  remark: string | null;
}

export interface GradeScale {
  id: number;
  name: string;
  pass_percent: number;
  is_default: boolean;
  bands: GradeBand[];
}

export interface GradeScaleInput {
  name: string;
  pass_percent: number;
  bands: GradeBand[];
}

export interface ReportAspect {
  id: number;
  section: ExamSection;
  name: string;
  active: boolean;
  sequence: number;
}

export interface AspectInput {
  section: ExamSection;
  name: string;
  active: boolean;
  sequence: number;
}

export type AspectUpdate = Partial<Omit<AspectInput, 'section'>>;

export interface MarkRow {
  student_id: number;
  name: string;
  roll_no: number | null;
  marks: Decimal | null;
  absent: boolean;
}

export interface MarkSheet {
  exam: Exam;
  subject: Subject;
  students: MarkRow[];
}

export interface MarkInputRow {
  student_id: number;
  marks: number | null;
  absent: boolean;
}

export interface MarkSaveInput {
  exam_id: number;
  subject_id: number;
  section_id: number;
  rows: MarkInputRow[];
}

export interface AspectCell {
  aspect_id: number;
  grade: AspectGrade | null;
  remark: string | null;
}

export interface AspectRow {
  student_id: number;
  name: string;
  roll_no: number | null;
  grades: AspectCell[];
}

export interface AspectSheet {
  aspects: ReportAspect[];
  students: AspectRow[];
}

export interface AspectGradeInput {
  student_id: number;
  aspect_id: number;
  grade: AspectGrade | null;
  remark: string | null;
}

export interface AspectGradeSaveInput {
  term_id: number;
  section_id: number;
  rows: AspectGradeInput[];
}

export interface TermRemarkRow {
  student_id: number;
  name: string;
  roll_no: number | null;
  remark: string | null;
}

export interface TermRemarkSaveInput {
  term_id: number;
  section_id: number;
  rows: { student_id: number; remark: string | null }[];
}

export interface ResultExamMark {
  exam_id: number;
  name: string;
  max_marks: Decimal;
  marks: Decimal | null;
  absent: boolean;
  percent: Decimal | null;
  weight_percent: number;
}

export interface ResultSubject {
  subject_id: number;
  name: string;
  kind: SubjectKind;
  exams: ResultExamMark[];
  /** Weighted percent of the subject in this term. */
  percent: Decimal | null;
  grade: string | null;
  grade_point: Decimal | null;
  result: PassResult | null;
}

export interface ResultAspect {
  aspect_id: number;
  section: ExamSection;
  name: string;
  grade: AspectGrade | null;
  remark: string | null;
}

export interface AttendanceSummary {
  present: number;
  total: number;
}

export interface TermResult {
  term_id: number;
  name: string;
  sequence: number;
  weight_percent: number;
  subjects: ResultSubject[];
  percent: Decimal | null;
  grade: string | null;
  grade_point: Decimal | null;
  result: PassResult | null;
  /** Only present when the school shows ranks. */
  rank: number | null;
  aspects: ResultAspect[];
  remark: string | null;
}

export interface AnnualResult {
  percent: Decimal | null;
  grade: string | null;
  grade_point: Decimal | null;
  result: PassResult | null;
  /** Terms did not add up to 100%, so equal weights were used. */
  equal_weights: boolean;
}

export interface ResultStudent {
  id: number;
  name: string;
  admission_no: string;
  class_name: string | null;
  section_name: string | null;
  roll_no: number | null;
}

export interface ResultReport {
  student: ResultStudent;
  academic_year: { id: number; name: string };
  report_format: ResultFormat;
  terms: TermResult[];
  annual: AnnualResult | null;
  attendance: AttendanceSummary | null;
}

export interface ResultQuery {
  student_id: number;
  academic_year_id: number;
  include_unpublished?: boolean;
  format?: ResultFormat;
}

export interface ClassSubjectSummary {
  subject_id: number;
  name: string;
  average: Decimal | null;
  highest: Decimal | null;
  fail_count: number;
}

export interface ClassSummary {
  exam: Exam;
  student_count: number;
  average: Decimal | null;
  highest: Decimal | null;
  fail_count: number;
  subjects: ClassSubjectSummary[];
}

export interface ProgressTerm {
  id: number;
  name: string;
  sequence: number;
}

export interface ProgressSubject {
  subject_id: number;
  name: string;
  /** One point per term, in the order of `terms`. */
  points: { term_id: number; percent: Decimal | null }[];
}

export interface Progress {
  terms: ProgressTerm[];
  subjects: ProgressSubject[];
}

/** Keep only the parameters that have a value. */
function toParams(
  values: Record<string, string | number | boolean | null | undefined>,
): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    params = params.set(key, String(value));
  }
  return params;
}

/** Typed client for exam setup, marks, aspects, class summaries and report cards. */
@Injectable({ providedIn: 'root' })
export class ExamsApi {
  private readonly http = inject(HttpClient);
  private readonly students = inject(StudentsApi);
  private readonly branch = inject(ExamBranchService);

  // Terms
  terms(academicYearId: number): Observable<ExamTerm[]> {
    return this.http.get<ExamTerm[]>(`${API}/terms`, {
      params: this.branchParams({ academic_year_id: academicYearId }),
    });
  }

  createTerm(body: TermInput): Observable<ExamTerm> {
    return this.http.post<ExamTerm>(`${API}/terms`, body, { params: this.branchParams() });
  }

  updateTerm(id: number, body: Partial<Omit<TermInput, 'academic_year_id'>>): Observable<ExamTerm> {
    return this.http.patch<ExamTerm>(`${API}/terms/${id}`, body);
  }

  // Subjects and class subjects
  subjects(): Observable<Subject[]> {
    return this.http.get<Subject[]>(`${API}/subjects`, { params: this.branchParams() });
  }

  createSubject(body: SubjectInput): Observable<Subject> {
    return this.http.post<Subject>(`${API}/subjects`, body, { params: this.branchParams() });
  }

  updateSubject(id: number, body: Partial<SubjectInput>): Observable<Subject> {
    return this.http.patch<Subject>(`${API}/subjects/${id}`, body);
  }

  classSubjects(classId: number): Observable<ClassSubjects> {
    return this.http.get<ClassSubjects>(`${API}/class-subjects`, {
      params: toParams({ class_id: classId }),
    });
  }

  saveClassSubjects(classId: number, subjectIds: number[]): Observable<ClassSubjects> {
    return this.http.put<ClassSubjects>(`${API}/class-subjects`, {
      class_id: classId,
      subject_ids: subjectIds,
    });
  }

  // Exams
  exams(academicYearId: number): Observable<Exam[]> {
    return this.http.get<Exam[]>(`${API}/exams`, {
      params: this.branchParams({ academic_year_id: academicYearId }),
    });
  }

  createExam(body: ExamInput): Observable<Exam> {
    return this.http.post<Exam>(`${API}/exams`, body);
  }

  updateExam(id: number, body: ExamUpdate): Observable<Exam> {
    return this.http.patch<Exam>(`${API}/exams/${id}`, body);
  }

  // Grading
  grading(): Observable<GradeScale> {
    return this.http.get<GradeScale>(`${API}/grading`);
  }

  saveGrading(body: GradeScaleInput): Observable<GradeScale> {
    return this.http.put<GradeScale>(`${API}/grading`, body);
  }

  // Aspects
  aspects(): Observable<ReportAspect[]> {
    return this.http.get<ReportAspect[]>(`${API}/aspects`, { params: this.branchParams() });
  }

  createAspect(body: AspectInput): Observable<ReportAspect> {
    return this.http.post<ReportAspect>(`${API}/aspects`, body, { params: this.branchParams() });
  }

  updateAspect(id: number, body: AspectUpdate): Observable<ReportAspect> {
    return this.http.patch<ReportAspect>(`${API}/aspects/${id}`, body);
  }

  // Marks
  marks(examId: number, sectionId: number, subjectId: number): Observable<MarkSheet> {
    return this.http.get<MarkSheet>(`${API}/marks`, {
      params: toParams({ exam_id: examId, section_id: sectionId, subject_id: subjectId }),
    });
  }

  saveMarks(body: MarkSaveInput): Observable<unknown> {
    return this.http.put(`${API}/marks`, body);
  }

  // Aspect grades and term remarks
  aspectGrades(termId: number, sectionId: number): Observable<AspectSheet> {
    return this.http.get<AspectSheet>(`${API}/aspect-grades`, {
      params: toParams({ term_id: termId, section_id: sectionId }),
    });
  }

  saveAspectGrades(body: AspectGradeSaveInput): Observable<unknown> {
    return this.http.put(`${API}/aspect-grades`, body);
  }

  termRemarks(termId: number, sectionId: number): Observable<TermRemarkRow[]> {
    return this.http.get<TermRemarkRow[]>(`${API}/term-remarks`, {
      params: toParams({ term_id: termId, section_id: sectionId }),
    });
  }

  saveTermRemarks(body: TermRemarkSaveInput): Observable<unknown> {
    return this.http.put(`${API}/term-remarks`, body);
  }

  // Results
  result(query: ResultQuery): Observable<ResultReport> {
    return this.http.get<ResultReport>(`${API}/results/student`, {
      params: this.resultParams(query),
    });
  }

  /** Report card PDF. The file name carries no personal data. */
  downloadReportCard(query: ResultQuery): Observable<void> {
    return this.http
      .get(`${API}/results/student.pdf`, { params: this.resultParams(query), responseType: 'blob' })
      .pipe(
        map((blob) => this.students.saveBlob(blob, `report-card-${query.academic_year_id}.pdf`)),
      );
  }

  classSummary(examId: number, sectionId: number): Observable<ClassSummary> {
    return this.http.get<ClassSummary>(`${API}/results/class`, {
      params: toParams({ exam_id: examId, section_id: sectionId }),
    });
  }

  progress(studentId: number, academicYearId: number): Observable<Progress> {
    return this.http.get<Progress>(`${API}/progress`, {
      params: toParams({ student_id: studentId, academic_year_id: academicYearId }),
    });
  }

  /** Query params plus `branch_id` when a school-wide account has picked a branch. */
  private branchParams(
    values: Record<string, string | number | boolean | null | undefined> = {},
  ): HttpParams {
    return toParams({ ...values, branch_id: this.branch.param() });
  }

  private resultParams(query: ResultQuery): HttpParams {
    return toParams({
      student_id: query.student_id,
      academic_year_id: query.academic_year_id,
      include_unpublished: query.include_unpublished,
      format: query.format,
    });
  }
}
