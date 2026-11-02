import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api/api-error';
import { DataRequest, DataRequestType, PolicyStatus, PrivacyApi } from '../../core/api/privacy.api';
import { Student, StudentsApi } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { formatDate, formatDateTime } from '../../core/ui/dates';
import { focusById } from '../../core/ui/download';

const TYPES: DataRequestType[] = ['access', 'correction', 'erasure'];

/** "Privacy and data": download my data, raise a data-rights request, see accepted policies. */
@Component({
  selector: 'sms-privacy',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './privacy.html',
  styleUrl: './privacy.css',
})
export class Privacy {
  private readonly api = inject(PrivacyApi);
  private readonly students = inject(StudentsApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly types = TYPES;
  protected readonly isParent = computed(() => this.auth.user()?.role === 'parent');
  protected readonly children = signal<Student[]>([]);

  protected readonly requests = signal<DataRequest[]>([]);
  protected readonly requestsLoading = signal(true);
  protected readonly requestsError = signal<string | null>(null);
  protected readonly policies = signal<PolicyStatus[]>([]);
  protected readonly policiesLoaded = signal(false);

  protected readonly downloading = signal(false);
  protected readonly downloadError = signal<string | null>(null);
  protected readonly submitting = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly form = this.fb.group({
    type: ['access' as DataRequestType, Validators.required],
    student_id: [0],
    message: ['', [Validators.required, Validators.maxLength(2000)]],
  });

  constructor() {
    this.loadRequests();
    this.api.policies().subscribe({
      next: (res) => {
        this.policies.set(res.policies);
        this.policiesLoaded.set(true);
      },
      error: () => this.policiesLoaded.set(true),
    });
    if (this.isParent()) {
      this.students.list({}, 1, 100).subscribe({
        next: (page) => {
          this.children.set(page.items);
          if (page.items.length === 1) this.form.controls.student_id.setValue(page.items[0].id);
        },
        error: () => undefined,
      });
    }
  }

  protected date(value: string | null): string {
    return formatDate(value, this.i18n.lang());
  }

  protected dateTime(value: string | null): string {
    return formatDateTime(value, this.i18n.lang());
  }

  protected download(): void {
    this.downloading.set(true);
    this.downloadError.set(null);
    this.api.downloadMyData().subscribe({
      next: () => this.downloading.set(false),
      error: (err: unknown) => {
        this.downloading.set(false);
        this.downloadError.set(apiErrorMessage(err));
      },
    });
  }

  protected submit(): void {
    const { type, student_id, message } = this.form.getRawValue();
    if (this.form.invalid || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.isParent() && this.children().length > 1 && !student_id) {
      this.formError.set(this.i18n.t('privacy.request.pickChild'));
      return;
    }
    this.submitting.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.api
      .createRequest({
        type,
        message: message.trim(),
        student_id: student_id || null,
      })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.form.controls.message.reset('');
          this.form.controls.message.markAsUntouched();
          this.notice.set(this.i18n.t('privacy.request.sent'));
          this.loadRequests();
          focusById('privacy-request-notice');
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.formError.set(apiErrorMessage(err));
        },
      });
  }

  private loadRequests(): void {
    this.requestsLoading.set(true);
    this.api.myRequests().subscribe({
      next: (items) => {
        this.requests.set(items);
        this.requestsLoading.set(false);
      },
      error: (err: unknown) => {
        this.requestsError.set(apiErrorMessage(err));
        this.requestsLoading.set(false);
      },
    });
  }
}
