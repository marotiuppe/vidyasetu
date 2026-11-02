import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Role, User } from '../auth/auth.models';
import { Branch } from './academics.api';

const API = '/api/v1';

export type { Branch };

export interface School {
  id: number;
  name: string;
  code: string;
  board: string;
  is_active: boolean;
}

export interface NewSchool {
  name: string;
  code: string;
  board: string;
  owner_email: string;
  owner_full_name: string;
  owner_password: string;
}

export interface NewUser {
  email: string;
  full_name: string;
  phone?: string | null;
  password: string;
  role: Role;
  school_id?: number | null;
  branch_id?: number | null;
}

export interface UserFilters {
  q?: string;
  role?: Role | '';
}

/** Typed client for the admin console: schools, branches, users and own password. */
@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);

  schools(): Observable<School[]> {
    return this.http.get<School[]>(`${API}/schools`);
  }

  createSchool(body: NewSchool): Observable<School> {
    return this.http.post<School>(`${API}/schools`, body);
  }

  updateSchool(id: number, body: { name?: string; board?: string; is_active?: boolean }): Observable<School> {
    return this.http.patch<School>(`${API}/schools/${id}`, body);
  }

  branches(): Observable<Branch[]> {
    return this.http.get<Branch[]>(`${API}/branches`);
  }

  createBranch(body: { name: string; code: string; school_id?: number | null }): Observable<Branch> {
    return this.http.post<Branch>(`${API}/branches`, body);
  }

  updateBranch(id: number, body: { name?: string; is_active?: boolean }): Observable<Branch> {
    return this.http.patch<Branch>(`${API}/branches/${id}`, body);
  }

  users(filters: UserFilters = {}): Observable<User[]> {
    let params = new HttpParams();
    if (filters.q?.trim()) params = params.set('q', filters.q.trim());
    if (filters.role) params = params.set('role', filters.role);
    return this.http.get<User[]>(`${API}/users`, { params });
  }

  createUser(body: NewUser): Observable<User> {
    return this.http.post<User>(`${API}/users`, body);
  }

  updateUser(
    id: number,
    body: { full_name?: string; phone?: string | null; is_active?: boolean },
  ): Observable<User> {
    return this.http.patch<User>(`${API}/users/${id}`, body);
  }

  resetPassword(id: number, newPassword: string): Observable<void> {
    return this.http.post<void>(`${API}/users/${id}/reset-password`, { new_password: newPassword });
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${API}/auth/change-password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}
