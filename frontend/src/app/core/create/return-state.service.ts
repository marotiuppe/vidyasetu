import { Injectable, inject } from '@angular/core';
import { Params, Router } from '@angular/router';

import { CREATE_ROUTES, CreateKind } from './create-new';

/** What a page left behind when it sent the user to create a missing record. */
export interface PendingReturn {
  returnUrl: string;
  kind: CreateKind;
  /** Form values of the page, as they were before the user chose "Create new...". */
  draft: unknown;
  /** Id of the record that was saved, or null when the user cancelled. */
  createdId: number | null;
}

/**
 * Carries a half-filled form across one trip to a create screen and back.
 * In memory only: drafts can hold a minor's personal data, so nothing is written to storage or the URL
 * (the URL carries the return path and the record kind only).
 */
@Injectable({ providedIn: 'root' })
export class ReturnStateService {
  private readonly router = inject(Router);
  private pending: PendingReturn | null = null;

  /** Keep this page's draft, then open the create screen for the record kind. */
  openCreate(kind: CreateKind, draft: unknown, from: string, extra: Params = {}): void {
    const returnUrl = this.router.url;
    this.pending = { returnUrl, kind, draft, createdId: null };
    void this.router.navigate([CREATE_ROUTES[kind]], {
      queryParams: { create: kind, returnTo: returnUrl, from, ...extra },
    });
  }

  /** The create screen saved a record: go back, where the page selects it. */
  finish(returnTo: string, kind: CreateKind, createdId: number): void {
    this.remember(returnTo, kind, createdId);
    void this.router.navigateByUrl(returnTo);
  }

  /** The create screen was left without saving: go back with nothing selected. */
  cancel(returnTo: string, kind: CreateKind): void {
    this.remember(returnTo, kind, null);
    void this.router.navigateByUrl(returnTo);
  }

  /** On start-up a page asks for its state. Returns it only when the URL is the one that was left. */
  take(url: string): PendingReturn | null {
    const p = this.pending;
    if (!p || p.returnUrl !== url) return null;
    this.pending = null;
    return p;
  }

  private remember(returnTo: string, kind: CreateKind, createdId: number | null): void {
    const draft = this.pending?.returnUrl === returnTo ? this.pending.draft : null;
    this.pending = { returnUrl: returnTo, kind, draft, createdId };
  }
}

/**
 * Filter or form values for a page coming back from a create screen: the kept ids, with the record
 * that was created selected in place of its field (nothing after a cancel). A parent dropdown that
 * changed clears the dropdowns below it, as it does on screen.
 */
export function restoreIds<T extends object>(
  back: PendingReturn,
  draft: T,
  fields: Partial<Record<CreateKind, keyof T>>,
): T {
  const out = { ...draft } as Record<string, unknown>;
  const idOf = (v: unknown): number => (typeof v === 'number' && v > 0 ? v : 0);
  const names = fields as Partial<Record<CreateKind, string>>;
  for (const kind of Object.keys(names) as CreateKind[]) {
    const key = names[kind];
    if (key) out[key] = kind === back.kind ? (back.createdId ?? 0) : idOf(out[key]);
  }
  if (back.kind === 'branch' && names.class) out[names.class] = 0;
  if ((back.kind === 'branch' || back.kind === 'class') && names.section) out[names.section] = 0;
  return out as unknown as T;
}
