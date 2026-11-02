import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, concatMap, filter, forkJoin, from, last, of, switchMap, tap } from 'rxjs';
import { Params, Router } from '@angular/router';

import { AcademicsApi, Branch, SchoolClass, Section } from '../../core/api/academics.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  AttendanceApi,
  AttendanceSheet,
  SheetEntry,
  SheetSummary,
  StudentMark,
} from '../../core/api/attendance.api';
import { StudentsApi } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import {
  CREATE_NEW,
  CREATE_NEW_LABEL,
  CreateKind,
  createPermissions,
  isCreateNewChange,
} from '../../core/create/create-new';
import { ReturnStateService, restoreIds } from '../../core/create/return-state.service';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { MARK_CLASS, MARK_KEY, STUDENT_MARKS, isoDate, monthStartIso } from './attendance-labels';

const MAX_ENTRIES = 200;

interface Mark {
  status: StudentMark | null;
  remark: string;
}

@Component({
  selector: 'sms-attendance-mark',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-mark.html',
  styleUrl: './attendance-mark.css',
})
export class AttendanceMark {
  private readonly api = inject(AttendanceApi);
  private readonly academics = inject(AcademicsApi);
  private readonly students = inject(StudentsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly returnState = inject(ReturnStateService);
  protected readonly createNew = CREATE_NEW;
  protected readonly createNewLabel = CREATE_NEW_LABEL;
  protected readonly canCreate = createPermissions(this.auth);
  protected readonly i18n = inject(I18n);

  /** Optional preselection (from the daily summary link). Read once on load. */
  readonly initialSection = input(0);
  readonly initialDate = input('');

  protected readonly marks = STUDENT_MARKS;
  protected readonly markClass = MARK_CLASS;
  protected readonly markKey = MARK_KEY;
  protected readonly today = isoDate(new Date());
  protected readonly canPickBranch = this.auth.user()?.branch_id == null;

  protected readonly branches = signal<Branch[]>([]);
  private readonly classes = signal<SchoolClass[]>([]);
  private readonly sections = signal<Section[]>([]);

  protected readonly branchId = signal(0);
  protected readonly classId = signal(0);
  protected readonly sectionId = signal(0);
  protected readonly date = signal(this.today);

  protected readonly sheet = signal<AttendanceSheet | null>(null);
  private readonly edits = signal<Record<number, Mark>>({});
  protected readonly openRemarks = signal<Record<number, boolean>>({});
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly exportFrom = signal(monthStartIso());
  protected readonly exportTo = signal(this.today);
  protected readonly exporting = signal(false);

  protected readonly classOptions = computed(() => {
    const b = this.branchId();
    return this.canPickBranch
      ? b
        ? this.classes().filter((c) => c.branch_id === b)
        : []
      : this.classes();
  });
  protected readonly sectionOptions = computed(() => {
    const c = this.classId();
    return c ? this.sections().filter((s) => s.class_id === c) : [];
  });

  protected readonly rows = computed(() => {
    const edits = this.edits();
    return (this.sheet()?.students ?? []).map((s) => {
      const e = edits[s.student_id];
      return { ...s, status: e ? e.status : s.status, remark: e ? e.remark : (s.remark ?? '') };
    });
  });

  protected readonly summary = computed<SheetSummary>(() => {
    const rows = this.rows();
    const count = (m: StudentMark) => rows.filter((r) => r.status === m).length;
    const present = count('present');
    const absent = count('absent');
    const leave = count('leave');
    return {
      total: rows.length,
      present,
      absent,
      leave,
      unmarked: rows.length - present - absent - leave,
    };
  });

  private readonly changed = computed<SheetEntry[]>(() => {
    const original = new Map((this.sheet()?.students ?? []).map((s) => [s.student_id, s]));
    const out: SheetEntry[] = [];
    for (const r of this.rows()) {
      const o = original.get(r.student_id);
      if (!r.status) continue;
      const remark = r.remark.trim();
      if (r.status !== o?.status || remark !== (o?.remark ?? '')) {
        out.push({ student_id: r.student_id, status: r.status, remark: remark || null });
      }
    }
    return out;
  });

  protected readonly dirty = computed(() => this.changed().length > 0);
  protected readonly canExport = computed(
    () =>
      this.sectionId() > 0 &&
      !!this.exportFrom() &&
      !!this.exportTo() &&
      this.exportFrom() <= this.exportTo(),
  );

  constructor() {
    // Back from a create screen: the date and the chosen branch, class and section come back.
    const back = this.returnState.take(this.router.url);
    if (back) {
      const d = back.draft as {
        date: string;
        branchId: number;
        classId: number;
        sectionId: number;
      };
      this.date.set(d.date);
      const ids = restoreIds(back, d, {
        branch: 'branchId',
        class: 'classId',
        section: 'sectionId',
      });
      this.branchId.set(ids.branchId);
      this.classId.set(ids.classId);
      this.sectionId.set(ids.sectionId);
    }
    forkJoin({
      classes: this.academics.classes(),
      sections: this.academics.sections(),
      branches: this.canPickBranch ? this.academics.branches() : of([] as Branch[]),
    })
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: (r) => {
          this.classes.set(r.classes);
          this.sections.set(r.sections);
          this.branches.set(r.branches);
          if (!back) this.preselect();
        },
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });

    toObservable(computed(() => ({ section: this.sectionId(), date: this.date() })))
      .pipe(
        filter((s) => s.section > 0 && !!s.date),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.notice.set(null);
        }),
        switchMap((s) =>
          this.api.sheet(s.section, s.date).pipe(
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

  private preselect(): void {
    const sec = this.sections().find((s) => s.id === this.initialSection());
    const date = this.initialDate();
    if (date && date <= this.today) this.date.set(date);
    if (!sec) return;
    this.branchId.set(sec.branch_id);
    this.classId.set(sec.class_id);
    this.sectionId.set(sec.id);
  }

  private applySheet(sheet: AttendanceSheet | null): void {
    this.sheet.set(sheet);
    this.edits.set({});
    this.openRemarks.set({});
  }

  private confirmLeave(): boolean {
    return !this.dirty() || window.confirm(this.i18n.t('ops.att.discard'));
  }

  /** Open a create screen for a missing branch, class or section; this page comes back with its state kept. */
  private openCreate(kind: CreateKind): void {
    const branchId = this.branchId();
    const extra: Params =
      kind === 'section'
        ? { classId: this.classId() }
        : kind === 'class' && branchId
          ? { branchId }
          : {};
    this.returnState.openCreate(
      kind,
      { date: this.date(), branchId, classId: this.classId(), sectionId: this.sectionId() },
      'Attendance',
      extra,
    );
  }

  protected pickBranch(event: Event): void {
    const el = event.target as HTMLSelectElement;
    if (!this.confirmLeave()) {
      el.value = String(this.branchId());
      return;
    }
    if (isCreateNewChange(event)) {
      this.openCreate('branch');
      return;
    }
    this.branchId.set(Number(el.value));
    this.classId.set(0);
    this.sectionId.set(0);
    this.applySheet(null);
  }

  protected pickClass(event: Event): void {
    const el = event.target as HTMLSelectElement;
    if (!this.confirmLeave()) {
      el.value = String(this.classId());
      return;
    }
    if (isCreateNewChange(event)) {
      this.openCreate('class');
      return;
    }
    this.classId.set(Number(el.value));
    this.sectionId.set(0);
    this.applySheet(null);
  }

  protected pickSection(event: Event): void {
    const el = event.target as HTMLSelectElement;
    if (!this.confirmLeave()) {
      el.value = String(this.sectionId());
      return;
    }
    if (isCreateNewChange(event)) {
      this.openCreate('section');
      return;
    }
    this.sectionId.set(Number(el.value));
    if (!this.sectionId()) this.applySheet(null);
  }

  protected pickDate(event: Event): void {
    const el = event.target as HTMLInputElement;
    if (!el.value || el.value > this.today || el.value === this.date() || !this.confirmLeave()) {
      el.value = this.date();
      return;
    }
    this.date.set(el.value);
  }

  protected setStatus(studentId: number, status: StudentMark): void {
    const remark = this.rows().find((r) => r.student_id === studentId)?.remark ?? '';
    this.edits.update((e) => ({ ...e, [studentId]: { status, remark } }));
    this.notice.set(null);
  }

  protected setRemark(studentId: number, event: Event): void {
    const remark = (event.target as HTMLInputElement).value;
    const status = this.rows().find((r) => r.student_id === studentId)?.status ?? null;
    this.edits.update((e) => ({ ...e, [studentId]: { status, remark } }));
    this.notice.set(null);
  }

  protected toggleRemark(studentId: number): void {
    this.openRemarks.update((o) => ({ ...o, [studentId]: !o[studentId] }));
  }

  protected markAllPresent(): void {
    const rows = this.rows();
    this.edits.update((e) => {
      const next = { ...e };
      for (const r of rows) {
        if (!r.status) next[r.student_id] = { status: 'present', remark: r.remark };
      }
      return next;
    });
    this.notice.set(null);
  }

  protected save(): void {
    const sheet = this.sheet();
    if (!sheet || !this.dirty() || this.saving() || !sheet.is_working_day) return;
    const chunks: SheetEntry[][] = [];
    const entries = this.changed();
    for (let i = 0; i < entries.length; i += MAX_ENTRIES)
      chunks.push(entries.slice(i, i + MAX_ENTRIES));
    this.saving.set(true);
    this.error.set(null);
    this.notice.set(null);
    from(chunks)
      .pipe(
        concatMap((c) => this.api.saveSheet(sheet.section_id, sheet.date, c)),
        last(),
      )
      .subscribe({
        next: (res) => {
          this.applySheet(res);
          this.notice.set(this.i18n.t('ops.mark.saved'));
          this.saving.set(false);
        },
        error: (err: unknown) => {
          this.error.set(apiErrorMessage(err));
          this.saving.set(false);
        },
      });
  }

  protected exportCsv(): void {
    const sheet = this.sheet();
    if (!this.canExport()) return;
    this.exporting.set(true);
    this.api.exportCsv(this.sectionId(), this.exportFrom(), this.exportTo()).subscribe({
      next: (blob) => {
        const name = sheet ? `${sheet.class_name}-${sheet.section_name}` : 'section';
        this.students.saveBlob(
          blob,
          `attendance-${name}-${this.exportFrom()}-to-${this.exportTo()}.csv`,
        );
        this.exporting.set(false);
      },
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.exporting.set(false);
      },
    });
  }

  protected setExport(which: 'from' | 'to', event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    (which === 'from' ? this.exportFrom : this.exportTo).set(value);
  }
}
