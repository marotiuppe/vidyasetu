import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, of, shareReplay } from 'rxjs';

import { AuthOptions, Role, TokenResponse, User } from './auth.models';

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

  /** `identifier` is a username, a mobile number or an email address. */
  login(identifier: string, password: string, rememberMe: boolean): Observable<User> {
    return this.http
      .post<TokenResponse>(`${API}/login`, { identifier, password, remember_me: rememberMe })
      .pipe(map((res) => this.accept(res)));
  }

  /** Public sign-in options (for example whether self-service password reset is on). */
  options(): Observable<AuthOptions> {
    return this.http.get<AuthOptions>(`${API}/options`);
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

  /** After a password change the server has ended all sessions: go to sign-in with a notice. */
  passwordChanged(): void {
    this.clear();
    void this.router.navigate(['/login'], { queryParams: { changed: 1 } });
  }

  /** Clear local session without calling the server (used when refresh fails). */
  clear(): void {
    this.accessToken = null;
    this.currentUser.set(null);
  }

  /** Re-read the signed-in user (for example after changing the password). */
  reloadUser(): Observable<User> {
    return this.http.get<User>(`${API}/me`).pipe(
      map((user) => {
        this.currentUser.update((current) => (current ? user : current));
        return user;
      }),
    );
  }

  /** Called when the server says a password change is required before anything else. */
  requirePasswordChange(): void {
    this.currentUser.update((user) => (user ? { ...user, must_change_password: true } : user));
  }

  private accept(res: TokenResponse): User {
    this.accessToken = res.access_token;
    this.currentUser.set(res.user);
    return res.user;
  }
}
