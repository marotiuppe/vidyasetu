import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ExamBranchService } from './exam-branch.service';

const API = '/api/v1/homework';

export interface Homework {
  id: number;
  academic_year_id: number;
  section_id: number;
  class_name: string | null;
  section_name: string | null;
  subject_id: number;
  subject_name: string | null;
  teacher_name: string | null;
  title: string;
  description: string | null;
  /** ISO date, YYYY-MM-DD */
  assigned_on: string;
  due_date: string;
}

export interface HomeworkInput {
  academic_year_id: number;
  section_id: number;
  subject_id: number;
  title: string;
  description: string | null;
  assigned_on: string;
  due_date: string;
}

export type HomeworkUpdate = Partial<Omit<HomeworkInput, 'academic_year_id' | 'section_id'>>;

export interface HomeworkPage {
  items: Homework[];
  total: number;
  page: number;
  page_size: number;
}

export interface HomeworkFilters {
  section_id?: number;
  subject_id?: number;
  from?: string;
  to?: string;
  /** Parents and students must pass the child. */
  student_id?: number;
}

/** Typed client for homework. */
@Injectable({ providedIn: 'root' })
export class HomeworkApi {
  private readonly http = inject(HttpClient);
  private readonly branch = inject(ExamBranchService);

  list(filters: HomeworkFilters, page: number, pageSize: number): Observable<HomeworkPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, value);
    }
    const branchId = this.branch.param();
    if (branchId !== null) params = params.set('branch_id', branchId);
    return this.http.get<HomeworkPage>(API, { params });
  }

  create(body: HomeworkInput): Observable<Homework> {
    return this.http.post<Homework>(API, body);
  }

  update(id: number, body: HomeworkUpdate): Observable<Homework> {
    return this.http.patch<Homework>(`${API}/${id}`, body);
  }

  remove(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/${id}`);
  }
}
