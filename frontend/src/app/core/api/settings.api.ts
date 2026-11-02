import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1/settings';

export type SettingLevel = 'platform' | 'school' | 'branch' | 'user';
export type SettingType =
  'string' | 'text' | 'int' | 'bool' | 'choice' | 'date' | 'email' | 'time' | 'secret';
export type SettingSource = 'own' | 'branch' | 'school' | 'platform' | 'env' | 'default';
export type SettingValue = string | number | boolean | null;

export interface LevelAccess {
  level: SettingLevel;
  can_edit: boolean;
}

export interface LevelsResponse {
  levels: LevelAccess[];
  /** Module switches such as `fees`: false means the module is off for this school. */
  features: Record<string, boolean>;
}

export interface SettingItem {
  key: string;
  group: string;
  label: string;
  help: string;
  type: SettingType;
  choices: string[] | null;
  min: number | null;
  max: number | null;
  secret: boolean;
  /** Always null for secrets. */
  value: SettingValue;
  is_set: boolean;
  source: SettingSource;
  default: SettingValue;
  can_edit: boolean;
  updated_by_name: string | null;
  updated_at: string | null;
}

/** Which school or branch a read or write applies to (platform admin and owner only). */
export interface SettingScope {
  school_id?: number | null;
  branch_id?: number | null;
}

export type IntegrationName = 'sms' | 'whatsapp' | 'smtp' | 'razorpay' | 'storage';

export interface IntegrationTestResult {
  ok: boolean;
  detail: string;
}

function scopeParams(scope: SettingScope): HttpParams {
  let params = new HttpParams();
  if (scope.school_id != null) params = params.set('school_id', scope.school_id);
  if (scope.branch_id != null) params = params.set('branch_id', scope.branch_id);
  return params;
}

/** Typed client for the settings registry. */
@Injectable({ providedIn: 'root' })
export class SettingsApi {
  private readonly http = inject(HttpClient);

  levels(): Observable<LevelsResponse> {
    return this.http.get<LevelsResponse>(`${API}/levels`);
  }

  list(level: SettingLevel, scope: SettingScope = {}): Observable<SettingItem[]> {
    return this.http.get<SettingItem[]>(API, {
      params: scopeParams(scope).set('level', level),
    });
  }

  update(
    level: SettingLevel,
    key: string,
    value: SettingValue,
    scope: SettingScope = {},
  ): Observable<SettingItem> {
    const body: { value: SettingValue; school_id?: number; branch_id?: number } = { value };
    if (scope.school_id != null) body.school_id = scope.school_id;
    if (scope.branch_id != null) body.branch_id = scope.branch_id;
    return this.http.put<SettingItem>(`${API}/${level}/${encodeURIComponent(key)}`, body);
  }

  reset(level: SettingLevel, key: string, scope: SettingScope = {}): Observable<SettingItem> {
    return this.http.delete<SettingItem>(`${API}/${level}/${encodeURIComponent(key)}`, {
      params: scopeParams(scope),
    });
  }

  testIntegration(
    name: IntegrationName,
    scope: SettingScope = {},
  ): Observable<IntegrationTestResult> {
    return this.http.post<IntegrationTestResult>(
      `${API}/school/integrations/${name}/test`,
      {},
      { params: scopeParams(scope) },
    );
  }
}
