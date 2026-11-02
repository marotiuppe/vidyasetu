import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

import { I18n } from '../i18n/i18n';
import { Icon } from './icon';

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_BYTES = 1024 * 1024;

/**
 * Choose a school logo: file input with drag and drop, validation and a live preview.
 * It only emits the chosen File (or null); the parent calls the API.
 */
@Component({
  selector: 'sms-logo-picker',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './logo-picker.html',
  styleUrl: './logo-picker.css',
})
export class LogoPicker {
  protected readonly i18n = inject(I18n);

  /** The logo already saved on the server, if any. */
  readonly currentUrl = input<string | null>(null);
  readonly schoolName = input('');
  readonly disabled = input(false);

  /** A valid file was chosen, or null when the choice was cleared. */
  readonly picked = output<File | null>();
  /** The user asked to delete the saved logo. */
  readonly removed = output<void>();

  protected readonly previewUrl = signal<string | null>(null);
  protected readonly fileName = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly dragging = signal(false);
  protected readonly savedBroken = signal(false);

  constructor() {
    inject(DestroyRef).onDestroy(() => this.revoke());
  }

  /** Forget the chosen file (the parent calls this after a successful upload). */
  clear(): void {
    this.revoke();
    this.previewUrl.set(null);
    this.fileName.set(null);
    this.error.set(null);
    this.savedBroken.set(false);
  }

  protected onInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.item(0) ?? null;
    input.value = '';
    if (file) this.choose(file);
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.disabled()) this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files.item(0) ?? null;
    if (file && !this.disabled()) this.choose(file);
  }

  protected discard(): void {
    this.clear();
    this.picked.emit(null);
  }

  private choose(file: File): void {
    if (!ALLOWED_TYPES.includes(file.type)) {
      this.error.set(this.i18n.t('admin.logo.typeError'));
      return;
    }
    if (file.size > MAX_BYTES) {
      this.error.set(this.i18n.t('admin.logo.sizeError'));
      return;
    }
    this.revoke();
    this.error.set(null);
    this.previewUrl.set(URL.createObjectURL(file));
    this.fileName.set(file.name);
    this.picked.emit(file);
  }

  private revoke(): void {
    const url = this.previewUrl();
    if (url) URL.revokeObjectURL(url);
  }
}
