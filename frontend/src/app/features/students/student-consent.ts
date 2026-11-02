import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  CONSENT_PURPOSES,
  ConsentInput,
  ConsentMethod,
  ConsentOverview,
  ConsentPurpose,
  ConsentStatus,
  PrivacyApi,
} from '../../core/api/privacy.api';
import { AuthService } from '../../core/auth/auth.service';
import { canWriteStudents } from '../../core/auth/permissions';
import { I18n } from '../../core/i18n/i18n';
import { formatDateTime } from '../../core/ui/dates';

type Recordable = 'granted' | 'refused' | 'withdrawn';

/**
 * Parental consent for one student: four purposes with their current status and a history.
 * Parents act online for their own children; office staff record paper or in-person consent.
 */
@Component({
  selector: 'sms-student-consent',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-consent.html',
  styleUrl: './student-consent.css',
})
export class StudentConsent {
  private readonly api = inject(PrivacyApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  readonly studentId = input.required<number>();

  protected readonly purposes = CONSENT_PURPOSES;
  protected readonly isParent = computed(() => this.auth.user()?.role === 'parent');
  protected readonly isStaffRecorder = canWriteStudents(this.auth);
  protected readonly canDownload = computed(() => this.isParent() || this.isStaffRecorder);

  protected readonly data = signal<ConsentOverview | null>(null);
  protected readonly loading = signal(true);
  /** The caller may not see consent for this student (403 or 404): the card then stays quiet. */
  protected readonly unavailable = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly downloading = signal(false);
  protected readonly showHistory = signal(false);
  /** Purpose whose staff form is open. */
  protected readonly recording = signal<ConsentPurpose | null>(null);

  protected readonly recordForm = this.fb.group({
    status: ['granted' as Recordable],
    method: ['paper' as Extract<ConsentMethod, 'paper' | 'in_person'>],
    note: [''],
  });

  constructor() {
    effect(() => {
      const id = this.studentId();
      untracked(() => this.load(id));
    });
  }

  protected statusOf(purpose: ConsentPurpose): ConsentStatus {
    return this.data()?.current.find((c) => c.purpose === purpose)?.status ?? 'none';
  }

  protected whenOf(purpose: ConsentPurpose): string {
    const c = this.data()?.current.find((x) => x.purpose === purpose);
    if (!c || c.status === 'none') return '';
    const parts = [
      c.method ? this.i18n.t('consent.method.' + c.method) : '',
      formatDateTime(c.recorded_at, this.i18n.lang()),
    ];
    return parts.filter(Boolean).join(' · ');
  }

  protected dateTime(value: string): string {
    return formatDateTime(value, this.i18n.lang());
  }

  /** Parent actions (online). */
  protected parentAct(purpose: ConsentPurpose, status: Recordable): void {
    this.save({ purpose, status, method: 'online' });
  }

  protected startRecord(purpose: ConsentPurpose): void {
    this.recording.set(purpose);
    this.recordForm.reset({ status: 'granted', method: 'paper', note: '' });
    this.error.set(null);
    this.notice.set(null);
  }

  protected cancelRecord(): void {
    this.recording.set(null);
  }

  protected submitRecord(): void {
    const purpose = this.recording();
    if (purpose === null) return;
    const { status, method, note } = this.recordForm.getRawValue();
    this.save({ purpose, status, method, note: note.trim() || undefined });
  }

  protected toggleHistory(): void {
    this.showHistory.update((v) => !v);
  }

  protected download(): void {
    this.downloading.set(true);
    this.error.set(null);
    this.api.downloadStudentData(this.studentId()).subscribe({
      next: () => this.downloading.set(false),
      error: (err: unknown) => {
        this.downloading.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private save(body: ConsentInput): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.notice.set(null);
    this.api.recordConsent(this.studentId(), body).subscribe({
      next: () => {
        this.busy.set(false);
        this.recording.set(null);
        this.notice.set(this.i18n.t('consent.saved'));
        this.load(this.studentId(), true);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  private load(id: number, quiet = false): void {
    if (!quiet) this.loading.set(true);
    this.api.consents(id).subscribe({
      next: (res) => {
        this.data.set(res);
        this.unavailable.set(false);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && (err.status === 403 || err.status === 404)) {
          this.unavailable.set(true);
          return;
        }
        this.error.set(apiErrorMessage(err));
      },
    });
  }
}
