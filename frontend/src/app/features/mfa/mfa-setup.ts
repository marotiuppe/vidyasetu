import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api/api-error';
import { PrivacyApi } from '../../core/api/privacy.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { copyText } from '../../core/ui/clipboard';
import { focusById, saveBlob } from '../../core/ui/download';

type View = 'password' | 'scan' | 'codes' | 'manage';

const CODE_PATTERN = /^\s*\d{3}\s?\d{3}\s*$/;

/**
 * Two-factor (authenticator app) setup and management. Forced when policy requires it
 * (the only page a user can open), voluntary from My settings otherwise.
 */
@Component({
  selector: 'sms-mfa-setup',
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './mfa-setup.html',
  styleUrl: './mfa-setup.css',
})
export class MfaSetup {
  private readonly api = inject(PrivacyApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly i18n = inject(I18n);

  protected readonly forced = computed(() => this.auth.user()?.mfa_setup_required === true);
  /** Set when the server refuses to switch two-factor off because policy requires it. */
  protected readonly policyLocked = signal(false);

  protected readonly view = signal<View>(this.auth.user()?.mfa_enabled ? 'manage' : 'password');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly secret = signal('');
  protected readonly qr = signal<string | null>(null);
  protected readonly recoveryCodes = signal<string[]>([]);
  protected readonly saved = signal(false);
  /** Which management form is open: regenerate codes or switch off. */
  protected readonly manageAction = signal<'regenerate' | 'disable' | null>(null);

  protected readonly spacedSecret = computed(() =>
    this.secret()
      .replace(/(.{4})/g, '$1 ')
      .trim(),
  );
  protected readonly codesText = computed(() => this.recoveryCodes().join('\n'));

  protected readonly passwordForm = this.fb.group({ password: ['', Validators.required] });
  protected readonly codeForm = this.fb.group({
    code: ['', [Validators.required, Validators.pattern(CODE_PATTERN)]],
  });
  protected readonly manageForm = this.fb.group({
    password: ['', Validators.required],
    code: ['', [Validators.required, Validators.pattern(CODE_PATTERN)]],
  });

  protected startSetup(): void {
    if (this.passwordForm.invalid || this.busy()) {
      this.passwordForm.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.api.mfaSetup(this.passwordForm.getRawValue().password).subscribe({
      next: (res) => {
        this.secret.set(res.secret);
        // The QR code is drawn here in the browser; the secret is never sent to any other service.
        void this.drawQr(res.otpauth_uri).then(() => {
          this.busy.set(false);
          this.passwordForm.reset();
          this.codeForm.reset();
          this.view.set('scan');
          focusById('mfa-step-heading');
        });
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  protected verify(): void {
    if (this.codeForm.invalid || this.busy()) {
      this.codeForm.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.api.mfaEnable(this.digits(this.codeForm.getRawValue().code)).subscribe({
      next: (res) => {
        this.busy.set(false);
        this.secret.set('');
        this.qr.set(null);
        this.showCodes(res.recovery_codes);
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  protected openManage(action: 'regenerate' | 'disable'): void {
    this.manageAction.set(action);
    this.manageForm.reset();
    this.error.set(null);
    this.notice.set(null);
    focusById('manage-password');
  }

  protected cancelManage(): void {
    this.manageAction.set(null);
    this.error.set(null);
  }

  protected submitManage(): void {
    const action = this.manageAction();
    if (this.manageForm.invalid || this.busy() || action === null) {
      this.manageForm.markAllAsTouched();
      return;
    }
    const { password, code } = this.manageForm.getRawValue();
    this.busy.set(true);
    this.error.set(null);
    if (action === 'regenerate') {
      this.api.mfaRecoveryCodes(password, this.digits(code)).subscribe({
        next: (res) => {
          this.busy.set(false);
          this.manageAction.set(null);
          this.showCodes(res.recovery_codes);
        },
        error: (err: unknown) => this.fail(err),
      });
      return;
    }
    this.api.mfaDisable(password, this.digits(code)).subscribe({
      next: () => {
        this.busy.set(false);
        this.manageAction.set(null);
        const reset = (): void => {
          this.view.set('password');
          this.notice.set(this.i18n.t('mfa.setup.disabled'));
          focusById('mfa-step-heading');
        };
        this.auth.reloadUser().subscribe({ next: reset, error: reset });
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  protected async copy(text: string, what: 'secret' | 'codes'): Promise<void> {
    const ok = await copyText(text);
    const key = ok
      ? what === 'secret'
        ? 'mfa.setup.copiedSecret'
        : 'mfa.setup.copiedCodes'
      : 'mfa.setup.copyFailed';
    this.notice.set(this.i18n.t(key));
  }

  protected downloadCodes(): void {
    saveBlob(new Blob([this.codesText() + '\n'], { type: 'text/plain' }), 'recovery-codes.txt');
  }

  protected toggleSaved(event: Event): void {
    this.saved.set((event.target as HTMLInputElement).checked);
  }

  protected done(): void {
    if (!this.saved()) return;
    this.recoveryCodes.set([]);
    const leave = (): void => void this.router.navigate(['/settings']);
    this.auth.reloadUser().subscribe({ next: leave, error: leave });
  }

  protected backToStart(): void {
    this.view.set('password');
    this.error.set(null);
    this.secret.set('');
    this.qr.set(null);
    focusById('mfa-step-heading');
  }

  private showCodes(codes: string[]): void {
    this.recoveryCodes.set(codes);
    this.saved.set(false);
    this.notice.set(null);
    this.view.set('codes');
    focusById('mfa-step-heading');
  }

  private digits(value: string): string {
    return value.replace(/\s+/g, '');
  }

  private async drawQr(uri: string): Promise<void> {
    try {
      const qrcode = await import('qrcode');
      this.qr.set(
        await qrcode.toDataURL(uri, { margin: 1, width: 220, errorCorrectionLevel: 'M' }),
      );
    } catch {
      // The typed secret is always shown, so the QR code is a convenience only.
      this.qr.set(null);
    }
  }

  private fail(err: unknown): void {
    this.busy.set(false);
    const code: unknown = err instanceof HttpErrorResponse ? err.error?.code : null;
    if (code === 'mfa_required') {
      this.policyLocked.set(true);
      this.manageAction.set(null);
      this.error.set(null);
      return;
    }
    this.error.set(
      err instanceof HttpErrorResponse && err.status === 401
        ? this.i18n.t('mfa.setup.badCredentials')
        : apiErrorMessage(err),
    );
  }
}
