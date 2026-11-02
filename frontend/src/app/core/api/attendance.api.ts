import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1';

export type StudentMark = 'present' | 'absent' | 'leave';
export type StaffMark = StudentMark | 'half_day';

export interface SheetStudent {
  student_id: number;
  admission_no: string;
  full_name: string;
  roll_no: number | null;
  status: StudentMark | null;
  remark: string | null;
}

export interface SheetSummary {
  total: number;
  present: number;
  absent: number;
  leave: number;
  unmarked: number;
}

export interface AttendanceSheet {
  section_id: number;
  section_name: string;
  class_id: number;
  class_name: string;
  branch_id: number;
  date: string;
  academic_year_id: number;
  is_working_day: boolean;
  non_working_reason: string | null;
  students: SheetStudent[];
  summary: SheetSummary;
}

export interface SheetEntry {
  student_id: number;
  status: StudentMark;
  remark?: string | null;
}

export interface SectionSummary extends SheetSummary {
  branch_id: number;
  class_id: number;
  class_name: string;
  section_id: number;
  section_name: string;
  is_working_day: boolean;
}

export interface DailySummary {
  date: string;
  is_working_day: boolean;
  non_working_reason: string | null;
  sections: SectionSummary[];
  totals: SheetSummary;
}

export interface DayRecord<S extends string = StudentMark> {
  date: string;
  status: S;
  remark: string | null;
}

export interface StudentAttendanceReport {
  student_id: number;
  from: string;
  to: string;
  records: DayRecord[];
  summary: { present: number; absent: number; leave: number; marked_days: number; percentage: number | null };
}

export interface StaffRow {
  user_id: number;
  full_name: string;
  role: string;
  branch_id: number | null;
  status: StaffMark | null;
  remark: string | null;
}

export interface StaffSheet {
  date: string;
  is_working_day: boolean;
  non_working_reason: string | null;
  staff: StaffRow[];
}

export interface StaffEntry {
  user_id: number;
  status: StaffMark;
  remark?: string | null;
}

export interface Holiday {
  id: number;
  school_id: number;
  branch_id: number | null;
  date: string;
  name: string;
}

export interface NewHoliday {
  date: string;
  name: string;
  branch_id?: number | null;
}

/** Typed client for student attendance, staff attendance and holidays. */
@Injectable({ providedIn: 'root' })
export class AttendanceApi {
  private readonly http = inject(HttpClient);

  sheet(sectionId: number, date: string): Observable<AttendanceSheet> {
    const params = new HttpParams().set('section_id', sectionId).set('date', date);
    return this.http.get<AttendanceSheet>(`${API}/attendance/sheet`, { params });
  }

  saveSheet(sectionId: number, date: string, entries: SheetEntry[]): Observable<AttendanceSheet> {
    return this.http.put<AttendanceSheet>(`${API}/attendance/sheet`, { section_id: sectionId, date, entries });
  }

  dailySummary(date: string, branchId: number | null): Observable<DailySummary> {
    let params = new HttpParams().set('date', date);
    if (branchId) params = params.set('branch_id', branchId);
    return this.http.get<DailySummary>(`${API}/attendance/daily-summary`, { params });
  }

  studentReport(studentId: number, from: string, to: string): Observable<StudentAttendanceReport> {
    const params = new HttpParams().set('from', from).set('to', to);
    return this.http.get<StudentAttendanceReport>(`${API}/students/${studentId}/attendance`, { params });
  }

  exportCsv(sectionId: number, from: string, to: string): Observable<Blob> {
    const params = new HttpParams().set('section_id', sectionId).set('from', from).set('to', to);
    return this.http.get(`${API}/attendance/export`, { params, responseType: 'blob' });
  }

  staffSheet(date: string, branchId: number | null): Observable<StaffSheet> {
    let params = new HttpParams().set('date', date);
    if (branchId) params = params.set('branch_id', branchId);
    return this.http.get<StaffSheet>(`${API}/staff-attendance`, { params });
  }

  saveStaffSheet(date: string, branchId: number | null, entries: StaffEntry[]): Observable<StaffSheet> {
    const body: { date: string; branch_id?: number; entries: StaffEntry[] } = { date, entries };
    if (branchId) body.branch_id = branchId;
    return this.http.put<StaffSheet>(`${API}/staff-attendance`, body);
  }

  holidays(from: string, to: string): Observable<Holiday[]> {
    const params = new HttpParams().set('from', from).set('to', to);
    return this.http.get<Holiday[]>(`${API}/holidays`, { params });
  }

  addHoliday(body: NewHoliday): Observable<Holiday> {
    return this.http.post<Holiday>(`${API}/holidays`, body);
  }

  deleteHoliday(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/holidays/${id}`);
  }
}
