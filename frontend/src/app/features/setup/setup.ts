import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';

import {
  AcademicYear,
  AcademicsApi,
  Branch,
  SchoolClass,
  Section,
} from '../../core/api/academics.api';
import { AuthService } from '../../core/auth/auth.service';
import { CREATE_LABELS, CreateKind, idParam, safeReturnUrl } from '../../core/create/create-new';
import { ReturnStateService } from '../../core/create/return-state.service';

/** Record kinds this screen can create (branches are created on the Branches screen). */
const SETUP_KINDS: CreateKind[] = ['academic_year', 'class', 'section'];

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
  private readonly route = inject(ActivatedRoute);
  private readonly returnState = inject(ReturnStateService);

  protected readonly years = signal<AcademicYear[]>([]);
  protected readonly branches = signal<Branch[]>([]);
  protected readonly classes = signal<SchoolClass[]>([]);
  protected readonly sections = signal<Section[]>([]);
  protected readonly error = signal<string | null>(null);

  private readonly query = toSignal(this.route.queryParamMap, {
    requireSync: true,
  });
  /** Set when another screen sent the user here to create one record. */
  protected readonly createKind = computed<CreateKind | null>(() => {
    const kind = this.query().get('create');
    return SETUP_KINDS.find((k) => k === kind) ?? null;
  });
  protected readonly returnTo = computed(() => safeReturnUrl(this.query().get('returnTo')));
  protected readonly from = computed(
    () => this.query().get('from')?.trim() || 'your previous page',
  );
  /** The banner and the automatic return only apply when both parameters are valid. */
  protected readonly returning = computed(
    () => this.createKind() !== null && this.returnTo() !== null,
  );
  protected readonly kindLabel = computed(() => {
    const kind = this.createKind();
    return kind ? CREATE_LABELS[kind] : '';
  });

  private readonly yearCard = viewChild<ElementRef<HTMLElement>>('yearCard');
  private readonly classCard = viewChild<ElementRef<HTMLElement>>('classCard');
  private readonly sectionCard = viewChild<ElementRef<HTMLElement>>('sectionCard');

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
    // Pre-fill from the page that asked for the record (ids only, nothing personal).
    const params = this.route.snapshot.queryParamMap;
    const branchId = idParam(params.get('branchId'));
    if (branchId) this.classForm.controls.branch_id.setValue(branchId);
    const classId = idParam(params.get('classId'));
    if (classId) this.sectionForm.controls.class_id.setValue(classId);

    this.reload();
    afterNextRender(() => this.focusTarget());
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
    this.run(this.api.createYear(this.yearForm.getRawValue()), 'academic_year', () =>
      this.yearForm.reset(),
    );
  }

  protected makeCurrent(id: number): void {
    this.run(this.api.makeYearCurrent(id));
  }

  protected addClass(): void {
    if (this.classForm.invalid) return;
    const { name, level, branch_id } = this.classForm.getRawValue();
    this.run(
      this.api.createClass({ name, level, branch_id: this.needsBranch() ? branch_id : null }),
      'class',
    );
  }

  protected addSection(): void {
    if (this.sectionForm.invalid) return;
    this.run(this.api.createSection(this.sectionForm.getRawValue()), 'section', () =>
      this.sectionForm.controls.name.reset(),
    );
  }

  /** Leave without saving: the other page comes back with nothing selected for this record. */
  protected cancelCreate(): void {
    const back = this.returnTo();
    const kind = this.createKind();
    if (back && kind) this.returnState.cancel(back, kind);
  }

  private run<T extends { id: number }>(
    request: Observable<T>,
    kind?: CreateKind,
    onDone?: () => void,
  ): void {
    this.error.set(null);
    request.subscribe({
      next: (created) => {
        onDone?.();
        const back = this.returnTo();
        if (kind && back && this.createKind() === kind) {
          this.returnState.finish(back, kind, created.id);
          return;
        }
        this.reload();
      },
      error: (err: unknown) => this.error.set(this.message(err)),
    });
  }

  /** Bring the matching form into view and focus its first field. */
  private focusTarget(): void {
    const kind = this.createKind();
    const card =
      kind === 'academic_year'
        ? this.yearCard()
        : kind === 'class'
          ? this.classCard()
          : kind === 'section'
            ? this.sectionCard()
            : undefined;
    if (!card) return;
    card.nativeElement.scrollIntoView({ block: 'center' });
    card.nativeElement.querySelector<HTMLElement>('input, select')?.focus();
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
