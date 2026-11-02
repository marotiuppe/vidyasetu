import { Injectable, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, map, of, shareReplay, tap } from 'rxjs';

import { I18n } from '../i18n/i18n';
import { LevelAccess, SettingsApi } from './settings.api';

/**
 * App-wide settings state: which levels the user sees, which modules are switched off, and the
 * personal language (applied to the UI as soon as it is known).
 */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly api = inject(SettingsApi);
  private readonly i18n = inject(I18n);

  readonly levels = signal<LevelAccess[] | null>(null);
  readonly features = signal<Record<string, boolean>>({});

  private levelsLoaded = false;
  private levelsRequest$: Observable<void> | null = null;

  /** Fails open: a module is hidden only when the server says it is explicitly off. */
  isModuleOn(feature: string | undefined): boolean {
    return feature === undefined || this.features()[feature] !== false;
  }

  /**
   * Feature flags loaded once per session, for route guards. Fails open: when the request errors,
   * every module stays visible.
   */
  ensureLoaded(): Observable<void> {
    return this.levelsLoaded ? of(undefined) : this.fetchLevels();
  }

  /** Load levels and feature flags, then apply the personal language. Errors are ignored. */
  load(): void {
    this.fetchLevels().subscribe();
    this.api.list('user').subscribe({
      next: (items) => {
        const lang = items.find((i) => i.key === 'user.language');
        if (lang) this.i18n.use(lang.value);
      },
      error: () => undefined,
    });
  }

  private fetchLevels(): Observable<void> {
    this.levelsRequest$ ??= this.api.levels().pipe(
      tap({
        next: (res) => {
          this.levels.set(res.levels);
          this.features.set(res.features ?? {});
        },
        error: () => {
          this.levels.set(null);
          this.features.set({});
        },
      }),
      map(() => undefined),
      catchError(() => of(undefined)),
      finalize(() => {
        this.levelsLoaded = true;
        this.levelsRequest$ = null;
      }),
      shareReplay(1),
    );
    return this.levelsRequest$;
  }
}
