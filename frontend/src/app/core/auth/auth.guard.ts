import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
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

/** Allow only the given roles. UX only; the backend enforces access. */
export const roleGuard =
  (...roles: Role[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    return auth.hasRole(...roles) ? true : inject(Router).createUrlTree(['/']);
  };
