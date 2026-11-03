import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Title } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { map } from 'rxjs';

import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import {
  PublicAdmissionInfo,
  PublicAdmissionsApi,
  PublicApplication,
} from '../../core/api/admissions.api';
import { GENDERS, Gender, RELATIONS, Relation } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { todayIst } from '../../core/ui/dates';
import { PHONE_PATTERN } from '../students/student-labels';

const PRODUCT_NAME = 'Vidyasetu';

/**
 * Online application form for one school, reached by its school code. Public: no sign-in, and it
 * lives outside the signed-in shell. Shows only the reference number after a successful send.
 */
@Component({
  selector: 'sms-apply-page',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './apply-page.html',
  styleUrl: './apply-page.css',
})
export class ApplyPage {
  private readonly api = inject(PublicAdmissionsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly title = inject(Title);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  protected readonly i18n = inject(I18n);

  protected readonly code = toSignal(this.route.paramMap.pipe(map((p) => p.get('code') ?? '')), {
    initialValue: this.route.snapshot.paramMap.get('code') ?? '',
  });
  protected readonly genders = GENDERS;
  protected readonly relations: Relation[] = RELATIONS;
  protected readonly today = todayIst();

  protected readonly info = signal<PublicAdmissionInfo | null>(null);
  protected readonly loading = signal(true);
  /** Unknown school, online admissions switched off, or the form is closed. Same message for all. */
  protected readonly unavailable = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly submitting = signal(false);
  protected readonly submitError = signal<string | null>(null);
  protected readonly reference = signal<string | null>(null);

  private readonly pickedBranch = signal(0);
  protected readonly classOptions = computed(() => {
    const b = this.pickedBranch();
    return (this.info()?.classes ?? []).filter((c) => c.branch_id === b);
  });

  protected readonly form = this.fb.group({
    branch_id: [0, Validators.min(1)],
    class_id: [0],
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    gender: ['' as Gender | ''],
    date_of_birth: [''],
    previous_school: ['', Validators.maxLength(200)],
    address: ['', Validators.maxLength(500)],
    guardian_name: ['', [Validators.required, Validators.maxLength(200)]],
    guardian_phone: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
    guardian_email: ['', [Validators.email, Validators.maxLength(254)]],
    guardian_relation: ['father' as Relation],
    consent: [false, Validators.requiredTrue],
    /** Honeypot: hidden from people, filled by bots. Must stay empty. */
    website: [''],
  });

  constructor() {
    const previous = this.title.getTitle();
    this.destroyRef.onDestroy(() => this.title.setTitle(previous));
    this.title.setTitle(`${this.i18n.t('apply.title')} | ${PRODUCT_NAME}`);

    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe(() => this.load());
  }

  protected onBranchChange(): void {
    this.pickedBranch.set(Number(this.form.controls.branch_id.value));
    this.form.controls.class_id.setValue(0);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.submitting()) return;
    const v = this.form.getRawValue();
    const body: PublicApplication = {
      branch_id: Number(v.branch_id),
      class_id: Number(v.class_id) || null,
      first_name: v.first_name.trim(),
      last_name: v.last_name.trim(),
      gender: v.gender || null,
      date_of_birth: v.date_of_birth || null,
      guardian_name: v.guardian_name.trim(),
      guardian_phone: v.guardian_phone.trim(),
      guardian_email: v.guardian_email.trim() || null,
      guardian_relation: v.guardian_relation,
      address: v.address.trim() || null,
      previous_school: v.previous_school.trim() || null,
      consent: true,
      website: v.website,
    };
    this.submitting.set(true);
    this.submitError.set(null);
    this.api.apply(this.code(), body).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.reference.set(res.reference);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.submitError.set(placeServerErrors(this.form, err));
      },
    });
  }

  protected again(): void {
    this.reference.set(null);
    this.submitError.set(null);
    this.form.reset({
      branch_id: this.info()?.branches.length === 1 ? (this.info()?.branches[0]?.id ?? 0) : 0,
      class_id: 0,
      first_name: '',
      last_name: '',
      gender: '',
      date_of_birth: '',
      previous_school: '',
      address: '',
      guardian_name: '',
      guardian_phone: '',
      guardian_email: '',
      guardian_relation: 'father',
      consent: false,
      website: '',
    });
    this.pickedBranch.set(Number(this.form.controls.branch_id.value));
  }

  private load(): void {
    this.loading.set(true);
    this.unavailable.set(false);
    this.loadError.set(null);
    this.info.set(null);
    this.api.info(this.code()).subscribe({
      next: (info) => {
        this.info.set(info);
        this.loading.set(false);
        if (!info.open) {
          this.unavailable.set(true);
          return;
        }
        if (info.branches.length === 1) {
          const only = info.branches[0]?.id ?? 0;
          this.form.controls.branch_id.setValue(only);
          this.pickedBranch.set(only);
        }
      },
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && err.status === 404) this.unavailable.set(true);
        else this.loadError.set(apiErrorMessage(err));
      },
    });
  }
}
