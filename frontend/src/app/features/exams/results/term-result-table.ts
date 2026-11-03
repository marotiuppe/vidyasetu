import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { ResultExamMark, ResultSubject, TermResult, num } from '../../../core/api/exams.api';
import { I18n } from '../../../core/i18n/i18n';
import { kindText, numberText, percentText, resultClass, resultText } from '../exam-labels';

interface ExamColumn {
  id: number;
  name: string;
  max: string;
}

/** Subjects of one term: each exam's marks, the weighted term percent, grade and pass or fail. */
@Component({
  selector: 'sms-term-result-table',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './term-result-table.html',
  styleUrl: '../exams-table.css',
})
export class TermResultTable {
  protected readonly i18n = inject(I18n);

  readonly term = input.required<TermResult>();

  protected readonly percentText = percentText;
  protected readonly numberText = numberText;
  protected readonly resultLabel = (r: TermResult['result']) => resultText(r, this.i18n.t);
  protected readonly resultBadge = resultClass;
  protected readonly kindLabel = (s: ResultSubject) => kindText(s.kind, this.i18n.t);

  /** Exams of this term, in the order they first appear across the subjects. */
  protected readonly columns = computed<ExamColumn[]>(() => {
    const seen = new Map<number, ExamColumn>();
    for (const s of this.term().subjects) {
      for (const e of s.exams) {
        if (!seen.has(e.exam_id))
          seen.set(e.exam_id, { id: e.exam_id, name: e.name, max: numberText(e.max_marks) });
      }
    }
    return [...seen.values()];
  });

  protected examOf(subject: ResultSubject, examId: number): ResultExamMark | null {
    return subject.exams.find((e) => e.exam_id === examId) ?? null;
  }

  protected markText(e: ResultExamMark | null): string {
    if (!e) return '—';
    if (e.absent) return this.i18n.t('exams.results.absent');
    return num(e.marks) === null ? '—' : numberText(e.marks);
  }
}
