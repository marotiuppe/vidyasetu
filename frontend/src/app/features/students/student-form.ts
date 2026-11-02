import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Params, Router, RouterLink } from '@angular/router';
import { filter } from 'rxjs';

import {
  AcademicYear,
  AcademicsApi,
  Branch,
  SchoolClass,
  Section,
} from '../../core/api/academics.api';
import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import {
  GENDERS,
  Gender,
  GuardianInput,
  NewStudent,
  ParentSummary,
  RELATIONS,
  Relation,
  StudentCredential,
  StudentsApi,
} from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import {
  CREATE_NEW,
  CREATE_NEW_LABEL,
  CreateKind,
  canCreateRecord,
} from '../../core/create/create-new';
import { PendingReturn, ReturnStateService } from '../../core/create/return-state.service';
import { LoginDetails } from './login-details';
import { ParentPicker } from './parent-picker';
import { PHONE_PATTERN, titleCase, todayIso } from './student-labels';

function notFuture(control: AbstractControl<string>): ValidationErrors | null {
  const v = control.value;
  return v && v > todayIso() ? { future: true } : null;
}

type ParentMode = 'new' | 'existing';

/** Values kept while the user creates a lookup record elsewhere (in memory only). */
interface GuardianDraft {
  parent_mode: ParentMode;
  existing_parent_user_id: number;
  full_name: string;
  relation: Relation;
  phone: string;
  email: string;
  is_primary: boolean;
  create_login: boolean;
}

interface StudentDraft {
  branch_id: number;
  first_name: string;
  last_name: string;
  gender: Gender;
  date_of_birth: string;
  admission_date: string;
  admission_no: string;
  address: string;
  previous_school: string;
  guardians: GuardianDraft[];
  create_student_login: boolean;
  academic_year_id: number;
  class_id: number;
  section_id: number;
  roll_no: string;
}

/** Ids from a draft: anything that is not a real id (for example the "Create new..." marker) becomes 0. */
function keepId(value: number | undefined): number {
  return value && value > 0 ? value : 0;
}

@Component({
  selector: 'sms-student-form',
  imports: [ReactiveFormsModule, RouterLink, ParentPicker, LoginDetails],
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
  private readonly returnState = inject(ReturnStateService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly genders = GENDERS;
  protected readonly relations = RELATIONS;
  protected readonly titleCase = titleCase;
  protected readonly today = todayIso();
  protected readonly needsBranch = this.auth.user()?.branch_id == null;
  protected readonly createNew = CREATE_NEW;
  protected readonly createNewLabel = CREATE_NEW_LABEL;
  protected readonly canCreateYear = canCreateRecord(this.auth, 'academic_year');
  protected readonly canCreateClass = canCreateRecord(this.auth, 'class');
  protected readonly canCreateSection = canCreateRecord(this.auth, 'section');
  protected readonly canCreateBranch = canCreateRecord(this.auth, 'branch');

  /** Set when the user came back from a create screen: the default year must not overwrite the draft. */
  private readonly returning: boolean;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Logins created with the student. Held only here: shown once, never stored, logged or put in a URL. */
  protected readonly credentials = signal<StudentCredential[] | null>(null);
  private readonly createdId = signal<number | null>(null);

  protected readonly form = this.fb.group({
    branch_id: [0],
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    gender: ['male' as Gender, Validators.required],
    date_of_birth: ['', [Validators.required, notFuture]],
    admission_date: [todayIso(), [Validators.required]],
    admission_no: [''],
    address: [''],
    previous_school: [''],
    guardians: this.fb.array([this.newGuardian(true)]),
    create_student_login: [true],
    academic_year_id: [0],
    class_id: [0],
    section_id: [0],
    roll_no: [''],
  });

  private readonly branchValue = toSignal(this.form.controls.branch_id.valueChanges, {
    initialValue: 0,
  });
  private readonly classValue = toSignal(this.form.controls.class_id.valueChanges, {
    initialValue: 0,
  });

  protected readonly classOptions = computed(() => {
    const b = this.needsBranch ? Number(this.branchValue()) : (this.auth.user()?.branch_id ?? 0);
    return b
      ? this.classes().filter((c) => c.branch_id === b)
      : this.needsBranch
        ? []
        : this.classes();
  });
  protected readonly sectionOptions = computed(() => {
    const c = Number(this.classValue());
    return c > 0 ? this.sections().filter((s) => s.class_id === c) : [];
  });

  constructor() {
    const back = this.returnState.take(this.router.url);
    this.returning = back !== null;

    if (this.needsBranch) {
      this.academics.branches().subscribe({
        next: (b) => this.branches.set(b),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
    }
    this.academics.years().subscribe({
      next: (y) => {
        this.years.set(y);
        if (!this.returning) {
          this.form.controls.academic_year_id.setValue(y.find((v) => v.is_current)?.id ?? 0);
        }
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
    this.academics
      .classes()
      .subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
    this.academics
      .sections()
      .subscribe({ next: (s) => this.sections.set(s), error: () => undefined });

    this.form.controls.branch_id.valueChanges.subscribe(() => {
      this.form.controls.class_id.setValue(0);
    });
    this.form.controls.class_id.valueChanges.subscribe(() => {
      this.form.controls.section_id.setValue(0);
    });

    // "+ Create new..." on a lookup: keep this form's draft and open the create screen.
    this.watchCreate(this.form.controls.academic_year_id, 'academic_year');
    this.watchCreate(this.form.controls.branch_id, 'branch');
    this.watchCreate(this.form.controls.class_id, 'class');
    this.watchCreate(this.form.controls.section_id, 'section');

    this.destroyRef.onDestroy(() => this.credentials.set(null));
    if (back) this.restore(back);
  }

  protected get guardians() {
    return this.form.controls.guardians;
  }

  private newGuardian(primary: boolean) {
    return this.fb.group({
      parent_mode: ['new' as ParentMode],
      existing_parent_user_id: [0],
      full_name: ['', [Validators.required, Validators.maxLength(150)]],
      relation: ['father' as Relation, Validators.required],
      phone: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
      email: ['', Validators.email],
      is_primary: [primary],
      create_login: [primary],
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
    this.guardians.controls.forEach((g, i) => {
      g.controls.is_primary.setValue(i === index);
      // A login is created by default for the primary guardian only; the user can still change it.
      g.controls.create_login.setValue(i === index);
    });
  }

  /** The user switched between "New parent" and "Existing parent" for one guardian. */
  protected onModeChange(index: number, event: Event): void {
    const mode: ParentMode =
      (event.target as HTMLInputElement).value === 'existing' ? 'existing' : 'new';
    const g = this.guardians.at(index);
    g.controls.parent_mode.setValue(mode);
    g.controls.existing_parent_user_id.setValue(0);
    if (mode === 'existing') {
      g.patchValue({ full_name: '', phone: '', email: '', create_login: false });
    } else {
      g.controls.create_login.setValue(g.controls.is_primary.value);
    }
  }

  /** Fill name and mobile from the parent chosen in the search (siblings share that login). */
  protected pickParent(index: number, parent: ParentSummary): void {
    this.guardians.at(index).patchValue({
      existing_parent_user_id: parent.id,
      full_name: parent.full_name,
      phone: parent.phone ?? '',
    });
  }

  /** Text for a field error: the server's message when there is one, else the local one. */
  protected fieldError(control: AbstractControl, fallback: string): string {
    const server = control.getError('server');
    return typeof server === 'string' ? server : fallback;
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
    const missing = v.guardians.findIndex(
      (g) => g.parent_mode === 'existing' && Number(g.existing_parent_user_id) < 1,
    );
    if (missing >= 0) {
      this.error.set(
        `Search for and select the existing parent of guardian ${missing + 1}, or choose New parent.`,
      );
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
      guardians: v.guardians.map((g): GuardianInput => {
        const base = {
          full_name: g.full_name.trim(),
          relation: g.relation,
          phone: g.phone.trim(),
          is_primary: g.is_primary,
        };
        return g.parent_mode === 'existing'
          ? { ...base, email: null, existing_parent_user_id: Number(g.existing_parent_user_id) }
          : { ...base, email: g.email.trim() || null, create_login: g.create_login };
      }),
      enrollment: enrolling
        ? {
            academic_year_id: Number(v.academic_year_id),
            class_id: Number(v.class_id),
            section_id: Number(v.section_id) || null,
            roll_no: rollNo,
          }
        : null,
      create_student_login: v.create_student_login,
    };

    this.submitting.set(true);
    this.api.create(body).subscribe({
      next: (student) => {
        this.submitting.set(false);
        const logins = student.credentials ?? [];
        if (logins.length > 0) {
          this.createdId.set(student.id);
          this.credentials.set(logins);
          return;
        }
        void this.router.navigate(['/students', student.id]);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(
          placeServerErrors(this.form, err) ?? 'Please correct the highlighted fields.',
        );
      },
    });
  }

  /** The one-time login panel is closed: drop the credentials and open the new student's profile. */
  protected done(): void {
    const id = this.createdId();
    this.credentials.set(null);
    this.createdId.set(null);
    if (id !== null) void this.router.navigate(['/students', id]);
  }

  private watchCreate(control: FormControl<number>, kind: CreateKind): void {
    control.valueChanges
      .pipe(
        filter((v) => v === CREATE_NEW),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.createRecord(kind));
  }

  private createRecord(kind: CreateKind): void {
    const extra: Params = {};
    if (kind === 'section') extra['classId'] = keepId(this.form.controls.class_id.value);
    const branchId = keepId(this.form.controls.branch_id.value);
    if (kind === 'class' && branchId > 0) extra['branchId'] = branchId;
    this.returnState.openCreate(kind, this.form.getRawValue(), 'New admission', extra);
  }

  /** Put back the draft and the record the user created (or nothing, after a cancel). */
  private restore(back: PendingReturn): void {
    const draft = back.draft as StudentDraft | null;
    const picked = back.createdId;
    if (draft) {
      const { guardians, branch_id, academic_year_id, class_id, section_id, ...scalars } = draft;
      this.guardians.clear();
      guardians.forEach(() => this.guardians.push(this.newGuardian(false)));
      this.guardians.patchValue(guardians);
      this.form.patchValue(scalars);
    }
    // Order matters: changing the branch clears the class, and changing the class clears the section.
    const kind = back.kind;
    this.form.controls.branch_id.setValue(
      kind === 'branch' ? (picked ?? 0) : keepId(draft?.branch_id),
    );
    this.form.controls.academic_year_id.setValue(
      kind === 'academic_year' ? (picked ?? 0) : keepId(draft?.academic_year_id),
    );
    this.form.controls.class_id.setValue(
      kind === 'class' ? (picked ?? 0) : kind === 'branch' ? 0 : keepId(draft?.class_id),
    );
    this.form.controls.section_id.setValue(
      kind === 'section'
        ? (picked ?? 0)
        : kind === 'class' || kind === 'branch'
          ? 0
          : keepId(draft?.section_id),
    );
  }
}
