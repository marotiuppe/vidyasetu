import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';

import { apiErrorMessage } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { ExamsApi, Subject } from '../../core/api/exams.api';
import { I18n } from '../../core/i18n/i18n';
import { FeeLookups } from '../fees/fee-lookups';
import { fieldChecked, fieldValue, kindText } from './exam-labels';

/** Which subjects each class studies in this branch. */
@Component({
  selector: 'sms-class-subjects-config',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './class-subjects-config.html',
  styleUrl: './exams-table.css',
})
export class ClassSubjectsConfig {
  private readonly api = inject(ExamsApi);
  private readonly lookups = inject(FeeLookups);
  private readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly kindLabel = (kind: Subject['kind']) => kindText(kind, this.i18n.t);
  /** Only the classes of the branch the screen works on. */
  protected readonly classes = computed(() => {
    const branch = this.scope.branch();
    if (!branch) return [];
    return this.lookups.classesOf(branch).sort((a, b) => a.level - b.level);
  });

  protected readonly subjects = signal<Subject[]>([]);
  protected readonly classId = signal(0);
  protected readonly selected = signal<ReadonlySet<number>>(new Set());
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly saved = signal(false);

  constructor() {
    this.lookups.load();
    effect(() => {
      this.scope.branch();
      untracked(() => this.reset());
    });
  }

  /** Another branch: its subjects, and no class chosen yet. */
  private reset(): void {
    this.classId.set(0);
    this.selected.set(new Set());
    this.saved.set(false);
    this.error.set(null);
    this.api.subjects().subscribe({
      next: (rows) => this.subjects.set(rows),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  protected pickClass(event: Event): void {
    const id = Number(fieldValue(event));
    this.classId.set(id);
    this.selected.set(new Set());
    this.error.set(null);
    this.saved.set(false);
    if (!id) return;
    this.loading.set(true);
    this.api.classSubjects(id).subscribe({
      next: (res) => {
        this.selected.set(new Set(res.subject_ids));
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  protected toggle(subjectId: number, event: Event): void {
    const next = new Set(this.selected());
    if (fieldChecked(event)) next.add(subjectId);
    else next.delete(subjectId);
    this.selected.set(next);
    this.saved.set(false);
  }

  protected save(): void {
    const id = this.classId();
    if (!id) return;
    this.error.set(null);
    this.saving.set(true);
    this.api.saveClassSubjects(id, [...this.selected()]).subscribe({
      next: () => {
        this.saving.set(false);
        this.saved.set(true);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
