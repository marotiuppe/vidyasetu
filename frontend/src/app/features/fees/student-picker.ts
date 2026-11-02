import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { Student, StudentsApi } from '../../core/api/students.api';
import { classSection, value } from './fee-labels';

/** Search active students by name or admission number and pick one. */
@Component({
  selector: 'sms-student-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-picker.html',
})
export class StudentPicker {
  private readonly api = inject(StudentsApi);

  readonly excludeIds = input<number[]>([]);
  readonly actionLabel = input('Add');
  readonly picked = output<Student>();

  protected readonly classSection = classSection;
  protected readonly query = signal('');
  protected readonly results = signal<Student[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    toObservable(this.query)
      .pipe(
        debounceTime(250),
        tap(() => this.error.set(null)),
        switchMap((q) => {
          const text = q.trim();
          if (text.length < 2) return of(null);
          this.loading.set(true);
          return this.api.list({ q: text, status: 'active' }, 1, 8).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((page) => {
        this.results.set(page?.items ?? []);
        this.loading.set(false);
      });
  }

  protected onInput(event: Event): void {
    this.query.set(value(event));
  }

  protected pick(student: Student): void {
    this.picked.emit(student);
  }

  protected excluded(id: number): boolean {
    return this.excludeIds().includes(id);
  }
}
