import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';

import { EN } from './en';
import { MR } from './mr';

export type Lang = 'en' | 'mr';

const DICTIONARIES: Record<Lang, Record<string, string>> = { en: EN, mr: MR };

/** Active UI language and string lookup. English is the fallback for any missing key. */
@Injectable({ providedIn: 'root' })
export class I18n {
  private readonly doc = inject(DOCUMENT);
  private readonly current = signal<Lang>('en');
  readonly lang = this.current.asReadonly();

  /** Switch language; unknown codes are ignored. */
  use(code: unknown): void {
    const lang: Lang = code === 'mr' ? 'mr' : code === 'en' ? 'en' : this.current();
    this.current.set(lang);
    this.doc.documentElement.lang = lang;
  }

  /** Look up `key`; `{name}` placeholders are filled from `params`. Reads the language signal. */
  readonly t = (key: string, params?: Record<string, string | number>): string => {
    const text = DICTIONARIES[this.current()][key] ?? EN[key] ?? key;
    return params ? text.replace(/\{(\w+)\}/g, (_m, p: string) => String(params[p] ?? '')) : text;
  };

  /** A server-defined string (label, group): translated from `prefix.<id>` when present, else the server text. */
  readonly server = (prefix: string, id: string, fallback: string): string =>
    DICTIONARIES[this.current()][`${prefix}.${id}`] ?? fallback;
}
