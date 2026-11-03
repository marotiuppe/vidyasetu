import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1/notices';

export type NoticeCategory = 'general' | 'academic' | 'event' | 'holiday' | 'urgent';
export type NoticeTargetType = 'school' | 'branch' | 'class' | 'section';

/** Notice categories in the order the forms show them (names come from `CATEGORY_KEYS`). */
export const NOTICE_CATEGORIES: { value: NoticeCategory }[] = [
  { value: 'general' },
  { value: 'academic' },
  { value: 'event' },
  { value: 'holiday' },
  { value: 'urgent' },
];

export interface NoticeAuthor {
  id: number;
  full_name: string;
  role: string;
}

export interface Notice {
  id: number;
  title: string;
  body: string;
  category: NoticeCategory;
  is_pinned: boolean;
  expires_on: string | null;
  is_expired: boolean;
  target_type: NoticeTargetType;
  target_label: string;
  branch_id: number | null;
  class_id: number | null;
  section_id: number | null;
  author: NoticeAuthor;
  created_at: string;
  is_read: boolean;
  read_count: number | null;
  can_edit: boolean;
}

export interface NoticePage {
  items: Notice[];
  total: number;
  page: number;
  page_size: number;
  unread_count: number;
}

export interface NoticeFilters {
  category?: NoticeCategory | '';
  q?: string;
  unread_only?: boolean;
  pinned?: boolean;
  page?: number;
  page_size?: number;
}

export interface NewNotice {
  title: string;
  body: string;
  category: NoticeCategory;
  is_pinned?: boolean;
  expires_on?: string | null;
  target: {
    type: NoticeTargetType;
    branch_id?: number;
    class_id?: number;
    section_id?: number;
  };
}

export interface NoticeUpdate {
  title?: string;
  body?: string;
  category?: NoticeCategory;
  is_pinned?: boolean;
  expires_on?: string | null;
}

/** Typed client for the noticeboard. */
@Injectable({ providedIn: 'root' })
export class NoticesApi {
  private readonly http = inject(HttpClient);

  list(filters: NoticeFilters = {}): Observable<NoticePage> {
    let params = new HttpParams();
    if (filters.category) params = params.set('category', filters.category);
    if (filters.q) params = params.set('q', filters.q);
    if (filters.unread_only) params = params.set('unread_only', true);
    if (filters.pinned) params = params.set('pinned', true);
    if (filters.page) params = params.set('page', filters.page);
    if (filters.page_size) params = params.set('page_size', filters.page_size);
    return this.http.get<NoticePage>(API, { params });
  }

  get(id: number): Observable<Notice> {
    return this.http.get<Notice>(`${API}/${id}`);
  }

  create(body: NewNotice): Observable<Notice> {
    return this.http.post<Notice>(API, body);
  }

  update(id: number, body: NoticeUpdate): Observable<Notice> {
    return this.http.patch<Notice>(`${API}/${id}`, body);
  }

  remove(id: number): Observable<void> {
    return this.http.delete<void>(`${API}/${id}`);
  }

  markRead(id: number): Observable<void> {
    return this.http.post<void>(`${API}/${id}/read`, {});
  }

  markAllRead(): Observable<void> {
    return this.http.post<void>(`${API}/read-all`, {});
  }

  unreadCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(`${API}/unread-count`);
  }
}
