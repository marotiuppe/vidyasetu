import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AcademicYear, AcademicsApi, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import {
  AdmissionDetail,
  AdmissionDocument,
  AdmissionStatus,
  AdmissionsApi,
  DOCUMENT_MAX_COUNT,
  DOCUMENT_TYPES,
} from '../../core/api/admissions.api';
import { StudentCredential } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { saveBlob } from '../../core/ui/download';
import { formatDate, todayIst } from '../../core/ui/dates';
import { LoginDetails } from '../students/login-details';
import {
  ALLOWED_TRANSITIONS,
  actionKey,
  extensionFor,
  fileProblem,
  sizeText,
  sourceKey,
  statusBadge,
  statusKey,
} from './admission-labels';
import { AdmissionForm, AdmissionFormValue } from './admission-form';

/** One application: details, status moves, documents and conversion to a student. */
@Component({
  selector: 'sms-admission-detail',
  imports: [ReactiveFormsModule, RouterLink, AdmissionForm, LoginDetails],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admission-detail.html',
  styleUrl: './admission-detail.css',
})
export class AdmissionDetailPage {
  private readonly api = inject(AdmissionsApi);
  private readonly academics = inject(AcademicsApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly statusKey = statusKey;
  protected readonly sourceKey = sourceKey;
  protected readonly actionKey = actionKey;
  protected readonly statusBadge = statusBadge;
  protected readonly sizeText = sizeText;
  protected readonly today = todayIst();
  protected readonly docTypes = DOCUMENT_TYPES.join(',');
  protected readonly maxDocuments = DOCUMENT_MAX_COUNT;
  protected readonly enrolledId = signal<number | null>(null);

  private appId = 0;
  protected readonly app = signal<AdmissionDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly notFound = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  // Status
  protected readonly busy = signal(false);
  protected readonly actions = computed<AdmissionStatus[]>(() => {
    const a = this.app();
    return a ? ALLOWED_TRANSITIONS[a.status] : [];
  });
  protected readonly rejecting = signal(false);
  protected readonly rejectForm = this.fb.group({
    reason: ['', [Validators.required, Validators.maxLength(1000)]],
  });

  // Edit
  protected readonly editing = signal(false);
  protected readonly editBusy = signal(false);
  protected readonly editError = signal<string | null>(null);

  // Documents
  protected readonly docForm = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(200)]],
  });
  protected readonly file = signal<File | null>(null);
  protected readonly docError = signal<string | null>(null);
  protected readonly uploading = signal(false);
  private readonly fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');
  protected readonly canUpload = computed(
    () => (this.app()?.documents.length ?? 0) < DOCUMENT_MAX_COUNT,
  );

  // Convert to student
  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);
  private readonly convertClass = signal(0);
  protected readonly convertClasses = computed(() => {
    const branch = this.app()?.branch_id;
    return this.classes().filter((c) => c.branch_id === branch);
  });
  protected readonly convertSections = computed(() => {
    const c = this.convertClass();
    return c ? this.sections().filter((s) => s.class_id === c) : [];
  });
  protected readonly convertForm = this.fb.group({
    class_id: [0, Validators.min(1)],
    section_id: [0],
    academic_year_id: [0, Validators.min(1)],
    admission_no: ['', [Validators.required, Validators.maxLength(50)]],
    admission_date: [todayIst()],
  });
  protected readonly converting = signal(false);
  protected readonly convertError = signal<string | null>(null);
  /** Logins created by the conversion. Held in memory only, shown once. */
  protected readonly credentials = signal<StudentCredential[] | null>(null);
  protected readonly studentId = computed(
    () => this.enrolledId() ?? this.app()?.student_id ?? null,
  );
  /** Needs the gender and date of birth, which the server requires for conversion. */
  protected readonly canConvert = computed(() => {
    const a = this.app();
    return a !== null && a.status === 'admitted' && !!a.gender && !!a.date_of_birth;
  });

  constructor() {
    this.academics.years().subscribe({
      next: (y) => {
        this.years.set(y);
        if (this.convertForm.controls.academic_year_id.value === 0) {
          const current = y.find((v) => v.is_current)?.id ?? 0;
          this.convertForm.controls.academic_year_id.setValue(current);
        }
      },
      error: () => undefined,
    });
    this.academics.classes().subscribe({
      next: (c) => this.classes.set(c),
      error: () => undefined,
    });
    this.academics.sections().subscribe({
      next: (s) => this.sections.set(s),
      error: () => undefined,
    });
    this.convertForm.controls.class_id.valueChanges.pipe(takeUntilDestroyed()).subscribe((v) => {
      this.convertClass.set(Number(v));
      this.convertForm.controls.section_id.setValue(0, { emitEvent: false });
    });

    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((p) => {
      this.appId = Number(p.get('id'));
      this.resetPanels();
      this.load(this.appId);
    });
  }

  protected yearName(id: number | null): string {
    if (id === null) return this.i18n.t('admissions.notSet');
    return this.years().find((y) => y.id === id)?.name ?? this.i18n.t('admissions.notSet');
  }

  protected dateText(value: string | null | undefined): string {
    return formatDate(value, this.i18n.lang()) || this.i18n.t('admissions.notSet');
  }

  protected enumText(group: 'gender' | 'relation', value: string): string {
    return this.i18n.t(`students.list.${group}.${value}`);
  }

  // ---- status ------------------------------------------------------------

  protected startMove(status: AdmissionStatus): void {
    this.notice.set(null);
    if (status === 'rejected') {
      this.rejectForm.reset({ reason: '' });
      this.rejecting.set(true);
      return;
    }
    this.changeStatus(status);
  }

  protected confirmReject(): void {
    if (this.rejectForm.invalid) {
      this.rejectForm.markAllAsTouched();
      return;
    }
    this.changeStatus('rejected', this.rejectForm.getRawValue().reason.trim());
  }

  protected cancelReject(): void {
    this.rejecting.set(false);
  }

  // ---- edit --------------------------------------------------------------

  protected saveEdit(body: AdmissionFormValue): void {
    if (this.editBusy()) return;
    this.editBusy.set(true);
    this.editError.set(null);
    this.api.update(this.appId, body).subscribe({
      next: () => {
        this.editBusy.set(false);
        this.editing.set(false);
        this.notice.set(this.i18n.t('admissions.detail.saved'));
        this.reload();
      },
      error: (err: unknown) => {
        this.editBusy.set(false);
        this.editError.set(apiErrorMessage(err));
      },
    });
  }

  // ---- documents ---------------------------------------------------------

  protected onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const picked = input.files?.[0] ?? null;
    this.docError.set(null);
    if (picked === null) {
      this.file.set(null);
      return;
    }
    const problem = fileProblem(picked, DOCUMENT_TYPES);
    if (problem !== null) {
      this.file.set(null);
      input.value = '';
      this.docError.set(
        this.i18n.t(
          problem === 'type' ? 'admissions.docs.typeInvalid' : 'admissions.docs.tooLarge',
        ),
      );
      return;
    }
    this.file.set(picked);
    if (!this.docForm.controls.name.value) {
      this.docForm.controls.name.setValue(picked.name.replace(/\.[^.]+$/, '').slice(0, 200));
    }
  }

  protected upload(): void {
    if (this.uploading()) return;
    if (!this.canUpload()) {
      this.docError.set(this.i18n.t('admissions.docs.full'));
      return;
    }
    const picked = this.file();
    if (picked === null) {
      this.docError.set(this.i18n.t('admissions.docs.noFile'));
      return;
    }
    if (this.docForm.invalid) {
      this.docForm.markAllAsTouched();
      return;
    }
    this.uploading.set(true);
    this.docError.set(null);
    this.api.uploadDocument(this.appId, picked, this.docForm.getRawValue().name.trim()).subscribe({
      next: () => {
        this.uploading.set(false);
        this.file.set(null);
        this.docForm.reset({ name: '' });
        const el = this.fileInput();
        if (el) el.nativeElement.value = '';
        this.notice.set(this.i18n.t('admissions.docs.uploaded'));
        this.reload();
      },
      error: (err: unknown) => {
        this.uploading.set(false);
        this.docError.set(apiErrorMessage(err));
      },
    });
  }

  protected download(doc: AdmissionDocument): void {
    this.docError.set(null);
    this.api.downloadDocument(this.appId, doc.id).subscribe({
      next: (blob) => {
        const ext = extensionFor(doc.content_type);
        const name = ext && !doc.name.toLowerCase().endsWith(ext) ? doc.name + ext : doc.name;
        saveBlob(blob, name);
      },
      error: (err: unknown) => this.docError.set(apiErrorMessage(err)),
    });
  }

  protected remove(doc: AdmissionDocument): void {
    if (!window.confirm(this.i18n.t('admissions.docs.confirmDelete', { name: doc.name }))) return;
    this.docError.set(null);
    this.api.deleteDocument(this.appId, doc.id).subscribe({
      next: () => {
        this.notice.set(this.i18n.t('admissions.docs.deleted'));
        this.reload();
      },
      error: (err: unknown) => this.docError.set(apiErrorMessage(err)),
    });
  }

  // ---- convert -----------------------------------------------------------

  protected convert(): void {
    const a = this.app();
    if (a === null || !this.canConvert() || this.converting()) return;
    if (this.convertForm.invalid) {
      this.convertForm.markAllAsTouched();
      return;
    }
    const v = this.convertForm.getRawValue();
    this.converting.set(true);
    this.convertError.set(null);
    this.api
      .convert(a.id, {
        class_id: Number(v.class_id),
        section_id: Number(v.section_id) || null,
        academic_year_id: Number(v.academic_year_id),
        admission_no: v.admission_no.trim(),
        admission_date: v.admission_date || null,
      })
      .subscribe({
        next: (res) => {
          this.converting.set(false);
          this.enrolledId.set(res.student_id);
          this.credentials.set(res.credentials?.length ? res.credentials : null);
          this.notice.set(this.i18n.t('admissions.convert.done'));
          this.reload();
        },
        error: (err: unknown) => {
          this.converting.set(false);
          this.convertError.set(placeServerErrors(this.convertForm, err));
        },
      });
  }

  /** Leave the one-time login panel for the new student's profile. */
  protected openStudent(): void {
    const id = this.studentId();
    this.credentials.set(null);
    if (id !== null) void this.router.navigate(['/students', id]);
  }

  // ---- loading -----------------------------------------------------------

  private load(id: number): void {
    this.loading.set(true);
    this.notFound.set(false);
    this.error.set(null);
    this.api.get(id).subscribe({
      next: (a) => {
        this.app.set(a);
        this.loading.set(false);
        if (a.class_id !== null) this.convertForm.controls.class_id.setValue(a.class_id);
      },
      error: (err: unknown) => {
        this.app.set(null);
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && err.status === 404) this.notFound.set(true);
        else this.error.set(apiErrorMessage(err));
      },
    });
  }

  private reload(): void {
    this.api.get(this.appId).subscribe({
      next: (a) => this.app.set(a),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  private changeStatus(status: AdmissionStatus, reason?: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.setStatus(this.appId, status, reason).subscribe({
      next: () => {
        this.busy.set(false);
        this.rejecting.set(false);
        this.notice.set(this.i18n.t('admissions.statusChanged'));
        this.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private resetPanels(): void {
    this.editing.set(false);
    this.rejecting.set(false);
    this.notice.set(null);
    this.error.set(null);
    this.docError.set(null);
    this.credentials.set(null);
    this.enrolledId.set(null);
    this.convertError.set(null);
  }
}
