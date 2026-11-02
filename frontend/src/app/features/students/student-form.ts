import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AcademicYear, AcademicsApi, Branch, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { GENDERS, NewStudent, RELATIONS, Relation } from '../../core/api/students.api';
import { StudentsApi } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { PHONE_PATTERN, titleCase, todayIso } from './student-labels';

function notFuture(control: AbstractControl<string>): ValidationErrors | null {
  const v = control.value;
  return v && v > todayIso() ? { future: true } : null;
}

@Component({
  selector: 'sms-student-form',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-form.html',
  styleUrl: './student-form.css',
})
export class StudentForm {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly api = inject(StudentsApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly genders = GENDERS;
  protected readonly relations = RELATIONS;
  protected readonly titleCase = titleCase;
  protected readonly today = todayIso();
  protected readonly needsBranch = this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group({
    branch_id: [0],
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    gender: ['male' as (typeof GENDERS)[number], Validators.required],
    date_of_birth: ['', [Validators.required, notFuture]],
    admission_date: [todayIso(), [Validators.required]],
    admission_no: [''],
    address: [''],
    previous_school: [''],
    guardians: this.fb.array([this.newGuardian(true)]),
    academic_year_id: [0],
    class_id: [0],
    section_id: [0],
    roll_no: [''],
  });

  private readonly branchValue = toSignal(this.form.controls.branch_id.valueChanges, {
    initialValue: 0,
  });
  private readonly classValue = toSignal(this.form.controls.class_id.valueChanges, { initialValue: 0 });

  protected readonly classOptions = computed(() => {
    const b = this.needsBranch ? Number(this.branchValue()) : (this.auth.user()?.branch_id ?? 0);
    return b ? this.classes().filter((c) => c.branch_id === b) : this.needsBranch ? [] : this.classes();
  });
  protected readonly sectionOptions = computed(() => {
    const c = Number(this.classValue());
    return c ? this.sections().filter((s) => s.class_id === c) : [];
  });

  constructor() {
    if (this.needsBranch) {
      this.academics.branches().subscribe({
        next: (b) => this.branches.set(b),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
    }
    this.academics.years().subscribe({
      next: (y) => {
        this.years.set(y);
        this.form.controls.academic_year_id.setValue(y.find((v) => v.is_current)?.id ?? 0);
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
    this.academics.classes().subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
    this.academics.sections().subscribe({ next: (s) => this.sections.set(s), error: () => undefined });

    this.form.controls.branch_id.valueChanges.subscribe(() => {
      this.form.controls.class_id.setValue(0);
    });
    this.form.controls.class_id.valueChanges.subscribe(() => {
      this.form.controls.section_id.setValue(0);
    });
  }

  protected get guardians() {
    return this.form.controls.guardians;
  }

  private newGuardian(primary: boolean) {
    return this.fb.group({
      full_name: ['', [Validators.required, Validators.maxLength(150)]],
      relation: ['father' as Relation, Validators.required],
      phone: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
      email: ['', Validators.email],
      is_primary: [primary],
    });
  }

  protected addGuardian(): void {
    this.guardians.push(this.newGuardian(false));
  }

  protected removeGuardian(index: number): void {
    if (this.guardians.length <= 1) return;
    const wasPrimary = this.guardians.at(index).controls.is_primary.value;
    this.guardians.removeAt(index);
    if (wasPrimary) this.setPrimary(0);
  }

  protected setPrimary(index: number): void {
    this.guardians.controls.forEach((g, i) => g.controls.is_primary.setValue(i === index));
  }

  protected submit(): void {
    this.error.set(null);
    const v = this.form.getRawValue();
    if (this.needsBranch && Number(v.branch_id) < 1) {
      this.form.controls.branch_id.markAsTouched();
    }
    if (this.form.invalid || (this.needsBranch && Number(v.branch_id) < 1)) {
      this.form.markAllAsTouched();
      this.error.set('Please correct the highlighted fields.');
      return;
    }
    const rollNo = v.roll_no.trim() === '' ? null : Number(v.roll_no);
    if (rollNo !== null && (!Number.isInteger(rollNo) || rollNo < 1)) {
      this.error.set('Roll number must be a positive whole number.');
      return;
    }
    const enrolling = Number(v.class_id) > 0;
    if (enrolling && Number(v.academic_year_id) < 1) {
      this.error.set('Select an academic year for the enrolment.');
      return;
    }

    const body: NewStudent = {
      branch_id: this.needsBranch ? Number(v.branch_id) : null,
      first_name: v.first_name.trim(),
      last_name: v.last_name.trim(),
      gender: v.gender,
      date_of_birth: v.date_of_birth,
      admission_date: v.admission_date || null,
      admission_no: v.admission_no.trim() || null,
      address: v.address.trim() || null,
      previous_school: v.previous_school.trim() || null,
      guardians: v.guardians.map((g) => ({
        full_name: g.full_name.trim(),
        relation: g.relation,
        phone: g.phone.trim(),
        email: g.email.trim() || null,
        is_primary: g.is_primary,
      })),
      enrollment: enrolling
        ? {
            academic_year_id: Number(v.academic_year_id),
            class_id: Number(v.class_id),
            section_id: Number(v.section_id) || null,
            roll_no: rollNo,
          }
        : null,
    };

    this.submitting.set(true);
    this.api.create(body).subscribe({
      next: (student) => {
        void this.router.navigate(['/students', student.id]);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
