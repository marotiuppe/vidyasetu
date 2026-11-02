import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { map } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { Student, StudentsApi } from '../../core/api/students.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { AttendanceMark } from './attendance-mark';
import { AttendanceSummary } from './attendance-summary';
import { Holidays } from './holidays';
import { StaffAttendance } from './staff-attendance';
import { StudentAttendance } from './student-attendance';

type TabId = 'mark' | 'summary' | 'staff' | 'holidays' | 'my';

interface Tab {
  id: TabId;
  labelKey: string;
}

@Component({
  selector: 'sms-attendance',
  imports: [AttendanceMark, AttendanceSummary, StaffAttendance, Holidays, StudentAttendance],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance.html',
  styleUrl: './attendance.css',
})
export class Attendance {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly studentsApi = inject(StudentsApi);
  protected readonly i18n = inject(I18n);

  protected readonly selfService = this.auth.hasRole('parent', 'student');
  protected readonly canMark = this.auth.hasRole(
    'school_owner',
    'management',
    'headmaster',
    'teacher',
    'clerk',
  );
  private readonly canStaff = this.auth.hasRole(
    'school_owner',
    'management',
    'headmaster',
    'clerk',
  );

  protected readonly tabs: Tab[] = this.buildTabs();

  private readonly params = toSignal(
    this.route.queryParamMap.pipe(
      map((p) => ({ tab: p.get('tab'), section: p.get('section'), date: p.get('date') })),
    ),
    {
      initialValue: { tab: null, section: null, date: null },
    },
  );

  protected readonly active = computed<TabId>(() => {
    const wanted = this.params().tab;
    return this.tabs.find((t) => t.id === wanted)?.id ?? this.tabs[0].id;
  });
  protected readonly section = computed(() => Number(this.params().section) || 0);
  protected readonly date = computed(() => this.params().date ?? '');

  // "My attendance" for parents (pick a child) and students (themselves).
  protected readonly children = signal<Student[]>([]);
  protected readonly childId = signal(0);
  protected readonly childrenLoading = signal(this.selfService);
  protected readonly childrenError = signal<string | null>(null);

  constructor() {
    if (this.selfService) {
      this.studentsApi.list({}, 1, 100).subscribe({
        next: (page) => {
          this.children.set(page.items);
          this.childId.set(page.items[0]?.id ?? 0);
          this.childrenLoading.set(false);
        },
        error: (err: unknown) => {
          this.childrenError.set(apiErrorMessage(err));
          this.childrenLoading.set(false);
        },
      });
    }
  }

  private buildTabs(): Tab[] {
    if (this.selfService) {
      return [
        { id: 'my', labelKey: 'ops.tab.my' },
        { id: 'holidays', labelKey: 'ops.tab.holidays' },
      ];
    }
    const tabs: Tab[] = [];
    if (this.canMark) tabs.push({ id: 'mark', labelKey: 'ops.tab.mark' });
    tabs.push({ id: 'summary', labelKey: 'ops.tab.summary' });
    if (this.canStaff) tabs.push({ id: 'staff', labelKey: 'ops.tab.staff' });
    tabs.push({ id: 'holidays', labelKey: 'ops.tab.holidays' });
    return tabs;
  }

  protected select(id: TabId): void {
    void this.router.navigate([], { queryParams: { tab: id }, replaceUrl: false });
  }

  protected onTabKey(event: KeyboardEvent): void {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const i = this.tabs.findIndex((t) => t.id === this.active());
    const next = this.tabs[(i + step + this.tabs.length) % this.tabs.length];
    this.select(next.id);
    queueMicrotask(() => document.getElementById('tab-' + next.id)?.focus());
  }

  protected pickChild(event: Event): void {
    this.childId.set(Number((event.target as HTMLSelectElement).value));
  }
}
