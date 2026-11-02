import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

import { AcademicsApi, Branch, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  NOTICE_CATEGORIES,
  NewNotice,
  Notice,
  NoticeCategory,
  NoticeTargetType,
  NoticesApi,
} from '../../core/api/notices.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { CATEGORY_KEYS, todayIso } from './notice-labels';

export const TITLE_MAX = 150;
export const BODY_MAX = 5000;

function notInPast(control: { value: string }): ValidationErrors | null {
  return control.value && control.value < todayIso() ? { past: true } : null;
}

/** Compose or edit a notice. Edit mode keeps the target read-only. */
@Component({
  selector: 'sms-notice-form',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './notice-form.html',
  styleUrl: './notice-form.css',
})
export class NoticeForm implements OnInit {
  private readonly api = inject(NoticesApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  readonly notice = input<Notice | null>(null);
  readonly saved = output<string>();
  readonly cancelled = output<void>();

  protected readonly titleMax = TITLE_MAX;
  protected readonly bodyMax = BODY_MAX;
  protected readonly categories = NOTICE_CATEGORIES;
  protected readonly today = todayIso();

  private readonly role = this.auth.user()?.role;
  protected readonly isOwner = this.role === 'school_owner';
  protected readonly canPin = this.auth.hasRole('school_owner', 'management', 'headmaster');
  private readonly ownBranchId = this.auth.user()?.branch_id ?? null;

  protected readonly levels: { value: NoticeTargetType; labelKey: string }[] = this.isOwner
    ? [
        { value: 'school', labelKey: 'ops.common.wholeSchool' },
        { value: 'branch', labelKey: 'ops.level.branch' },
        { value: 'class', labelKey: 'ops.level.class' },
        { value: 'section', labelKey: 'ops.level.section' },
      ]
    : this.role === 'teacher'
      ? [
          { value: 'class', labelKey: 'ops.level.class' },
          { value: 'section', labelKey: 'ops.level.section' },
        ]
      : [
          { value: 'branch', labelKey: 'ops.level.myBranch' },
          { value: 'class', labelKey: 'ops.level.class' },
          { value: 'section', labelKey: 'ops.level.section' },
        ];

  protected readonly form = this.fb.group({
    title: ['', [Validators.required, Validators.maxLength(TITLE_MAX)]],
    body: ['', [Validators.required, Validators.maxLength(BODY_MAX)]],
    category: ['general' as NoticeCategory],
    is_pinned: [false],
    expires_on: ['', notInPast],
    level: [this.levels[0].value],
    branchId: [0],
    classId: [0],
    sectionId: [0],
  });

  protected readonly branches = signal<Branch[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);
  protected readonly busy = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);

  private readonly value = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });
  protected readonly titleLength = computed(() => this.value().title?.length ?? 0);
  protected readonly bodyLength = computed(() => this.value().body?.length ?? 0);
  protected readonly level = computed(() => this.value().level ?? this.levels[0].value);

  protected readonly classOptions = computed(() => {
    const b = this.isOwner ? (this.value().branchId ?? 0) : (this.ownBranchId ?? 0);
    return b ? this.classes().filter((c) => c.branch_id === b) : this.isOwner ? [] : this.classes();
  });
  protected readonly sectionOptions = computed(() => {
    const c = this.value().classId ?? 0;
    return c ? this.sections().filter((s) => s.class_id === c) : [];
  });

  /** Translation key of the target error to show, or null when the target is complete. */
  protected readonly targetError = computed(() => {
    const v = this.value();
    const level = this.level();
    if (this.isOwner && level !== 'school' && !v.branchId) return 'ops.form.errBranch';
    if ((level === 'class' || level === 'section') && !v.classId) return 'ops.form.errClass';
    if (level === 'section' && !v.sectionId) return 'ops.form.errSection';
    return null;
  });

  protected categoryName(category: NoticeCategory): string {
    return this.i18n.t(CATEGORY_KEYS[category]);
  }

  constructor() {
    effect(() => {
      const n = this.notice();
      untracked(() => this.fill(n));
    });
  }

  ngOnInit(): void {
    // Targets are only needed when composing; the lists are already scoped to the user by the backend.
    if (this.isOwner) {
      this.academics
        .branches()
        .subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
    }
    this.academics
      .classes()
      .subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
    this.academics
      .sections()
      .subscribe({ next: (s) => this.sections.set(s), error: () => undefined });
  }

  private fill(n: Notice | null): void {
    this.submitted.set(false);
    this.error.set(null);
    this.form.reset({
      title: n?.title ?? '',
      body: n?.body ?? '',
      category: n?.category ?? 'general',
      is_pinned: n?.is_pinned ?? false,
      expires_on: n?.expires_on ?? '',
      level: this.levels[0].value,
      branchId: 0,
      classId: 0,
      sectionId: 0,
    });
  }

  protected onLevelChange(): void {
    this.form.patchValue({ branchId: 0, classId: 0, sectionId: 0 });
  }

  protected onBranchChange(): void {
    this.form.patchValue({ classId: 0, sectionId: 0 });
  }

  protected onClassChange(): void {
    this.form.patchValue({ sectionId: 0 });
  }

  protected submit(): void {
    this.submitted.set(true);
    this.form.markAllAsTouched();
    const existing = this.notice();
    if (this.form.invalid || this.busy() || (!existing && this.targetError())) return;
    const v = this.form.getRawValue();
    const title = v.title.trim();
    const body = v.body.trim();
    if (!title || !body) return;
    this.busy.set(true);
    this.error.set(null);

    const done = {
      next: () => {
        this.busy.set(false);
        this.saved.emit(this.i18n.t(existing ? 'ops.form.updated' : 'ops.form.posted'));
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    };

    if (existing) {
      this.api
        .update(existing.id, {
          title,
          body,
          category: v.category,
          ...(this.canPin ? { is_pinned: v.is_pinned } : {}),
          expires_on: v.expires_on || null,
        })
        .subscribe(done);
      return;
    }

    const target: NewNotice['target'] = { type: v.level };
    if (this.isOwner && v.level !== 'school') target.branch_id = v.branchId;
    if (v.level === 'class' || v.level === 'section') target.class_id = v.classId;
    if (v.level === 'section') target.section_id = v.sectionId;
    this.api
      .create({
        title,
        body,
        category: v.category,
        ...(this.canPin ? { is_pinned: v.is_pinned } : {}),
        expires_on: v.expires_on || null,
        target,
      })
      .subscribe(done);
  }
}
