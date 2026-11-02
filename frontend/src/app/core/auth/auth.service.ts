import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, of, shareReplay } from 'rxjs';

import { Role, TokenResponse, User } from './auth.models';

const API = '/api/v1/auth';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  // The access token lives only in memory. The refresh token is an httpOnly cookie.
  private accessToken: string | null = null;
  private refreshInFlight$: Observable<string> | null = null;

  private readonly currentUser = signal<User | null>(null);
  readonly user = this.currentUser.asReadonly();
  readonly isLoggedIn = computed(() => this.currentUser() !== null);

  token(): string | null {
    return this.accessToken;
  }

  hasRole(...roles: Role[]): boolean {
    const user = this.currentUser();
    return user !== null && roles.includes(user.role);
  }

  login(email: string, password: string): Observable<User> {
    return this.http
      .post<TokenResponse>(`${API}/login`, { email, password })
      .pipe(map((res) => this.accept(res)));
  }

  /** Try to restore a session from the refresh cookie (page reload). */
  restore(): Observable<boolean> {
    return this.refresh().pipe(
      map(() => true),
      catchError(() => of(false)),
    );
  }

  /** Get a new access token. Concurrent callers share one request. */
  refresh(): Observable<string> {
    if (!this.refreshInFlight$) {
      this.refreshInFlight$ = this.http.post<TokenResponse>(`${API}/refresh`, {}).pipe(
        map((res) => {
          this.accept(res);
          return res.access_token;
        }),
        finalize(() => (this.refreshInFlight$ = null)),
        shareReplay(1),
      );
    }
    return this.refreshInFlight$;
  }

  logout(): void {
    this.http
      .post(`${API}/logout`, {})
      .pipe(catchError(() => of(null)))
      .subscribe();
    this.clear();
    void this.router.navigate(['/login']);
  }

  /** Clear local session without calling the server (used when refresh fails). */
  clear(): void {
    this.accessToken = null;
    this.currentUser.set(null);
  }

  private accept(res: TokenResponse): User {
    this.accessToken = res.access_token;
    this.currentUser.set(res.user);
    return res.user;
  }
}
