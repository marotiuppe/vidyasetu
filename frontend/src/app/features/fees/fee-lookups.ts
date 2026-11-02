import { Injectable, computed, inject, signal } from '@angular/core';

import {
  AcademicYear,
  AcademicsApi,
  Branch,
  SchoolClass,
  Section,
} from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';

/** Academic years, classes, sections and branches shared by the fee tabs (loaded once). */
@Injectable({ providedIn: 'root' })
export class FeeLookups {
  private readonly academics = inject(AcademicsApi);
  private started = false;
  private branchesStarted = false;

  readonly years = signal<AcademicYear[]>([]);
  readonly classes = signal<SchoolClass[]>([]);
  readonly sections = signal<Section[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly loaded = signal(false);
  readonly error = signal<string | null>(null);

  readonly currentYearId = computed(
    () => this.years().find((y) => y.is_current)?.id ?? this.years()[0]?.id ?? 0,
  );

  load(): void {
    if (this.started) return;
    this.started = true;
    this.academics.years().subscribe({
      next: (y) => {
        this.years.set(y);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.loaded.set(true);
      },
    });
    this.academics
      .classes()
      .subscribe({ next: (c) => this.classes.set(c), error: () => undefined });
    this.academics
      .sections()
      .subscribe({ next: (s) => this.sections.set(s), error: () => undefined });
  }

  /** Fetch the lists again, for a page back from a create screen (a new record is not in the cache). */
  refresh(): void {
    this.started = false;
    this.load();
    if (this.branchesStarted) {
      this.branchesStarted = false;
      this.loadBranches();
    }
  }

  loadBranches(): void {
    if (this.branchesStarted) return;
    this.branchesStarted = true;
    this.academics
      .branches()
      .subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
  }

  classesOf(branchId: number): SchoolClass[] {
    return branchId ? this.classes().filter((c) => c.branch_id === branchId) : this.classes();
  }

  sectionsOf(classId: number): Section[] {
    return classId ? this.sections().filter((s) => s.class_id === classId) : [];
  }
}
