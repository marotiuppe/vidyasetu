import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

const isAuthEndpoint = (url: string) =>
  url.includes('/api/v1/auth/login') || url.includes('/api/v1/auth/refresh');

const withToken = (req: HttpRequest<unknown>, token: string | null) =>
  token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

/** The server answers 403 with this code while the user must choose a new password. */
const isPasswordChangeRequired = (error: HttpErrorResponse): boolean => {
  const body: unknown = error.error;
  return (
    typeof body === 'object' &&
    body !== null &&
    (body as { code?: unknown }).code === 'password_change_required'
  );
};

/** The server answers 403 with this code until two-factor sign-in has been set up. */
const isMfaSetupRequired = (error: HttpErrorResponse): boolean => {
  const body: unknown = error.error;
  return (
    typeof body === 'object' &&
    body !== null &&
    (body as { code?: unknown }).code === 'mfa_setup_required'
  );
};

/**
 * Attach the access token and the CSRF header (`X-Requested-With`) to every API call.
 * On a 401 refresh once and retry (concurrent 401s share one refresh call), otherwise sign out.
 * A 403 `password_change_required` sends the user to the forced password screen.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/')) {
    return next(req);
  }

  const auth = inject(AuthService);
  const router = inject(Router);
  const withCsrf = req.clone({ setHeaders: { 'X-Requested-With': 'XMLHttpRequest' } });

  if (isAuthEndpoint(req.url)) {
    return next(withCsrf);
  }

  const sentWith = auth.token();
  return next(withToken(withCsrf, sentWith)).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }
      if (error.status === 403 && isPasswordChangeRequired(error)) {
        auth.requirePasswordChange();
        void router.navigate(['/change-password']);
        return throwError(() => error);
      }
      if (error.status === 403 && isMfaSetupRequired(error)) {
        auth.requireMfaSetup();
        void router.navigate(['/account/mfa']);
        return throwError(() => error);
      }
      if (error.status !== 401) {
        return throwError(() => error);
      }
      // Another request already refreshed the token while this one was in flight: just retry.
      const current = auth.token();
      if (current !== null && current !== sentWith) {
        return next(withToken(withCsrf, current));
      }
      return auth.refresh().pipe(
        switchMap((token) => next(withToken(withCsrf, token))),
        catchError((refreshError: unknown) => {
          auth.clear();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
