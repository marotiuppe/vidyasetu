import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import {
  EMPTY,
  Observable,
  catchError,
  debounceTime,
  distinctUntilChanged,
  map,
  of,
  switchMap,
  tap,
} from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { ParentSummary, StudentsApi } from '../../core/api/students.api';

/** Search the school's existing parents and pick one (siblings share one parent login). */
@Component({
  selector: 'sms-parent-picker',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './parent-picker.html',
  styleUrl: './parent-picker.css',
})
export class ParentPicker {
  private readonly api = inject(StudentsApi);

  /** Id of the parent already chosen for this guardian, shown as pressed. */
  readonly selectedId = input<number | null>(null);
  readonly selected = output<ParentSummary>();

  protected readonly query = new FormControl('', { nonNullable: true });
  protected readonly results = signal<ParentSummary[]>([]);
  protected readonly searching = signal(false);
  protected readonly searched = signal(false);
  protected readonly searchError = signal<string | null>(null);

  constructor() {
    this.query.valueChanges
      .pipe(
        map((v) => v.trim()),
        debounceTime(300),
        distinctUntilChanged(),
        tap((q) => {
          this.searchError.set(null);
          if (q.length < 2) {
            this.results.set([]);
            this.searched.set(false);
            this.searching.set(false);
          }
        }),
        switchMap((q) => {
          if (q.length < 2) return EMPTY;
          this.searching.set(true);
          return this.search(q);
        }),
        takeUntilDestroyed(),
      )
      .subscribe((list) => {
        this.results.set(list);
        this.searching.set(false);
        this.searched.set(true);
      });
  }

  protected childrenText(p: ParentSummary): string {
    if (p.children.length === 0) return 'No children linked yet.';
    const names = p.children.map((c) =>
      c.class_name ? `${c.full_name} (${c.class_name})` : c.full_name,
    );
    return `Children already linked: ${names.join(', ')}`;
  }

  private search(q: string): Observable<ParentSummary[]> {
    return this.api.searchParents(q).pipe(
      catchError((err: unknown) => {
        this.searchError.set(apiErrorMessage(err));
        return of([] as ParentSummary[]);
      }),
    );
  }
}
