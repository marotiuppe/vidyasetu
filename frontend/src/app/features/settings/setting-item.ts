import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  linkedSignal,
  output,
  signal,
} from '@angular/core';

import { apiErrorMessage } from '../../core/api/api-error';
import {
  SettingItem,
  SettingLevel,
  SettingScope,
  SettingValue,
  SettingsApi,
} from '../../core/api/settings.api';
import { I18n } from '../../core/i18n/i18n';

type Draft = string | boolean;

function initialDraft(item: SettingItem): Draft {
  if (item.secret || item.type === 'secret') return '';
  if (item.type === 'bool') return item.value === true;
  return item.value === null || item.value === undefined ? '' : String(item.value);
}

/** One setting, drawn from its metadata. Saves and resets itself, then reports the updated item. */
@Component({
  selector: 'sms-setting-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './setting-item.html',
  styleUrl: './setting-item.css',
})
export class SettingItemView {
  private readonly api = inject(SettingsApi);
  protected readonly i18n = inject(I18n);

  readonly item = input.required<SettingItem>();
  readonly level = input.required<SettingLevel>();
  readonly scope = input<SettingScope>({});
  readonly updated = output<SettingItem>();

  protected readonly draft = linkedSignal<Draft>(() => initialDraft(this.item()));
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly isSecret = computed(() => this.item().secret || this.item().type === 'secret');
  protected readonly label = computed(() =>
    this.i18n.server('settings', this.item().key, this.item().label),
  );
  protected readonly inputId = computed(() => 'setting-' + this.item().key.replace(/\W/g, '-'));
  protected readonly dirty = computed(() => {
    const d = this.draft();
    if (this.isSecret()) return d !== '';
    return d !== initialDraft(this.item());
  });
  protected readonly inputType = computed(() => {
    switch (this.item().type) {
      case 'email':
        return 'email';
      case 'date':
        return 'date';
      case 'time':
        return 'time';
      case 'int':
        return 'number';
      default:
        return 'text';
    }
  });
  protected readonly range = computed(() => {
    const { min, max, type } = this.item();
    return type === 'int' && min !== null && max !== null
      ? this.i18n.t('settings.range', { min, max })
      : null;
  });
  protected readonly sourceLabel = computed(() =>
    this.i18n.t('settings.source.' + this.item().source),
  );
  protected readonly changed = computed(() => {
    const { updated_by_name: name, updated_at: at } = this.item();
    if (!at) return null;
    const date = new Date(at).toLocaleString(this.i18n.lang() === 'mr' ? 'mr-IN' : 'en-IN', {
      timeZone: 'Asia/Kolkata',
      dateStyle: 'medium',
      timeStyle: 'short',
    });
    return name
      ? this.i18n.t('settings.changedBy', { name, date })
      : this.i18n.t('settings.changedAt', { date });
  });
  protected readonly displayValue = computed(() => {
    const item = this.item();
    if (this.isSecret()) return this.i18n.t(item.is_set ? 'settings.set' : 'settings.notSet');
    if (item.type === 'bool')
      return this.i18n.t(item.value === true ? 'settings.on' : 'settings.off');
    return item.value === null || item.value === '' ? '—' : String(item.value);
  });

  protected setText(event: Event): void {
    this.draft.set((event.target as HTMLInputElement).value);
  }

  protected setBool(event: Event): void {
    this.draft.set((event.target as HTMLInputElement).checked);
  }

  protected save(): void {
    this.send(this.payload(), 'settings.saved');
  }

  protected clearSecret(): void {
    this.send('', 'settings.secret.cleared');
  }

  protected reset(): void {
    this.begin();
    this.api.reset(this.level(), this.item().key, this.scope()).subscribe({
      next: (res) => this.done(res, 'settings.resetDone'),
      error: (err: unknown) => this.fail(err),
    });
  }

  private payload(): SettingValue {
    const d = this.draft();
    if (typeof d === 'boolean') return d;
    if (this.item().type === 'int') return d.trim() === '' ? null : Number(d);
    return d;
  }

  private send(value: SettingValue, doneKey: string): void {
    this.begin();
    this.api.update(this.level(), this.item().key, value, this.scope()).subscribe({
      next: (res) => this.done(res, doneKey),
      error: (err: unknown) => this.fail(err),
    });
  }

  private begin(): void {
    this.busy.set(true);
    this.error.set(null);
    this.notice.set(null);
  }

  private done(res: SettingItem, noticeKey: string): void {
    this.busy.set(false);
    this.notice.set(this.i18n.t(noticeKey));
    this.updated.emit(res);
  }

  private fail(err: unknown): void {
    this.busy.set(false);
    this.error.set(apiErrorMessage(err));
  }
}
