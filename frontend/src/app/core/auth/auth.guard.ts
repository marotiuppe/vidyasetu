import { inject } from '@angular/core';
import { CanActivateChildFn, CanActivateFn, CanMatchFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { PrivacyApi } from '../api/privacy.api';

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

const MFA_PATH = '/account/mfa';

/** A user whose policy requires two-factor stays on the setup page until it is enabled. */
export const mfaSetupGuard: CanActivateChildFn = (_route, state) => {
  const auth = inject(AuthService);
  if (!auth.user()?.mfa_setup_required || state.url.startsWith(MFA_PATH)) {
    return true;
  }
  return inject(Router).createUrlTree([MFA_PATH]);
};

/**
 * Block the app until the current Privacy Policy and Terms of Use are accepted.
 * Checked once per session; fails open when the check itself errors.
 */
export const policyGuard: CanActivateChildFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (state.url.startsWith(MFA_PATH) || auth.user()?.mfa_setup_required) {
    return true;
  }
  const pending = auth.policyGate();
  if (pending !== null) {
    return pending ? router.createUrlTree(['/accept-policies']) : true;
  }
  return inject(PrivacyApi)
    .policies()
    .pipe(
      map((res) => {
        auth.setPoliciesPending(res.pending);
        return res.pending ? router.createUrlTree(['/accept-policies']) : true;
      }),
      catchError(() => of(true)),
    );
};
