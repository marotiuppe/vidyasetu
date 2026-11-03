import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const API = '/api/v1';

/** One hit. `url` is an app route (for example `/students/12`); the server only returns routes it knows. */
export interface SearchItem {
  id: number | string;
  title: string;
  subtitle: string | null;
  url: string;
}

/** Hits of one kind. The server decides which kinds the signed-in user may see. */
export interface SearchGroup {
  /** students, guardians, receipts, invoices, notices or admissions; unknown kinds are shown as sent. */
  type: string;
  items: SearchItem[];
}

export interface SearchResults {
  q: string;
  groups: SearchGroup[];
}

/** Typed client for the global search in the top bar. */
@Injectable({ providedIn: 'root' })
export class SearchApi {
  private readonly http = inject(HttpClient);

  /** The query must be 2 to 60 characters; `limit` is per group (1 to 10). */
  search(q: string, limit = 5): Observable<SearchResults> {
    const params = new HttpParams().set('q', q).set('limit', limit);
    return this.http.get<SearchResults>(`${API}/search`, { params });
  }
}
