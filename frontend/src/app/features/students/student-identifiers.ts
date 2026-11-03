import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage, placeServerErrors } from '../../core/api/api-error';
import {
  IdentifiersReveal,
  IdentifiersUpdate,
  IdentifiersView,
  StudentsApi,
} from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';

/** A yes / no / not-asked choice in the form. Maps to true, false or null on the wire. */
type Choice = 'unset' | 'yes' | 'no';

const PEN_PATTERN = /^[A-Za-z0-9]{11}$/;
const APAAR_PATTERN = /^[0-9]{12}$/;

function toChoice(value: boolean | null): Choice {
  if (value === true) return 'yes';
  if (value === false) return 'no';
  return 'unset';
}

function toBool(choice: Choice): boolean | null {
  if (choice === 'yes') return true;
  if (choice === 'no') return false;
  return null;
}

/**
 * Government IDs (PEN, APAAR, Aadhaar check) for one student. Shown only when the school has
 * switched the storage on. Values are masked; the full ones appear only after an explicit reveal.
 */
@Component({
  selector: 'sms-student-identifiers',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-identifiers.html',
  styleUrl: './student-identifiers.css',
})
export class StudentIdentifiers {
  private readonly api = inject(StudentsApi);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  readonly studentId = input.required<number>();
  /** The signed-in role may see the full values (school owner, management, headmaster). */
  readonly canReveal = input(false);

  protected readonly view = signal<IdentifiersView | null>(null);
  /** Full values after a reveal. Cleared when the user hides them or the student changes. */
  protected readonly revealed = signal<IdentifiersReveal | null>(null);
  /** The school has the feature off, or this user may not see it: the card stays out of the page. */
  protected readonly hidden = signal(false);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly editing = signal(false);
  protected readonly busy = signal(false);
  protected readonly editError = signal<string | null>(null);

  protected readonly form = this.fb.group({
    pen: ['', Validators.pattern(PEN_PATTERN)],
    remove_pen: [false],
    consent: ['unset' as Choice],
    apaar_id: ['', Validators.pattern(APAAR_PATTERN)],
    remove_apaar: [false],
    aadhaar: ['unset' as Choice],
  });

  constructor() {
    effect(() => {
      const id = this.studentId();
      untracked(() => {
        this.revealed.set(null);
        this.editing.set(false);
        this.load(id);
      });
    });
  }

  protected consentText(value: boolean | null): string {
    return this.i18n.t(`students.ids.consent.${toChoice(value)}`);
  }

  protected aadhaarText(value: boolean | null): string {
    return this.i18n.t(`students.ids.aadhaar.${toChoice(value)}`);
  }

  protected reveal(): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.revealIdentifiers(this.studentId()).subscribe({
      next: (values) => {
        this.busy.set(false);
        this.revealed.set(values);
        this.notice.set(this.i18n.t('students.ids.revealed'));
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected hide(): void {
    this.revealed.set(null);
    this.notice.set(null);
  }

  protected startEdit(): void {
    const v = this.view();
    if (v === null) return;
    this.form.reset({
      pen: '',
      remove_pen: false,
      consent: toChoice(v.apaar_consent),
      apaar_id: '',
      remove_apaar: false,
      aadhaar: toChoice(v.aadhaar_details_match),
    });
    this.editError.set(null);
    this.notice.set(null);
    this.editing.set(true);
  }

  protected cancelEdit(): void {
    this.editing.set(false);
    this.editError.set(null);
  }

  protected save(): void {
    if (this.busy()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    if (v.consent !== 'yes' && v.apaar_id.trim() !== '') {
      this.editError.set(this.i18n.t('students.ids.apaarNeedsConsent'));
      return;
    }

    // Blank keeps the saved value; "Remove" sends null, which clears it.
    const body: IdentifiersUpdate = {
      apaar_consent: toBool(v.consent),
      aadhaar_details_match: toBool(v.aadhaar),
    };
    if (v.remove_pen) body.pen = null;
    else if (v.pen.trim() !== '') body.pen = v.pen.trim();

    if (v.consent !== 'yes' || v.remove_apaar) body.apaar_id = null;
    else if (v.apaar_id.trim() !== '') body.apaar_id = v.apaar_id.trim();

    this.busy.set(true);
    this.editError.set(null);
    this.api.updateIdentifiers(this.studentId(), body).subscribe({
      next: () => {
        this.busy.set(false);
        this.editing.set(false);
        this.revealed.set(null);
        this.notice.set(this.i18n.t('students.ids.saved'));
        this.load(this.studentId());
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.editError.set(placeServerErrors(this.form, err));
      },
    });
  }

  private load(id: number): void {
    this.error.set(null);
    this.api.getIdentifiers(id).subscribe({
      next: (v) => {
        this.view.set(v);
        this.hidden.set(!v.enabled);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && (err.status === 403 || err.status === 404)) {
          this.hidden.set(true);
          return;
        }
        this.error.set(this.i18n.t('students.ids.error.load'));
      },
    });
  }
}
