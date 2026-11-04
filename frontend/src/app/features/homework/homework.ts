import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import { ExamBranchService } from '../../core/api/exam-branch.service';
import { ExamsApi, Subject } from '../../core/api/exams.api';
import { Homework, HomeworkApi, HomeworkFilters } from '../../core/api/homework.api';
import { Student, StudentsApi } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { HOMEWORK_WRITE_ROLES } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { ExamBranchPicker } from '../exams/exam-branch-picker';
import { fieldError, fieldValue } from '../exams/exam-labels';
import { FeeLookups } from '../fees/fee-lookups';

const PAGE_SIZE = 25;

interface DueGroup {
  date: string;
  items: Homework[];
}

/** Today as YYYY-MM-DD in the device's local time. */
function todayIso(): string {
  return new Date().toLocaleDateString('en-CA');
}

/**
 * Homework. Staff filter by section, subject and dates, and teachers, management and the
 * headmaster add, edit and delete. Parents and students see their child's homework by due date.
 */
@Component({
  selector: 'sms-homework',
  imports: [ReactiveFormsModule, ExamBranchPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './homework.html',
})
export class HomeworkPage {
  private readonly api = inject(HomeworkApi);
  private readonly exams = inject(ExamsApi);
  private readonly students = inject(StudentsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly lookups = inject(FeeLookups);
  protected readonly scope = inject(ExamBranchService);
  protected readonly i18n = inject(I18n);

  protected readonly selfService = this.auth.hasRole('parent', 'student');
  protected readonly canWrite = this.auth.hasRole(...HOMEWORK_WRITE_ROLES);
  protected readonly today = todayIso();
  protected readonly fieldError = (c: Parameters<typeof fieldError>[0]) =>
    fieldError(c, this.i18n.t);

  // Child switcher (parent and student)
  protected readonly children = signal<Student[]>([]);
  protected readonly childrenLoaded = signal(!this.selfService);
  private readonly childChoice = signal<number | null>(null);
  protected readonly studentId = computed(() => this.childChoice() ?? this.children()[0]?.id ?? 0);

  // Filters (staff)
  protected readonly classFilter = signal(0);
  protected readonly sectionFilter = signal(0);
  protected readonly subjectFilter = signal(0);
  protected readonly from = signal('');
  protected readonly to = signal('');
  protected readonly page = signal(1);

  protected readonly subjects = signal<Subject[]>([]);
  protected readonly classes = computed<SchoolClass[]>(() => {
    const branch = this.scope.branch();
    return branch ? this.lookups.classesOf(branch) : [];
  });
  protected readonly filterSections = computed<Section[]>(() =>
    this.lookups.sectionsOf(this.classFilter()),
  );
  protected readonly formSections = signal<Section[]>([]);

  protected readonly items = signal<Homework[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly lastPage = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));
  protected readonly groups = computed<DueGroup[]>(() => {
    const out: DueGroup[] = [];
    for (const hw of this.items()) {
      const last = out.at(-1);
      if (last && last.date === hw.due_date) last.items.push(hw);
      else out.push({ date: hw.due_date, items: [hw] });
    }
    return out;
  });

  // Form (teacher, management, headmaster)
  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Homework | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly formClass = signal(0);
  protected readonly form = this.fb.group({
    section_id: [0, [Validators.min(1)]],
    subject_id: [0, [Validators.min(1)]],
    title: ['', [Validators.required, Validators.maxLength(150)]],
    description: ['', Validators.maxLength(2000)],
    assigned_on: [todayIso(), Validators.required],
    due_date: [todayIso(), Validators.required],
  });

  constructor() {
    this.lookups.load();
    if (this.selfService) {
      this.students.list({}, 1, 100).subscribe({
        next: (p) => {
          this.children.set(p.items);
          this.childrenLoaded.set(true);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.childrenLoaded.set(true);
        },
      });
    }
    effect(() => {
      this.scope.branch();
      untracked(() => {
        this.classFilter.set(0);
        this.sectionFilter.set(0);
        this.page.set(1);
        if (!this.selfService && !this.scope.choiceNeeded()) this.loadSubjects();
      });
    });
    effect(() => {
      this.scope.branch();
      this.studentId();
      this.childrenLoaded();
      this.classFilter();
      this.sectionFilter();
      this.subjectFilter();
      this.from();
      this.to();
      this.page();
      untracked(() => this.load());
    });
  }

  protected pickChild(event: Event): void {
    this.childChoice.set(Number(fieldValue(event)));
    this.page.set(1);
  }

  protected pickClassFilter(event: Event): void {
    this.classFilter.set(Number(fieldValue(event)));
    this.sectionFilter.set(0);
    this.page.set(1);
  }

  protected pickSectionFilter(event: Event): void {
    this.sectionFilter.set(Number(fieldValue(event)));
    this.page.set(1);
  }

  protected pickSubjectFilter(event: Event): void {
    this.subjectFilter.set(Number(fieldValue(event)));
    this.page.set(1);
  }

  protected setFrom(event: Event): void {
    this.from.set(fieldValue(event));
    this.page.set(1);
  }

  protected setTo(event: Event): void {
    this.to.set(fieldValue(event));
    this.page.set(1);
  }

  protected go(page: number): void {
    this.page.set(Math.min(Math.max(1, page), this.lastPage()));
  }

  protected isOverdue(hw: Homework): boolean {
    return hw.due_date < this.today;
  }

  /** Date text such as 4 Nov 2026, in the active language. */
  protected fmt(iso: string): string {
    const d = new Date(`${iso}T00:00:00`);
    return d.toLocaleDateString(this.i18n.lang() === 'mr' ? 'mr-IN' : 'en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }

  protected sectionText(hw: Homework): string {
    return [hw.class_name, hw.section_name].filter(Boolean).join(' ');
  }

  // Form
  protected openNew(): void {
    this.editing.set(null);
    this.formClass.set(this.classFilter());
    this.formSections.set(this.lookups.sectionsOf(this.classFilter()));
    this.form.reset({
      section_id: this.sectionFilter(),
      subject_id: this.subjectFilter(),
      title: '',
      description: '',
      assigned_on: todayIso(),
      due_date: todayIso(),
    });
    this.form.controls.section_id.enable();
    this.formError.set(null);
    this.formOpen.set(true);
  }

  protected edit(hw: Homework): void {
    this.editing.set(hw);
    const section = this.lookups.sections().find((s) => s.id === hw.section_id);
    this.formClass.set(section?.class_id ?? 0);
    this.formSections.set(section ? this.lookups.sectionsOf(section.class_id) : []);
    this.form.reset({
      section_id: hw.section_id,
      subject_id: hw.subject_id,
      title: hw.title,
      description: hw.description ?? '',
      assigned_on: hw.assigned_on,
      due_date: hw.due_date,
    });
    this.form.controls.section_id.disable();
    this.formError.set(null);
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected pickFormClass(event: Event): void {
    const id = Number(fieldValue(event));
    this.formClass.set(id);
    this.formSections.set(this.lookups.sectionsOf(id));
    this.form.controls.section_id.setValue(0);
  }

  protected save(): void {
    this.formError.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    if (v.due_date < v.assigned_on) {
      this.formError.set(this.i18n.t('homework.form.dueBeforeAssigned'));
      return;
    }
    const base = {
      subject_id: v.subject_id,
      title: v.title.trim(),
      description: v.description.trim() || null,
      assigned_on: v.assigned_on,
      due_date: v.due_date,
    };
    const current = this.editing();
    const request = current
      ? this.api.update(current.id, base)
      : this.api.create({
          ...base,
          academic_year_id: this.lookups.currentYearId(),
          section_id: v.section_id,
        });
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const message = placeServerErrors(this.form, err);
        if (message) this.formError.set(message);
      },
    });
  }

  protected remove(hw: Homework): void {
    if (!window.confirm(this.i18n.t('homework.confirmDelete', { title: hw.title }))) return;
    this.error.set(null);
    this.api.remove(hw.id).subscribe({
      next: () => this.load(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private loadSubjects(): void {
    this.exams.subjects().subscribe({
      next: (rows) => this.subjects.set(rows.filter((s) => s.active)),
      error: () => this.subjects.set([]),
    });
  }

  private load(): void {
    if (!this.childrenLoaded()) return;
    if (this.selfService && !this.studentId()) {
      this.items.set([]);
      this.total.set(0);
      this.loading.set(false);
      return;
    }
    if (!this.selfService && this.scope.choiceNeeded()) {
      this.items.set([]);
      this.total.set(0);
      this.loading.set(false);
      return;
    }
    const filters: HomeworkFilters = {};
    if (this.selfService) filters.student_id = this.studentId();
    else {
      if (this.sectionFilter()) filters.section_id = this.sectionFilter();
      if (this.subjectFilter()) filters.subject_id = this.subjectFilter();
    }
    if (this.from()) filters.from = this.from();
    if (this.to()) filters.to = this.to();
    this.loading.set(true);
    this.error.set(null);
    this.api.list(filters, this.page(), PAGE_SIZE).subscribe({
      next: (p) => {
        this.items.set(p.items);
        this.total.set(p.total);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
