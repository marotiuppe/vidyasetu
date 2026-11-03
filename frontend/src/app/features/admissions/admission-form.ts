import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AcademicYear, AcademicsApi, Branch, SchoolClass } from '../../core/api/academics.api';
import { AdmissionApp, AdmissionInput } from '../../core/api/admissions.api';
import { GENDERS, Gender, RELATIONS, Relation } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { todayIst } from '../../core/ui/dates';
import { PHONE_PATTERN } from '../students/student-labels';

/** What the form emits: the fields, plus `branch_id` only when an application is created by a school owner. */
export type AdmissionFormValue = AdmissionInput & { branch_id?: number | null };

/**
 * Applicant, guardian and admission fields. Used for a new enquiry and for editing an existing one.
 * The parent screen makes the API call; this component only validates and emits the values.
 */
@Component({
  selector: 'sms-admission-form',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admission-form.html',
  styleUrl: './admission-form.css',
})
export class AdmissionForm {
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  /** Existing application being edited; null when a new enquiry is created. */
  readonly app = input<AdmissionApp | null>(null);
  readonly busy = input(false);
  readonly error = input<string | null>(null);
  readonly submitted = output<AdmissionFormValue>();
  readonly cancelled = output<void>();

  protected readonly genders = GENDERS;
  protected readonly relations = RELATIONS;
  protected readonly today = todayIst();
  /** A school owner has no branch of their own and picks one; branch-level staff use their token's branch. */
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly pickedBranch = signal(0);

  /** The branch the application belongs to: its own on edit, the token's branch or the picked one on create. */
  private readonly branchId = computed(
    () => this.app()?.branch_id ?? this.auth.user()?.branch_id ?? this.pickedBranch(),
  );
  protected readonly classOptions = computed(() => {
    const b = this.branchId();
    return b ? this.classes().filter((c) => c.branch_id === b) : [];
  });

  protected readonly form = this.fb.group({
    branch_id: [0],
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    gender: ['' as Gender | ''],
    date_of_birth: [''],
    academic_year_id: [0],
    class_id: [0],
    guardian_name: ['', [Validators.required, Validators.maxLength(200)]],
    guardian_phone: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
    guardian_email: ['', [Validators.email, Validators.maxLength(254)]],
    guardian_relation: ['father' as Relation],
    address: [''],
    previous_school: ['', Validators.maxLength(200)],
    notes: [''],
  });

  constructor() {
    if (this.canPickBranch) {
      this.academics.branches().subscribe({
        next: (b) => this.branches.set(b),
        error: () => undefined,
      });
    }
    this.academics.years().subscribe({
      next: (y) => {
        this.years.set(y);
        if (!this.app()) {
          const current = y.find((v) => v.is_current)?.id ?? 0;
          this.form.controls.academic_year_id.setValue(current);
        }
      },
      error: () => undefined,
    });
    this.academics.classes().subscribe({
      next: (c) => this.classes.set(c),
      error: () => undefined,
    });

    // Fill the fields when a different application is shown, or clear them for a new one.
    effect(() => {
      const a = this.app();
      untracked(() => this.fill(a));
    });
  }

  /** A user picked another branch: the class list follows it, so the old class choice is dropped. */
  protected onBranchChange(): void {
    this.pickedBranch.set(Number(this.form.controls.branch_id.value));
    this.form.controls.class_id.setValue(0);
  }

  protected submit(): void {
    if (this.canPickBranch && !this.app() && this.form.controls.branch_id.value < 1) {
      this.form.controls.branch_id.setErrors({ required: true });
      this.form.controls.branch_id.markAsTouched();
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const body: AdmissionFormValue = {
      first_name: v.first_name.trim(),
      last_name: v.last_name.trim(),
      gender: v.gender || null,
      date_of_birth: v.date_of_birth || null,
      class_id: Number(v.class_id) || null,
      academic_year_id: Number(v.academic_year_id) || null,
      guardian_name: v.guardian_name.trim(),
      guardian_phone: v.guardian_phone.trim(),
      guardian_email: v.guardian_email.trim() || null,
      guardian_relation: v.guardian_relation,
      address: v.address.trim() || null,
      previous_school: v.previous_school.trim() || null,
      notes: v.notes.trim() || null,
    };
    if (!this.app()) {
      body.branch_id = this.canPickBranch ? Number(v.branch_id) : null;
    }
    this.submitted.emit(body);
  }

  private fill(a: AdmissionApp | null): void {
    if (a === null) {
      this.form.reset({
        branch_id: 0,
        first_name: '',
        last_name: '',
        gender: '',
        date_of_birth: '',
        academic_year_id: this.years().find((y) => y.is_current)?.id ?? 0,
        class_id: 0,
        guardian_name: '',
        guardian_phone: '',
        guardian_email: '',
        guardian_relation: 'father',
        address: '',
        previous_school: '',
        notes: '',
      });
      this.pickedBranch.set(0);
      return;
    }
    this.form.reset({
      branch_id: a.branch_id,
      first_name: a.first_name,
      last_name: a.last_name,
      gender: a.gender ?? '',
      date_of_birth: a.date_of_birth ?? '',
      academic_year_id: a.academic_year_id ?? 0,
      class_id: a.class_id ?? 0,
      guardian_name: a.guardian_name,
      guardian_phone: a.guardian_phone,
      guardian_email: a.guardian_email ?? '',
      guardian_relation: a.guardian_relation,
      address: a.address ?? '',
      previous_school: a.previous_school ?? '',
      notes: a.notes ?? '',
    });
  }
}
