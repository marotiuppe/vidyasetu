import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';

import { StudentCredential } from '../../core/api/students.api';
import { I18n } from '../../core/i18n/i18n';
import { copyText } from '../../core/ui/clipboard';

/**
 * One-time list of the logins created with a student. The credentials are an input from the form only:
 * this component never stores, logs or puts them in the URL.
 */
@Component({
  selector: 'sms-login-details',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login-details.html',
  styleUrl: './login-details.css',
})
export class LoginDetails {
  readonly credentials = input.required<StudentCredential[]>();
  readonly done = output<void>();
  protected readonly i18n = inject(I18n);

  /** Polite status line for screen readers after a copy. */
  protected readonly status = signal('');

  protected roleLabel(role: StudentCredential['role']): string {
    return this.i18n.t(
      role === 'student' ? 'students.list.login.roleStudent' : 'students.list.login.roleParent',
    );
  }

  protected async copy(c: StudentCredential): Promise<void> {
    const lines = [
      this.i18n.t('students.list.login.copyRole', {
        role: this.roleLabel(c.role),
        name: c.full_name,
      }),
      this.i18n.t('students.list.login.copyUsername', { username: c.username }),
      c.linked_existing
        ? this.i18n.t('students.list.login.copyExisting')
        : this.i18n.t('students.list.login.copyTemp', { password: c.temporary_password ?? '' }),
    ];
    const ok = await copyText(lines.join('\n'));
    this.status.set(
      ok
        ? this.i18n.t('students.list.login.copied', { name: c.full_name })
        : this.i18n.t('students.list.login.copyUnavailable'),
    );
  }

  protected print(): void {
    window.print();
  }
}
