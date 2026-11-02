import { inject } from '@angular/core';
import { CanActivateChildFn, CanActivateFn, CanMatchFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { Role } from './auth.models';
import { AuthService } from './auth.service';

/** Allow signed-in users only; tries to restore the session after a page reload. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isLoggedIn()) {
    return true;
  }
  return auth.restore().pipe(map((ok) => (ok ? true : router.createUrlTree(['/login']))));
};

/**
 * Match the public landing route only for visitors without a session.
 * A signed-in user (or one restorable from the refresh cookie) skips it and gets the dashboard.
 */
export const publicOnlyMatch: CanMatchFn = () => {
  const auth = inject(AuthService);
  if (auth.isLoggedIn()) {
    return false;
  }
  return auth.restore().pipe(map((ok) => !ok));
};

/** Allow only the given roles. UX only; the backend enforces access. */
export const roleGuard =
  (...roles: Role[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    return auth.hasRole(...roles) ? true : inject(Router).createUrlTree(['/']);
  };

/**
 * Keep a user who must change the password inside the forced password screen.
 * Applied to the shell's children, so every app page is blocked (logout stays on that screen).
 */
export const mustChangePasswordGuard: CanActivateChildFn = () => {
  const auth = inject(AuthService);
  return auth.user()?.must_change_password
    ? inject(Router).createUrlTree(['/change-password'])
    : true;
};
