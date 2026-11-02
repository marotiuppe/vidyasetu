import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1';

export type Gender = 'male' | 'female' | 'other';
export type Relation = 'father' | 'mother' | 'guardian' | 'other';
export type StudentStatus = 'active' | 'left' | 'transferred' | 'passed_out';

export const GENDERS: Gender[] = ['male', 'female', 'other'];
export const RELATIONS: Relation[] = ['father', 'mother', 'guardian', 'other'];
export const STATUSES: StudentStatus[] = ['active', 'left', 'transferred', 'passed_out'];

export interface Enrollment {
  id: number;
  student_id: number;
  academic_year_id: number;
  academic_year_name: string;
  class_id: number;
  class_name: string;
  section_id: number | null;
  section_name: string | null;
  roll_no: number | null;
}

export interface PrimaryGuardian {
  full_name: string;
  phone: string;
  relation: Relation;
}

export interface Student {
  id: number;
  school_id: number;
  branch_id: number;
  admission_no: string;
  first_name: string;
  last_name: string;
  full_name: string;
  gender: Gender;
  date_of_birth: string;
  admission_date: string;
  status: StudentStatus;
  user_id: number | null;
  current_enrollment: Enrollment | null;
  primary_guardian: PrimaryGuardian | null;
}

export interface Guardian {
  id: number;
  student_id: number;
  full_name: string;
  relation: Relation;
  phone: string;
  email: string | null;
  is_primary: boolean;
  user_id: number | null;
  has_login: boolean;
}

export interface StudentDetail extends Student {
  address: string | null;
  previous_school: string | null;
  guardians: Guardian[];
  enrollments: Enrollment[];
}

export interface StudentPage {
  items: Student[];
  total: number;
  page: number;
  page_size: number;
}

export interface StudentFilters {
  branch_id?: number | null;
  class_id?: number | null;
  section_id?: number | null;
  academic_year_id?: number | null;
  status?: StudentStatus | '';
  q?: string;
}

export interface GuardianInput {
  full_name: string;
  relation: Relation;
  phone: string;
  email?: string | null;
  is_primary?: boolean;
}

export interface EnrollmentInput {
  academic_year_id: number;
  class_id: number;
  section_id?: number | null;
  roll_no?: number | null;
}

export interface NewStudent {
  branch_id?: number | null;
  first_name: string;
  last_name: string;
  gender: Gender;
  date_of_birth: string;
  admission_date?: string | null;
  admission_no?: string | null;
  address?: string | null;
  previous_school?: string | null;
  guardians: GuardianInput[];
  enrollment?: EnrollmentInput | null;
}

export interface StudentUpdate {
  first_name?: string;
  last_name?: string;
  gender?: Gender;
  date_of_birth?: string;
  admission_date?: string;
  address?: string | null;
  previous_school?: string | null;
  status?: StudentStatus;
}

export interface ImportRow {
  first_name: string;
  last_name: string;
  gender: string;
  date_of_birth: string;
  admission_date?: string;
  admission_no?: string;
  address?: string;
  guardian_name: string;
  guardian_phone: string;
  guardian_relation?: string;
  class?: string;
  section?: string;
  roll_no?: string;
}

export interface ImportResult {
  created: number;
  failed: number;
  errors: { row: number; message: string }[];
}

function filterParams(f: StudentFilters): HttpParams {
  let params = new HttpParams();
  if (f.branch_id) params = params.set('branch_id', f.branch_id);
  if (f.class_id) params = params.set('class_id', f.class_id);
  if (f.section_id) params = params.set('section_id', f.section_id);
  if (f.academic_year_id) params = params.set('academic_year_id', f.academic_year_id);
  if (f.status) params = params.set('status', f.status);
  if (f.q?.trim()) params = params.set('q', f.q.trim());
  return params;
}

/** Typed client for students, guardians, enrolments, logins, import and export. */
@Injectable({ providedIn: 'root' })
export class StudentsApi {
  private readonly http = inject(HttpClient);

  list(filters: StudentFilters, page: number, pageSize: number): Observable<StudentPage> {
    const params = filterParams(filters).set('page', page).set('page_size', pageSize);
    return this.http.get<StudentPage>(`${API}/students`, { params });
  }

  get(id: number): Observable<StudentDetail> {
    return this.http.get<StudentDetail>(`${API}/students/${id}`);
  }

  create(body: NewStudent): Observable<StudentDetail> {
    return this.http.post<StudentDetail>(`${API}/students`, body);
  }

  update(id: number, body: StudentUpdate): Observable<StudentDetail> {
    return this.http.patch<StudentDetail>(`${API}/students/${id}`, body);
  }

  setEnrollment(id: number, body: EnrollmentInput): Observable<StudentDetail> {
    return this.http.put<StudentDetail>(`${API}/students/${id}/enrollment`, body);
  }

  addGuardian(studentId: number, body: GuardianInput): Observable<Guardian> {
    return this.http.post<Guardian>(`${API}/students/${studentId}/guardians`, body);
  }

  updateGuardian(id: number, body: Partial<GuardianInput>): Observable<Guardian> {
    return this.http.patch<Guardian>(`${API}/guardians/${id}`, body);
  }

  deleteGuardian(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/guardians/${id}`);
  }

  createGuardianLogin(id: number, email: string, password: string): Observable<Guardian> {
    return this.http.post<Guardian>(`${API}/guardians/${id}/login`, { email, password });
  }

  removeGuardianLogin(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/guardians/${id}/login`);
  }

  createStudentLogin(id: number, email: string, password: string): Observable<StudentDetail> {
    return this.http.post<StudentDetail>(`${API}/students/${id}/login`, { email, password });
  }

  importRows(body: {
    branch_id?: number | null;
    academic_year_id?: number | null;
    rows: ImportRow[];
  }): Observable<ImportResult> {
    return this.http.post<ImportResult>(`${API}/students/import`, body);
  }

  exportCsv(filters: StudentFilters): Observable<Blob> {
    return this.http.get(`${API}/students/export`, { params: filterParams(filters), responseType: 'blob' });
  }

  /** Save a blob through a temporary object URL and anchor. */
  saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
}
