import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import {
  AcademicYear,
  AcademicsApi,
  Branch,
  SchoolClass,
  Section,
} from '../../core/api/academics.api';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'sms-setup',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './setup.html',
  styleUrl: './setup.css',
})
export class Setup {
  private readonly api = inject(AcademicsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);

  protected readonly years = signal<AcademicYear[]>([]);
  protected readonly branches = signal<Branch[]>([]);
  protected readonly classes = signal<SchoolClass[]>([]);
  protected readonly sections = signal<Section[]>([]);
  protected readonly error = signal<string | null>(null);

  protected readonly canManageYears = computed(() => this.auth.hasRole('school_owner'));
  // Users tied to one branch do not need to pick a branch.
  protected readonly needsBranch = computed(() => this.auth.user()?.branch_id == null);

  protected readonly yearForm = this.fb.group({
    name: ['', Validators.required],
    start_date: ['', Validators.required],
    end_date: ['', Validators.required],
    is_current: [false],
  });
  protected readonly classForm = this.fb.group({
    name: ['', Validators.required],
    level: [1, [Validators.required, Validators.min(1), Validators.max(12)]],
    branch_id: [0],
  });
  protected readonly sectionForm = this.fb.group({
    class_id: [0, Validators.min(1)],
    name: ['', Validators.required],
  });

  constructor() {
    this.reload();
  }

  protected branchName(id: number): string {
    return this.branches().find((b) => b.id === id)?.name ?? `#${id}`;
  }

  protected className(id: number): string {
    return this.classes().find((c) => c.id === id)?.name ?? `#${id}`;
  }

  protected sectionsOf(classId: number): Section[] {
    return this.sections().filter((s) => s.class_id === classId);
  }

  protected addYear(): void {
    if (this.yearForm.invalid) return;
    this.run(this.api.createYear(this.yearForm.getRawValue()), () => this.yearForm.reset());
  }

  protected makeCurrent(id: number): void {
    this.run(this.api.makeYearCurrent(id));
  }

  protected addClass(): void {
    if (this.classForm.invalid) return;
    const { name, level, branch_id } = this.classForm.getRawValue();
    this.run(this.api.createClass({ name, level, branch_id: this.needsBranch() ? branch_id : null }));
  }

  protected addSection(): void {
    if (this.sectionForm.invalid) return;
    this.run(this.api.createSection(this.sectionForm.getRawValue()), () =>
      this.sectionForm.controls.name.reset(),
    );
  }

  private run(request: { subscribe: (o: object) => unknown }, onDone?: () => void): void {
    this.error.set(null);
    request.subscribe({
      next: () => {
        onDone?.();
        this.reload();
      },
      error: (err: unknown) => this.error.set(this.message(err)),
    });
  }

  private reload(): void {
    this.api.branches().subscribe((b) => this.branches.set(b));
    this.api.years().subscribe((y) => this.years.set(y));
    this.api.classes().subscribe((c) => this.classes.set(c));
    this.api.sections().subscribe((s) => this.sections.set(s));
  }

  private message(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      const detail: unknown = err.error?.detail;
      if (typeof detail === 'string') return detail;
      if (err.status === 403) return 'You are not allowed to do this.';
    }
    return 'Something went wrong. Please try again.';
  }
}
