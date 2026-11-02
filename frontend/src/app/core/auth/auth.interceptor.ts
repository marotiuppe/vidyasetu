import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

const isAuthEndpoint = (url: string) => url.includes('/api/v1/auth/login') || url.includes('/api/v1/auth/refresh');

const withToken = (req: HttpRequest<unknown>, token: string | null) =>
  token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

/** Attach the access token; on a 401 refresh once and retry, otherwise sign out. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!req.url.startsWith('/api/') || isAuthEndpoint(req.url)) {
    return next(req);
  }

  return next(withToken(req, auth.token())).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }
      return auth.refresh().pipe(
        switchMap((token) => next(withToken(req, token))),
        catchError((refreshError: unknown) => {
          auth.clear();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
