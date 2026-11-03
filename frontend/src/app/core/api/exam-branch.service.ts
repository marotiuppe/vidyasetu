import { Injectable, computed, inject, signal } from '@angular/core';

import { AuthService } from '../auth/auth.service';

/**
 * The branch the exam screens work on. A branch-level user always works on their own branch and
 * never picks one. A school owner (no branch of their own) picks a branch once here, and every
 * exam screen shares the choice.
 */
@Injectable({ providedIn: 'root' })
export class ExamBranchService {
  private readonly auth = inject(AuthService);

  /** True for school-wide accounts that have no branch of their own. */
  readonly needsPick = computed(() => this.auth.user()?.branch_id == null);

  /** The branch a school-wide account picked, or null until one is chosen. */
  readonly picked = signal<number | null>(null);

  /** Branch the screens filter by: the picked branch, or the user's own branch. Null = nothing chosen. */
  readonly branch = computed<number | null>(() =>
    this.needsPick() ? this.picked() : (this.auth.user()?.branch_id ?? null),
  );

  /** A school-wide account must pick a branch before the branch-scoped screens can work. */
  readonly choiceNeeded = computed(() => this.needsPick() && this.picked() === null);

  /** Value for `branch_id` on the calls the server accepts it on. Branch-level users send none. */
  readonly param = computed<number | null>(() => (this.needsPick() ? this.picked() : null));

  pick(branchId: number | null): void {
    this.picked.set(branchId);
  }
}
