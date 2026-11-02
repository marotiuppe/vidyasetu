import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';

import { StudentCredential } from '../../core/api/students.api';
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

  /** Polite status line for screen readers after a copy. */
  protected readonly status = signal('');

  protected roleLabel(role: StudentCredential['role']): string {
    return role === 'student' ? 'Student' : 'Parent';
  }

  protected async copy(c: StudentCredential): Promise<void> {
    const lines = [
      `${this.roleLabel(c.role)}: ${c.full_name}`,
      `Username: ${c.username}`,
      c.linked_existing
        ? 'Password: uses the existing parent login'
        : `Temporary password: ${c.temporary_password ?? ''}`,
    ];
    const ok = await copyText(lines.join('\n'));
    this.status.set(
      ok
        ? `Copied the details for ${c.full_name}.`
        : 'Copying is not available here. Select the text and copy it by hand.',
    );
  }

  protected print(): void {
    window.print();
  }
}
