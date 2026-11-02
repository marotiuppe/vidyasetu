import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { SettingsService } from './settings.service';

/**
 * Open a module's route only while its feature switch is on (see the Settings levels). A module that
 * is switched off redirects to the dashboard. Fails open when the flags cannot be loaded.
 */
export const moduleGuard =
  (feature: string): CanActivateFn =>
  () => {
    const settings = inject(SettingsService);
    const router = inject(Router);
    return settings
      .ensureLoaded()
      .pipe(map(() => (settings.isModuleOn(feature) ? true : router.createUrlTree(['/']))));
  };
