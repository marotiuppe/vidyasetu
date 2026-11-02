import {
  DestroyRef,
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { catchError, debounceTime, of, startWith, switchMap, tap } from 'rxjs';

import { AdminApi, Branch, School } from '../../core/api/admin.api';
import { apiErrorMessage, fieldErrorsFrom } from '../../core/api/api-error';
import { Role, User } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { MOBILE_HINT, USERNAME_HINT, mobileFormat, usernameFormat } from '../../core/auth/identity';
import { ROLE_LABELS } from '../../core/layout/nav';

const BRANCH_BOUND: Role[] = [
  'management',
  'headmaster',
  'teacher',
  'accountant',
  'clerk',
  'student',
];
const ALL_ROLES = Object.keys(ROLE_LABELS) as Role[];
const BRANCH_LEVEL_CREATORS: Role[] = ['teacher', 'accountant', 'clerk', 'student', 'parent'];

@Component({
  selector: 'sms-users',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './users.html',
  styleUrl: './users.css',
})
export class Users {
  private readonly api = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly roleLabels = ROLE_LABELS;
  protected readonly allRoles = ALL_ROLES;
  protected readonly usernameHint = USERNAME_HINT;
  protected readonly mobileHint = MOBILE_HINT;

  protected readonly users = signal<User[]>([]);
  protected readonly branches = signal<Branch[]>([]);
  protected readonly schools = signal<School[]>([]);
  protected readonly loading = signal(true);
  protected readonly submitting = signal(false);
  protected readonly showForm = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly editError = signal<string | null>(null);
  protected readonly editingId = signal<number | null>(null);
  protected readonly resettingId = signal<number | null>(null);
  protected readonly busyId = signal<number | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly selectedRole = signal<Role>('teacher');
  protected readonly selectedSchool = signal(0);

  private readonly me = computed(() => this.auth.user());
  protected readonly isSuperAdmin = computed(() => this.me()?.role === 'super_admin');

  /** Roles the signed-in user may create (UX only; the backend enforces it). */
  protected readonly creatableRoles = computed<Role[]>(() => {
    switch (this.me()?.role) {
      case 'super_admin':
        return ALL_ROLES;
      case 'school_owner':
        return ALL_ROLES.filter((r) => r !== 'super_admin');
      case 'management':
      case 'headmaster':
        return ALL_ROLES.filter((r) => BRANCH_LEVEL_CREATORS.includes(r));
      default:
        return [];
    }
  });

  protected readonly needsSchool = computed(
    () => this.isSuperAdmin() && this.selectedRole() !== 'super_admin',
  );
  // A branch is picked only for branch-bound roles by users not tied to one branch.
  protected readonly needsBranch = computed(
    () => this.me()?.branch_id == null && BRANCH_BOUND.includes(this.selectedRole()),
  );
  protected readonly branchOptions = computed(() => {
    const school = this.selectedSchool();
    return this.isSuperAdmin()
      ? this.branches().filter((b) => b.school_id === school)
      : this.branches();
  });

  protected readonly filters = this.fb.group({ q: [''], role: ['' as Role | ''] });
  protected readonly form = this.fb.group({
    role: ['teacher' as Role, Validators.required],
    school_id: [0],
    branch_id: [0],
    full_name: ['', Validators.required],
    username: ['', [Validators.required, usernameFormat]],
    email: ['', Validators.email],
    phone: ['', mobileFormat],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });
  protected readonly editForm = this.fb.group({
    full_name: ['', Validators.required],
    email: ['', Validators.email],
    phone: ['', mobileFormat],
    is_active: [true],
  });
  protected readonly resetControl = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(8)],
  });

  constructor() {
    this.api.branches().subscribe({
      next: (b) => this.branches.set(b),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
    if (this.isSuperAdmin()) {
      this.api.schools().subscribe({
        next: (s) => this.schools.set(s),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
    }

    this.form.controls.role.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((r) => this.selectedRole.set(r));
    this.form.controls.school_id.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((id) => {
        this.selectedSchool.set(Number(id));
        this.form.controls.branch_id.setValue(0);
      });
    const roles = this.creatableRoles();
    const first = roles.includes('teacher') ? 'teacher' : roles[0];
    if (first) {
      this.form.controls.role.setValue(first);
    }

    this.filters.valueChanges
      .pipe(
        startWith(this.filters.getRawValue()),
        debounceTime(300),
        tap(() => this.loading.set(true)),
        switchMap(() =>
          this.api.users(this.filters.getRawValue()).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((list) => {
        if (list) {
          this.users.set(list);
        }
        this.loading.set(false);
      });
  }

  /** Show a field as invalid only after the user has touched or changed it. */
  protected bad(control: AbstractControl): boolean {
    return control.invalid && (control.dirty || control.touched);
  }

  protected branchName(id: number | null): string {
    if (id == null) return 'All branches';
    return this.branches().find((b) => b.id === id)?.name ?? `Branch #${id}`;
  }

  protected toggleForm(): void {
    this.showForm.update((v) => !v);
    this.formError.set(null);
  }

  protected create(): void {
    const v = this.form.getRawValue();
    this.formError.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.needsSchool() && Number(v.school_id) < 1) {
      this.formError.set('Select a school.');
      return;
    }
    if (this.needsBranch() && Number(v.branch_id) < 1) {
      this.formError.set('Select a branch for this role.');
      return;
    }
    this.submitting.set(true);
    this.api
      .createUser({
        username: v.username.trim().toLowerCase(),
        email: v.email.trim() || null,
        full_name: v.full_name.trim(),
        phone: v.phone.trim() || null,
        password: v.password,
        role: v.role,
        school_id: this.needsSchool() ? Number(v.school_id) : null,
        branch_id: this.needsBranch() ? Number(v.branch_id) : null,
      })
      .subscribe({
        next: (user) => {
          this.submitting.set(false);
          this.form.patchValue({ full_name: '', username: '', email: '', phone: '', password: '' });
          this.form.markAsUntouched();
          this.showForm.set(false);
          this.notice.set(`Created ${user.full_name} (${user.username}).`);
          this.reload();
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.formError.set(this.placeErrors(this.form, err));
        },
      });
  }

  protected startEdit(user: User): void {
    this.resettingId.set(null);
    this.editError.set(null);
    this.editForm.setValue({
      full_name: user.full_name,
      email: user.email ?? '',
      phone: user.phone ?? '',
      is_active: user.is_active,
    });
    this.editingId.set(user.id);
  }

  protected saveEdit(user: User): void {
    if (this.editForm.invalid) {
      this.editForm.markAllAsTouched();
      return;
    }
    const v = this.editForm.getRawValue();
    this.editError.set(null);
    this.run(
      user.id,
      this.api.updateUser(user.id, {
        full_name: v.full_name.trim(),
        email: v.email.trim() || null,
        phone: v.phone.trim() || null,
        is_active: v.is_active,
      }),
      () => {
        this.editingId.set(null);
        this.notice.set('User updated.');
      },
      (err) => this.editError.set(this.placeErrors(this.editForm, err)),
    );
  }

  protected startReset(user: User): void {
    this.editingId.set(null);
    this.resetControl.reset('');
    this.resettingId.set(user.id);
  }

  protected saveReset(user: User): void {
    if (this.resetControl.invalid) {
      this.resetControl.markAsTouched();
      return;
    }
    this.run(user.id, this.api.resetPassword(user.id, this.resetControl.value), () => {
      this.resetControl.reset('');
      this.resettingId.set(null);
      this.notice.set(`Password reset for ${user.full_name}.`);
    });
  }

  protected closePanels(): void {
    this.editingId.set(null);
    this.resettingId.set(null);
  }

  /**
   * Put 422 messages on their fields. Returns the message to show next to the form
   * (for example a 409 duplicate), or null when every problem sits on a field.
   */
  private placeErrors(form: { get(name: string): unknown }, err: unknown): string | null {
    let placed = false;
    for (const [name, message] of Object.entries(fieldErrorsFrom(err))) {
      const control = form.get(name);
      if (control instanceof FormControl) {
        control.setErrors({ server: message });
        control.markAsTouched();
        placed = true;
      }
    }
    return placed ? null : apiErrorMessage(err);
  }

  private run(
    id: number,
    request: { subscribe: (o: { next: () => void; error: (e: unknown) => void }) => unknown },
    onDone: () => void,
    onError: (err: unknown) => void = (err) => this.error.set(apiErrorMessage(err)),
  ): void {
    this.busyId.set(id);
    this.error.set(null);
    this.notice.set(null);
    request.subscribe({
      next: () => {
        this.busyId.set(null);
        onDone();
        this.reload();
      },
      error: (err: unknown) => {
        this.busyId.set(null);
        onError(err);
      },
    });
  }

  private reload(): void {
    this.filters.updateValueAndValidity();
  }
}
