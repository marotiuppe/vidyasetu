import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { catchError, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { FeesApi, GenerateInput, GenerateResult, StructureItem } from '../../core/api/fees.api';
import { Student } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { formatPaise } from '../../core/ui/money';
import { FeeLookups } from './fee-lookups';
import { StudentPicker } from './student-picker';

type Target = 'class' | 'section' | 'students' | 'branch';

/** Bulk-create invoices from the fee structure for a class, a section or chosen students. */
@Component({
  selector: 'sms-invoice-generate',
  imports: [ReactiveFormsModule, Icon, StudentPicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './invoice-generate.html',
})
export class InvoiceGenerate {
  private readonly api = inject(FeesApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly lookups = inject(FeeLookups);
  protected readonly i18n = inject(I18n);

  readonly generated = output<void>();
  readonly closed = output<void>();

  protected readonly money = formatPaise;
  /** Branch-level roles always work in their own branch; only the school owner picks one. */
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly form = this.fb.group({
    yearId: [this.lookups.currentYearId()],
    title: [''],
    dueDate: [''],
    target: ['class' as Target],
    classId: [0],
    sectionId: [0],
    branchId: [0],
  });
  private readonly values = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });

  protected readonly students = signal<Student[]>([]);
  protected readonly structure = signal<StructureItem[]>([]);
  private readonly unchecked = signal<number[]>([]);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<GenerateResult | null>(null);

  protected readonly target = computed(() => this.values().target ?? 'class');
  protected readonly sectionOptions = computed(() =>
    this.lookups.sectionsOf(Number(this.values().classId)),
  );
  protected readonly studentIds = computed(() => this.students().map((s) => s.id));
  /** Fee heads and the class and section pickers only apply to a class or section. */
  protected readonly isClassTarget = computed(() => {
    const t = this.target();
    return t === 'class' || t === 'section';
  });

  constructor() {
    if (this.canPickBranch) this.lookups.loadBranches();
    toObservable(
      computed(() => ({
        y: Number(this.values().yearId),
        c: Number(this.values().classId),
        t: this.target(),
      })),
    )
      .pipe(
        tap(() => {
          this.structure.set([]);
          this.unchecked.set([]);
        }),
        switchMap((s) =>
          (s.t === 'class' || s.t === 'section') && s.y && s.c
            ? this.api.structure(s.y, s.c).pipe(catchError(() => of([] as StructureItem[])))
            : of([] as StructureItem[]),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((items) => this.structure.set(items));
  }

  protected isChecked(headId: number): boolean {
    return !this.unchecked().includes(headId);
  }

  protected toggleHead(headId: number): void {
    this.unchecked.update((u) =>
      u.includes(headId) ? u.filter((x) => x !== headId) : [...u, headId],
    );
  }

  protected addStudent(s: Student): void {
    this.students.update((list) => (list.some((x) => x.id === s.id) ? list : [...list, s]));
  }

  protected removeStudent(id: number): void {
    this.students.update((list) => list.filter((x) => x.id !== id));
  }

  protected submit(): void {
    this.error.set(null);
    this.result.set(null);
    const v = this.form.getRawValue();
    const title = v.title.trim();
    if (!v.yearId) return this.error.set(this.i18n.t('fees.setup.common.chooseYear'));
    if (!title) return this.error.set(this.i18n.t('fees.setup.generate.enterTitle'));
    if (!v.dueDate) return this.error.set(this.i18n.t('fees.setup.common.chooseDue'));

    const body: GenerateInput = { academic_year_id: v.yearId, title, due_date: v.dueDate };
    if (v.target === 'branch') {
      body.all_students = true;
      if (this.canPickBranch && v.branchId) body.branch_id = v.branchId;
    } else if (v.target === 'students') {
      if (!this.students().length)
        return this.error.set(this.i18n.t('fees.setup.generate.addStudent'));
      body.student_ids = this.studentIds();
    } else {
      if (!v.classId) return this.error.set(this.i18n.t('fees.setup.common.chooseClassError'));
      body.class_id = v.classId;
      if (v.target === 'section') {
        if (!v.sectionId)
          return this.error.set(this.i18n.t('fees.setup.common.chooseSectionError'));
        body.section_id = v.sectionId;
      }
      const chosen = this.structure()
        .filter((i) => this.isChecked(i.fee_head_id))
        .map((i) => i.fee_head_id);
      if (this.structure().length && !chosen.length)
        return this.error.set(this.i18n.t('fees.setup.generate.selectHead'));
      if (chosen.length && chosen.length < this.structure().length) body.fee_head_ids = chosen;
    }

    this.busy.set(true);
    this.api.generate(body).subscribe({
      next: (res) => {
        this.busy.set(false);
        this.result.set(res);
        this.generated.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
