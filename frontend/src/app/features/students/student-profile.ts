import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { NgTemplateOutlet } from '@angular/common';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { Observable, filter } from 'rxjs';

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
import { suggestUsername, usernameFormat } from '../../core/auth/identity';
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../../core/auth/password';
import { canWriteStudents } from '../../core/auth/permissions';
import { CREATE_NEW, CreateKind, canCreateRecord } from '../../core/create/create-new';
import { PendingReturn, ReturnStateService } from '../../core/create/return-state.service';
import { I18n } from '../../core/i18n/i18n';
import { StudentAttendance } from '../attendance/student-attendance';
import { StudentConsent } from './student-consent';
import { PHONE_PATTERN, initials, statusKey, todayIso } from './student-labels';

@Component({
  selector: 'sms-student-profile',
  imports: [ReactiveFormsModule, RouterLink, NgTemplateOutlet, StudentAttendance, StudentConsent],
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
  private readonly router = inject(Router);
  private readonly returnState = inject(ReturnStateService);
  protected readonly i18n = inject(I18n);

  protected readonly genders = GENDERS;
  protected readonly relations = RELATIONS;
  protected readonly statuses = STATUSES;
  protected readonly initials = initials;
  protected readonly today = todayIso();
  protected readonly canWrite = canWriteStudents(this.auth);
  /** Students see their own profile but consent is a matter for parents and the school. */
  protected readonly isStudentLogin = this.auth.hasRole('student');
  protected readonly createNew = CREATE_NEW;
  protected readonly canCreateYear = canCreateRecord(this.auth, 'academic_year');
  protected readonly canCreateClass = canCreateRecord(this.auth, 'class');
  protected readonly canCreateSection = canCreateRecord(this.auth, 'section');
  /** Set when this page is back from a create screen; applied once the student has loaded. */
  private pendingBack: PendingReturn | null = null;

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
    this.pendingBack = this.returnState.take(this.router.url);
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
      this.watchCreate(this.enrolForm.controls.academic_year_id, 'academic_year');
      this.watchCreate(this.enrolForm.controls.class_id, 'class');
      this.watchCreate(this.enrolForm.controls.section_id, 'section');
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
        const back = this.pendingBack;
        this.pendingBack = null;
        if (back) this.restoreEnrol(back);
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

  protected statusText(status: StudentStatus): string {
    return this.i18n.t(statusKey(status));
  }

  /** Gender or relation value shown as a label, e.g. male -> Male. */
  protected enumText(group: 'gender' | 'relation', value: string): string {
    return this.i18n.t(`students.list.${group}.${value}`);
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
      this.i18n.t('students.list.notice.detailsSaved'),
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
    if (g)
      this.mutate(
        this.api.updateGuardian(g.id, body),
        this.i18n.t('students.list.notice.guardianUpdated'),
      );
    else
      this.mutate(
        this.api.addGuardian(s.id, body),
        this.i18n.t('students.list.notice.guardianAdded'),
      );
  }

  protected makePrimary(g: Guardian): void {
    this.mutate(
      this.api.updateGuardian(g.id, { is_primary: true }),
      this.i18n.t('students.list.notice.primaryChanged'),
    );
  }

  protected removeGuardian(g: Guardian): void {
    if (!window.confirm(this.i18n.t('students.list.confirm.removeGuardian', { name: g.full_name })))
      return;
    this.mutate(this.api.deleteGuardian(g.id), this.i18n.t('students.list.notice.guardianRemoved'));
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
      this.i18n.t('students.list.notice.parentLoginCreated'),
      this.loginForm,
    );
  }

  protected removeGuardianLogin(g: Guardian): void {
    if (!window.confirm(this.i18n.t('students.list.confirm.removeLogin', { name: g.full_name })))
      return;
    this.mutate(
      this.api.removeGuardianLogin(g.id),
      this.i18n.t('students.list.notice.loginRemoved'),
    );
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
      this.panelError.set(this.i18n.t('students.list.error.selectYearClass'));
      return;
    }
    if (rollNo !== null && (!Number.isInteger(rollNo) || rollNo < 1)) {
      this.panelError.set(this.i18n.t('students.list.error.roll'));
      return;
    }
    this.mutate(
      this.api.setEnrollment(s.id, {
        academic_year_id: Number(v.academic_year_id),
        class_id: Number(v.class_id),
        section_id: Number(v.section_id) || null,
        roll_no: rollNo,
      }),
      this.i18n.t('students.list.notice.enrolmentSaved'),
    );
  }

  /** "+ Create new..." in the enrolment panel: keep the panel values and open the create screen. */
  private watchCreate(control: FormControl<number>, kind: CreateKind): void {
    control.valueChanges
      .pipe(
        filter((v) => v === CREATE_NEW),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        const extra: Params = {};
        const cls = Number(this.enrolForm.controls.class_id.value);
        if (kind === 'section' && cls > 0) extra['classId'] = cls;
        this.returnState.openCreate(
          kind,
          this.enrolForm.getRawValue(),
          this.i18n.t('students.list.from.profile'),
          extra,
        );
      });
  }

  /** Re-open the enrolment panel with the values kept before the create screen, and the new record selected. */
  private restoreEnrol(back: PendingReturn): void {
    const draft = back.draft as {
      academic_year_id: number;
      class_id: number;
      section_id: number;
      roll_no: string;
    } | null;
    const keep = (v: number | undefined): number => (v && v > 0 ? v : 0);
    const picked = back.createdId ?? 0;
    const year = back.kind === 'academic_year' ? picked : keep(draft?.academic_year_id);
    const cls = back.kind === 'class' ? picked : keep(draft?.class_id);
    const section =
      back.kind === 'section' ? picked : back.kind === 'class' ? 0 : keep(draft?.section_id);
    this.enrolForm.controls.academic_year_id.setValue(year);
    this.enrolForm.controls.class_id.setValue(cls);
    this.enrolForm.controls.section_id.setValue(section);
    this.enrolForm.controls.roll_no.setValue(draft?.roll_no ?? '');
    this.enrolClass.set(cls);
    this.open('enrol');
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
      this.i18n.t('students.list.notice.studentLoginCreated'),
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
