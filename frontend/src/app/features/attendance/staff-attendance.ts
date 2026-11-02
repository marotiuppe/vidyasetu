import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, concatMap, from, last, of, switchMap, tap } from 'rxjs';

import { AcademicsApi, Branch } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { AttendanceApi, StaffEntry, StaffMark, StaffSheet } from '../../core/api/attendance.api';
import { AuthService } from '../../core/auth/auth.service';
import { ROLE_LABELS } from '../../core/layout/nav';
import { Role } from '../../core/auth/auth.models';
import { MARK_CLASS, STAFF_MARKS, isoDate } from './attendance-labels';

const MAX_ENTRIES = 200;
const DISCARD = 'You have unsaved attendance changes. Discard them?';

interface Mark {
  status: StaffMark | null;
  remark: string;
}

@Component({
  selector: 'sms-staff-attendance',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './staff-attendance.html',
  styleUrl: './staff-attendance.css',
})
export class StaffAttendance {
  private readonly api = inject(AttendanceApi);
  private readonly academics = inject(AcademicsApi);
  private readonly auth = inject(AuthService);

  protected readonly marks = STAFF_MARKS;
  protected readonly markClass = MARK_CLASS;
  protected readonly today = isoDate(new Date());
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  protected readonly date = signal(this.today);
  protected readonly branchId = signal(0);

  protected readonly sheet = signal<StaffSheet | null>(null);
  private readonly edits = signal<Record<number, Mark>>({});
  protected readonly openRemarks = signal<Record<number, boolean>>({});
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly rows = computed(() => {
    const edits = this.edits();
    const names = new Map(this.branches().map((b) => [b.id, b.name]));
    return (this.sheet()?.staff ?? []).map((s) => {
      const e = edits[s.user_id];
      return {
        ...s,
        status: e ? e.status : s.status,
        remark: e ? e.remark : (s.remark ?? ''),
        roleLabel: ROLE_LABELS[s.role as Role] ?? s.role,
        branchName: s.branch_id !== null ? (names.get(s.branch_id) ?? null) : null,
      };
    });
  });

  protected readonly counts = computed(() => {
    const rows = this.rows();
    const n = (m: StaffMark) => rows.filter((r) => r.status === m).length;
    const marked = rows.filter((r) => r.status).length;
    return {
      total: rows.length,
      present: n('present'),
      absent: n('absent'),
      leave: n('leave'),
      half: n('half_day'),
      unmarked: rows.length - marked,
    };
  });

  private readonly changed = computed<StaffEntry[]>(() => {
    const original = new Map((this.sheet()?.staff ?? []).map((s) => [s.user_id, s]));
    const out: StaffEntry[] = [];
    for (const r of this.rows()) {
      const o = original.get(r.user_id);
      if (!r.status) continue;
      const remark = r.remark.trim();
      if (r.status !== o?.status || remark !== (o?.remark ?? '')) {
        out.push({ user_id: r.user_id, status: r.status, remark: remark || null });
      }
    }
    return out;
  });

  protected readonly dirty = computed(() => this.changed().length > 0);

  constructor() {
    if (this.canPickBranch) {
      this.academics.branches().subscribe({ next: (b) => this.branches.set(b), error: () => undefined });
    }
    toObservable(computed(() => ({ date: this.date(), branch: this.branchId() })))
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.notice.set(null);
        }),
        switchMap((s) =>
          this.api.staffSheet(s.date, s.branch || null).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((sheet) => {
        this.applySheet(sheet);
        this.loading.set(false);
      });
  }

  private applySheet(sheet: StaffSheet | null): void {
    this.sheet.set(sheet);
    this.edits.set({});
    this.openRemarks.set({});
  }

  protected pickBranch(event: Event): void {
    const el = event.target as HTMLSelectElement;
    if (this.dirty() && !window.confirm(DISCARD)) {
      el.value = String(this.branchId());
      return;
    }
    this.branchId.set(Number(el.value));
  }

  protected pickDate(event: Event): void {
    const el = event.target as HTMLInputElement;
    if (!el.value || el.value > this.today || el.value === this.date() || (this.dirty() && !window.confirm(DISCARD))) {
      el.value = this.date();
      return;
    }
    this.date.set(el.value);
  }

  protected setStatus(userId: number, status: StaffMark): void {
    const remark = this.rows().find((r) => r.user_id === userId)?.remark ?? '';
    this.edits.update((e) => ({ ...e, [userId]: { status, remark } }));
    this.notice.set(null);
  }

  protected setRemark(userId: number, event: Event): void {
    const remark = (event.target as HTMLInputElement).value;
    const status = this.rows().find((r) => r.user_id === userId)?.status ?? null;
    this.edits.update((e) => ({ ...e, [userId]: { status, remark } }));
    this.notice.set(null);
  }

  protected toggleRemark(userId: number): void {
    this.openRemarks.update((o) => ({ ...o, [userId]: !o[userId] }));
  }

  protected markAllPresent(): void {
    const rows = this.rows();
    this.edits.update((e) => {
      const next = { ...e };
      for (const r of rows) {
        if (!r.status) next[r.user_id] = { status: 'present', remark: r.remark };
      }
      return next;
    });
    this.notice.set(null);
  }

  protected save(): void {
    const sheet = this.sheet();
    if (!sheet || !this.dirty() || this.saving() || !sheet.is_working_day) return;
    const entries = this.changed();
    const chunks: StaffEntry[][] = [];
    for (let i = 0; i < entries.length; i += MAX_ENTRIES) chunks.push(entries.slice(i, i + MAX_ENTRIES));
    this.saving.set(true);
    this.error.set(null);
    this.notice.set(null);
    from(chunks)
      .pipe(
        concatMap((c) => this.api.saveStaffSheet(sheet.date, this.branchId() || null, c)),
        last(),
      )
      .subscribe({
        next: (res) => {
          this.applySheet(res);
          this.notice.set('Staff attendance saved.');
          this.saving.set(false);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.saving.set(false);
        },
      });
  }
}
