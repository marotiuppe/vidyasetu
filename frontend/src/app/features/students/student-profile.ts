import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { NgTemplateOutlet } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { AcademicYear, AcademicsApi, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage, fieldErrorsFrom } from '../../core/api/api-error';
import {
  GENDERS,
  Gender,
  Guardian,
  LoginInput,
  RELATIONS,
  Relation,
  STATUSES,
  StudentDetail,
  StudentStatus,
  StudentsApi,
} from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { USERNAME_HINT, suggestUsername, usernameFormat } from '../../core/auth/identity';
import { PASSWORD_HINT, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../../core/auth/password';
import { canWriteStudents } from '../../core/auth/permissions';
import { StudentAttendance } from '../attendance/student-attendance';
import { PHONE_PATTERN, initials, statusLabel, titleCase, todayIso } from './student-labels';

@Component({
  selector: 'sms-student-profile',
  imports: [ReactiveFormsModule, RouterLink, NgTemplateOutlet, StudentAttendance],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-profile.html',
  styleUrl: './student-profile.css',
})
export class StudentProfile {
  private readonly api = inject(StudentsApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly genders = GENDERS;
  protected readonly relations = RELATIONS;
  protected readonly statuses = STATUSES;
  protected readonly titleCase = titleCase;
  protected readonly statusLabel = statusLabel;
  protected readonly initials = initials;
  protected readonly today = todayIso();
  protected readonly usernameHint = USERNAME_HINT;
  protected readonly canWrite = canWriteStudents(this.auth);

  protected readonly student = signal<StudentDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly busy = signal(false);
  /** Which inline panel is open: 'student', 'guardian-add', 'guardian-edit-<id>', 'guardian-login-<id>', 'enrol', 'login'. */
  protected readonly panel = signal<string | null>(null);
  protected readonly panelError = signal<string | null>(null);

  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);
  private readonly enrolClass = signal(0);

  protected readonly classOptions = computed(() => {
    const branch = this.student()?.branch_id;
    return this.classes().filter((c) => c.branch_id === branch);
  });
  protected readonly sectionOptions = computed(() =>
    this.enrolClass() ? this.sections().filter((s) => s.class_id === this.enrolClass()) : [],
  );

  protected readonly studentForm = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    gender: ['male' as Gender, Validators.required],
    date_of_birth: ['', Validators.required],
    admission_date: ['', Validators.required],
    address: [''],
    previous_school: [''],
    status: ['active' as StudentStatus],
  });
  protected readonly guardianForm = this.fb.group({
    full_name: ['', Validators.required],
    relation: ['father' as Relation, Validators.required],
    phone: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
    email: ['', Validators.email],
    is_primary: [false],
  });
  protected readonly passwordHint = PASSWORD_HINT;
  protected readonly minLength = PASSWORD_MIN_LENGTH;
  protected readonly loginForm = this.fb.group({
    username: ['', [Validators.required, usernameFormat]],
    email: ['', Validators.email],
    password: [
      '',
      [
        Validators.required,
        Validators.minLength(PASSWORD_MIN_LENGTH),
        Validators.maxLength(PASSWORD_MAX_LENGTH),
      ],
    ],
  });
  protected readonly enrolForm = this.fb.group({
    academic_year_id: [0],
    class_id: [0],
    section_id: [0],
    roll_no: [''],
  });

  constructor() {
    if (this.canWrite) {
      this.academics.years().subscribe({ next: (y) => this.years.set(y), error: () => undefined });
      this.academics
        .classes()
        .subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
      this.academics
        .sections()
        .subscribe({ next: (s) => this.sections.set(s), error: () => undefined });
      this.enrolForm.controls.class_id.valueChanges
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe((v) => {
          this.enrolClass.set(Number(v));
          this.enrolForm.controls.section_id.setValue(0);
        });
    }
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((p) => {
      const id = Number(p.get('id'));
      this.panel.set(null);
      this.load(id);
    });
  }

  private load(id: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.get(id).subscribe({
      next: (s) => {
        this.student.set(s);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.student.set(null);
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected closePanel(): void {
    this.panel.set(null);
    this.panelError.set(null);
  }

  // ---- student details -------------------------------------------------

  protected editStudent(s: StudentDetail): void {
    this.studentForm.setValue({
      first_name: s.first_name,
      last_name: s.last_name,
      gender: s.gender,
      date_of_birth: s.date_of_birth,
      admission_date: s.admission_date,
      address: s.address ?? '',
      previous_school: s.previous_school ?? '',
      status: s.status,
    });
    this.open('student');
  }

  protected saveStudent(s: StudentDetail): void {
    if (this.studentForm.invalid) {
      this.studentForm.markAllAsTouched();
      return;
    }
    const v = this.studentForm.getRawValue();
    this.mutate(
      this.api.update(s.id, {
        first_name: v.first_name.trim(),
        last_name: v.last_name.trim(),
        gender: v.gender,
        date_of_birth: v.date_of_birth,
        admission_date: v.admission_date,
        address: v.address.trim() || null,
        previous_school: v.previous_school.trim() || null,
        status: v.status,
      }),
      'Details saved.',
    );
  }

  // ---- guardians -------------------------------------------------------

  protected addGuardian(): void {
    this.guardianForm.reset({ relation: 'father', is_primary: false });
    this.open('guardian-add');
  }

  protected editGuardian(g: Guardian): void {
    this.guardianForm.setValue({
      full_name: g.full_name,
      relation: g.relation,
      phone: g.phone,
      email: g.email ?? '',
      is_primary: g.is_primary,
    });
    this.open(`guardian-edit-${g.id}`);
  }

  protected saveGuardian(s: StudentDetail, g: Guardian | null): void {
    if (this.guardianForm.invalid) {
      this.guardianForm.markAllAsTouched();
      return;
    }
    const v = this.guardianForm.getRawValue();
    const body = {
      full_name: v.full_name.trim(),
      relation: v.relation,
      phone: v.phone.trim(),
      email: v.email.trim() || null,
      is_primary: v.is_primary,
    };
    if (g) this.mutate(this.api.updateGuardian(g.id, body), 'Guardian updated.');
    else this.mutate(this.api.addGuardian(s.id, body), 'Guardian added.');
  }

  protected makePrimary(g: Guardian): void {
    this.mutate(this.api.updateGuardian(g.id, { is_primary: true }), 'Primary guardian changed.');
  }

  protected removeGuardian(g: Guardian): void {
    if (!window.confirm(`Remove ${g.full_name} as a guardian?`)) return;
    this.mutate(this.api.deleteGuardian(g.id), 'Guardian removed.');
  }

  protected startGuardianLogin(g: Guardian): void {
    this.loginForm.reset({
      username: suggestUsername(g.email || g.full_name),
      email: g.email ?? '',
      password: '',
    });
    this.open(`guardian-login-${g.id}`);
  }

  protected saveGuardianLogin(g: Guardian): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }
    const v = this.loginForm.getRawValue();
    this.mutate(
      this.api.createGuardianLogin(g.id, this.loginBody(v)),
      'Parent login created.',
      this.loginForm,
    );
  }

  protected removeGuardianLogin(g: Guardian): void {
    if (!window.confirm(`Remove the login for ${g.full_name}?`)) return;
    this.mutate(this.api.removeGuardianLogin(g.id), 'Login removed.');
  }

  // ---- enrolment -------------------------------------------------------

  protected startEnrol(s: StudentDetail): void {
    const cur = s.current_enrollment;
    const year = cur?.academic_year_id ?? this.years().find((y) => y.is_current)?.id ?? 0;
    this.enrolForm.setValue({
      academic_year_id: year,
      class_id: cur?.class_id ?? 0,
      section_id: 0,
      roll_no: '',
    });
    this.enrolClass.set(cur?.class_id ?? 0);
    this.enrolForm.controls.section_id.setValue(cur?.section_id ?? 0, { emitEvent: false });
    this.open('enrol');
  }

  protected saveEnrol(s: StudentDetail): void {
    const v = this.enrolForm.getRawValue();
    const rollNo = v.roll_no.trim() === '' ? null : Number(v.roll_no);
    if (Number(v.academic_year_id) < 1 || Number(v.class_id) < 1) {
      this.panelError.set('Select an academic year and a class.');
      return;
    }
    if (rollNo !== null && (!Number.isInteger(rollNo) || rollNo < 1)) {
      this.panelError.set('Roll number must be a positive whole number.');
      return;
    }
    this.mutate(
      this.api.setEnrollment(s.id, {
        academic_year_id: Number(v.academic_year_id),
        class_id: Number(v.class_id),
        section_id: Number(v.section_id) || null,
        roll_no: rollNo,
      }),
      'Enrolment saved.',
    );
  }

  // ---- student login ---------------------------------------------------

  protected startStudentLogin(s: StudentDetail): void {
    this.loginForm.reset({
      username: suggestUsername(`${s.first_name} ${s.last_name}`),
      email: '',
      password: '',
    });
    this.open('login');
  }

  protected saveStudentLogin(s: StudentDetail): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }
    const v = this.loginForm.getRawValue();
    this.mutate(
      this.api.createStudentLogin(s.id, this.loginBody(v)),
      'Student login created.',
      this.loginForm,
    );
  }

  // ---- helpers ---------------------------------------------------------

  private loginBody(v: { username: string; email: string; password: string }): LoginInput {
    return {
      username: v.username.trim().toLowerCase(),
      email: v.email.trim() || null,
      password: v.password,
    };
  }

  private open(panel: string): void {
    this.panelError.set(null);
    this.notice.set(null);
    this.panel.set(panel);
  }

  /**
   * Run a write call, then reload the profile so every card shows the saved state.
   * With `form`, 422 messages land on their fields instead of the panel.
   */
  private mutate(request: Observable<unknown>, message: string, form?: FormGroup): void {
    const id = this.student()?.id;
    if (id === undefined) return;
    this.busy.set(true);
    this.panelError.set(null);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.panel.set(null);
        this.loginForm.reset({ username: '', email: '', password: '' });
        this.notice.set(message);
        this.api.get(id).subscribe({
          next: (s) => this.student.set(s),
          error: (err: unknown) => this.error.set(apiErrorMessage(err)),
        });
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(null);
        let placed = false;
        for (const [name, text] of Object.entries(form ? fieldErrorsFrom(err) : {})) {
          const control = form?.get(name);
          if (control) {
            control.setErrors({ server: text });
            control.markAsTouched();
            placed = true;
          }
        }
        this.panelError.set(placed ? null : apiErrorMessage(err));
      },
    });
  }
}
