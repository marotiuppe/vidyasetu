import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1';

export interface Branch {
  id: number;
  school_id: number;
  name: string;
  code: string;
  is_active: boolean;
}

export interface AcademicYear {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

export interface SchoolClass {
  id: number;
  branch_id: number;
  name: string;
  level: number;
}

export interface Section {
  id: number;
  branch_id: number;
  class_id: number;
  name: string;
}

@Injectable({ providedIn: 'root' })
export class AcademicsApi {
  private readonly http = inject(HttpClient);

  branches(): Observable<Branch[]> {
    return this.http.get<Branch[]>(`${API}/branches`);
  }

  years(): Observable<AcademicYear[]> {
    return this.http.get<AcademicYear[]>(`${API}/academic-years`);
  }

  createYear(body: Omit<AcademicYear, 'id'>): Observable<AcademicYear> {
    return this.http.post<AcademicYear>(`${API}/academic-years`, body);
  }

  makeYearCurrent(id: number): Observable<AcademicYear> {
    return this.http.patch<AcademicYear>(`${API}/academic-years/${id}`, { is_current: true });
  }

  classes(): Observable<SchoolClass[]> {
    return this.http.get<SchoolClass[]>(`${API}/classes`);
  }

  createClass(body: { name: string; level: number; branch_id: number | null }): Observable<SchoolClass> {
    return this.http.post<SchoolClass>(`${API}/classes`, body);
  }

  sections(): Observable<Section[]> {
    return this.http.get<Section[]>(`${API}/sections`);
  }

  createSection(body: { class_id: number; name: string }): Observable<Section> {
    return this.http.post<Section>(`${API}/sections`, body);
  }
}
