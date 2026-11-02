import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AdminApi, Branch, School } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { safeReturnUrl } from '../../core/create/create-new';
import { ReturnStateService } from '../../core/create/return-state.service';

@Component({
  selector: 'sms-branches',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './branches.html',
  styleUrl: './branches.css',
})
export class Branches {
  private readonly api = inject(AdminApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly returnState = inject(ReturnStateService);

  /** Set when a form elsewhere sent the user here to create a branch; the page returns there after saving. */
  protected readonly returnTo: string | null;
  protected readonly from: string;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly schools = signal<School[]>([]);
  protected readonly loading = signal(true);
  protected readonly submitting = signal(false);
  protected readonly showForm = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly editingId = signal<number | null>(null);
  protected readonly busyId = signal<number | null>(null);

  protected readonly isSuperAdmin = computed(() => this.auth.hasRole('super_admin'));

  protected readonly form = this.fb.group({
    school_id: [0],
    name: ['', Validators.required],
    code: ['', [Validators.required, Validators.pattern(/^[a-z0-9_-]+$/)]],
  });
  protected readonly renameControl = new FormControl('', {
    nonNullable: true,
    validators: Validators.required,
  });

  constructor() {
    const params = this.route.snapshot.queryParamMap;
    this.returnTo =
      params.get('create') === 'branch' ? safeReturnUrl(params.get('returnTo')) : null;
    this.from = params.get('from')?.trim() || 'your previous page';
    if (this.returnTo) this.showForm.set(true);

    if (this.isSuperAdmin()) {
      this.api.schools().subscribe({
        next: (s) => this.schools.set(s),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
    }
    this.load();
  }

  /** Leave without saving: the form that asked for the branch comes back with nothing selected. */
  protected cancelCreate(): void {
    if (this.returnTo) this.returnState.cancel(this.returnTo, 'branch');
  }

  protected schoolName(id: number): string {
    return this.schools().find((s) => s.id === id)?.name ?? `School #${id}`;
  }

  protected toggleForm(): void {
    this.showForm.update((v) => !v);
    this.formError.set(null);
  }

  protected create(): void {
    const { school_id, name, code } = this.form.getRawValue();
    const needsSchool = this.isSuperAdmin();
    if (this.form.invalid || (needsSchool && school_id < 1)) {
      this.form.markAllAsTouched();
      this.formError.set(needsSchool && school_id < 1 ? 'Select a school.' : null);
      return;
    }
    this.submitting.set(true);
    this.formError.set(null);
    this.api.createBranch({ name, code, school_id: needsSchool ? school_id : null }).subscribe({
      next: (created) => {
        this.submitting.set(false);
        this.form.reset();
        if (this.returnTo) {
          this.returnState.finish(this.returnTo, 'branch', created.id);
          return;
        }
        this.showForm.set(false);
        this.load();
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.formError.set(apiErrorMessage(err));
      },
    });
  }

  protected startRename(branch: Branch): void {
    this.renameControl.setValue(branch.name);
    this.editingId.set(branch.id);
  }

  protected cancelRename(): void {
    this.editingId.set(null);
  }

  protected saveRename(branch: Branch): void {
    const name = this.renameControl.value.trim();
    if (!name) return;
    this.update(branch.id, { name });
  }

  protected toggleActive(branch: Branch): void {
    this.update(branch.id, { is_active: !branch.is_active });
  }

  private update(id: number, body: { name?: string; is_active?: boolean }): void {
    this.busyId.set(id);
    this.error.set(null);
    this.api.updateBranch(id, body).subscribe({
      next: () => {
        this.busyId.set(null);
        this.editingId.set(null);
        this.load();
      },
      error: (err: unknown) => {
        this.busyId.set(null);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private load(): void {
    this.api.branches().subscribe({
      next: (b) => {
        this.branches.set(b);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
