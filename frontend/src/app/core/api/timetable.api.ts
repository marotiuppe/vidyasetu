import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ExamBranchService } from './exam-branch.service';

const API = '/api/v1/timetable';

/** Weekday numbers the server uses: 1 = Monday ... 7 = Sunday. The grid shows Monday to Saturday. */
export const GRID_DAYS = [1, 2, 3, 4, 5, 6];

export interface Period {
  id: number;
  name: string;
  sequence: number;
  /** "HH:MM:SS" */
  start_time: string;
  end_time: string;
  is_break: boolean;
}

export interface PeriodInput {
  name: string;
  sequence: number;
  start_time: string;
  end_time: string;
  is_break: boolean;
}

export interface TimetableEntry {
  id: number;
  weekday: number;
  period_id: number;
  subject_id: number | null;
  subject_name: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  room: string | null;
}

export interface SectionTimetable {
  section: { id: number; name: string; class_id: number; class_name: string };
  academic_year_id: number;
  periods: Period[];
  entries: TimetableEntry[];
}

export interface EntryInput {
  section_id: number;
  academic_year_id: number;
  weekday: number;
  period_id: number;
  subject_id: number;
  teacher_id: number | null;
  room: string | null;
}

/** One lesson in a teacher's, parent's or student's week. */
export interface WeekEntry {
  weekday: number;
  period_id: number;
  subject_name: string | null;
  teacher_name?: string | null;
  class_name?: string | null;
  section_name?: string | null;
  room: string | null;
}

export interface WeekTimetable {
  periods: Period[];
  entries: WeekEntry[];
}

/** Typed client for the timetable: periods, section grids and read-only weeks. */
@Injectable({ providedIn: 'root' })
export class TimetableApi {
  private readonly http = inject(HttpClient);
  private readonly branch = inject(ExamBranchService);

  periods(): Observable<Period[]> {
    return this.http.get<Period[]>(`${API}/periods`, { params: this.branchParams() });
  }

  createPeriod(body: PeriodInput): Observable<Period> {
    return this.http.post<Period>(`${API}/periods`, body, { params: this.branchParams() });
  }

  updatePeriod(id: number, body: Partial<PeriodInput>): Observable<Period> {
    return this.http.patch<Period>(`${API}/periods/${id}`, body);
  }

  deletePeriod(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/periods/${id}`);
  }

  section(sectionId: number, academicYearId: number): Observable<SectionTimetable> {
    return this.http.get<SectionTimetable>(`${API}/sections/${sectionId}`, {
      params: new HttpParams().set('academic_year_id', academicYearId),
    });
  }

  saveEntry(body: EntryInput): Observable<TimetableEntry> {
    return this.http.put<TimetableEntry>(`${API}/entries`, body);
  }

  deleteEntry(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/entries/${id}`);
  }

  /** The signed-in teacher's own week. */
  mine(): Observable<WeekTimetable> {
    return this.http.get<WeekTimetable>(`${API}/me`);
  }

  /** A child's week (parent and student accounts). */
  student(studentId: number): Observable<WeekTimetable> {
    return this.http.get<WeekTimetable>(`${API}/students/${studentId}`);
  }

  private branchParams(): HttpParams {
    const id = this.branch.param();
    return id === null ? new HttpParams() : new HttpParams().set('branch_id', id);
  }
}

/** "HH:MM:SS" (or "HH:MM") as "HH:MM". */
export function shortTime(value: string): string {
  return value.slice(0, 5);
}
