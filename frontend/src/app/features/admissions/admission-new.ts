import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api/api-error';
import { AdmissionsApi } from '../../core/api/admissions.api';
import { I18n } from '../../core/i18n/i18n';
import { AdmissionForm, AdmissionFormValue } from './admission-form';

/** Create a new enquiry. The server sets the source (enquiry or walk-in) for staff entries. */
@Component({
  selector: 'sms-admission-new',
  imports: [RouterLink, AdmissionForm],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admission-new.html',
})
export class AdmissionNew {
  private readonly api = inject(AdmissionsApi);
  private readonly router = inject(Router);
  protected readonly i18n = inject(I18n);

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected save(body: AdmissionFormValue): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.create(body).subscribe({
      next: (created) => {
        this.busy.set(false);
        void this.router.navigate(['/admissions', created.id]);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected cancel(): void {
    void this.router.navigate(['/admissions']);
  }
}
