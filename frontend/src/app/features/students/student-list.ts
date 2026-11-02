import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toObservable, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, debounceTime, filter, of, switchMap, tap } from 'rxjs';

import { AcademicYear, AcademicsApi, Branch, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  STATUSES,
  Student,
  StudentFilters,
  StudentStatus,
  StudentsApi,
} from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { canWriteStudents, isStudentSelfService } from '../../core/auth/permissions';
import { Icon } from '../../core/ui/icon';
import { StudentImport } from './student-import';
import { initials, statusLabel } from './student-labels';

const PAGE_SIZE = 25;

interface Filters {
  q: string;
  branchId: number;
  classId: number;
  sectionId: number;
  yearId: number;
  status: StudentStatus | '';
}

@Component({
  selector: 'sms-student-list',
  imports: [RouterLink, Icon, StudentImport],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './student-list.html',
  styleUrl: './student-list.css',
})
export class StudentList {
  private readonly api = inject(StudentsApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);

  protected readonly statuses = STATUSES;
  protected readonly statusLabel = statusLabel;
  protected readonly initials = initials;

  protected readonly canWrite = canWriteStudents(this.auth);
  protected readonly selfService = isStudentSelfService(this.auth);
  protected readonly title = this.auth.hasRole('student')
    ? 'My profile'
    : this.selfService
      ? 'My children'
      : 'Student records';
  protected readonly canPickBranch = !this.selfService && this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly years = signal<AcademicYear[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);

  protected readonly filters = signal<Filters>({
    q: '',
    branchId: 0,
    classId: 0,
    sectionId: 0,
    yearId: 0,
    status: '',
  });
  protected readonly page = signal(1);
  private readonly ready = signal(false);

  protected readonly items = signal<Student[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly exporting = signal(false);
  protected readonly showImport = signal(false);
  protected readonly notice = signal<string | null>(null);
  private readonly reloadTick = signal(0);

  protected readonly classOptions = computed(() => {
    const b = this.filters().branchId;
    return b ? this.classes().filter((c) => c.branch_id === b) : this.classes();
  });
  protected readonly sectionOptions = computed(() => {
    const c = this.filters().classId;
    return c ? this.sections().filter((s) => s.class_id === c) : [];
  });
  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));

  constructor() {
    if (this.selfService) {
      this.ready.set(true);
    } else {
      this.academics.years().subscribe({
        next: (y) => {
          this.years.set(y);
          this.filters.update((f) => ({ ...f, yearId: y.find((v) => v.is_current)?.id ?? 0 }));
          this.ready.set(true);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.ready.set(true);
        },
      });
      this.academics.classes().subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
      this.academics.sections().subscribe({ next: (s) => this.sections.set(s), error: () => undefined });
      if (this.canPickBranch) {
        this.academics.branches().subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
      }
    }

    toObservable(
      computed(() => ({
        ready: this.ready(),
        f: this.filters(),
        page: this.page(),
        tick: this.reloadTick(),
      })),
    )
      .pipe(
        filter((s) => s.ready),
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((s) =>
          this.api.list(this.toApiFilters(s.f), s.page, PAGE_SIZE).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        if (res) {
          this.items.set(res.items);
          this.total.set(res.total);
        } else {
          this.items.set([]);
          this.total.set(0);
        }
        this.loading.set(false);
      });
  }

  protected onSearch(e: Event): void {
    this.patch({ q: (e.target as HTMLInputElement).value });
  }

  protected onSelect(key: 'branchId' | 'classId' | 'sectionId' | 'yearId', e: Event): void {
    const value = Number((e.target as HTMLSelectElement).value);
    if (key === 'branchId') this.patch({ branchId: value, classId: 0, sectionId: 0 });
    else if (key === 'classId') this.patch({ classId: value, sectionId: 0 });
    else this.patch({ [key]: value });
  }

  protected onStatus(e: Event): void {
    this.patch({ status: (e.target as HTMLSelectElement).value as StudentStatus | '' });
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    if (this.to() < this.total()) this.page.update((p) => p + 1);
  }

  protected exportCsv(): void {
    this.exporting.set(true);
    this.error.set(null);
    this.api.exportCsv(this.toApiFilters(this.filters())).subscribe({
      next: (blob) => {
        this.api.saveBlob(blob, 'students.csv');
        this.exporting.set(false);
      },
      error: (err: unknown) => {
        this.exporting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected imported(created: number): void {
    if (created > 0) {
      this.notice.set(`Imported ${created} student${created === 1 ? '' : 's'}.`);
      this.page.set(1);
      this.reloadTick.update((t) => t + 1);
    }
  }

  private patch(change: Partial<Filters>): void {
    this.filters.update((f) => ({ ...f, ...change }));
    this.page.set(1);
  }

  private toApiFilters(f: Filters): StudentFilters {
    return {
      q: f.q,
      branch_id: f.branchId || null,
      class_id: f.classId || null,
      section_id: f.sectionId || null,
      academic_year_id: f.yearId || null,
      status: f.status,
    };
  }
}
