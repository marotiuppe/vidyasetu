import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { RouterLink } from '@angular/router';

import { AcademicsApi } from '../../core/api/academics.api';
import { Notice, NoticesApi } from '../../core/api/notices.api';
import { SchoolService } from '../../core/api/school.service';
import { AuthService } from '../../core/auth/auth.service';
import { Icon, IconName } from '../../core/ui/icon';
import { relativeDate } from '../notices/notice-labels';

interface Stat {
  label: string;
  value: string;
  note: string;
  icon: IconName;
  tone: 'green' | 'lavender' | 'peach' | 'sky';
}

@Component({
  selector: 'sms-dashboard',
  imports: [Icon, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {
  private readonly auth = inject(AuthService);
  private readonly api = inject(AcademicsApi);

  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly today = new Date().toLocaleDateString('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  private readonly noticesApi = inject(NoticesApi);
  protected readonly showNotices = !this.auth.hasRole('super_admin');
  protected readonly latest = signal<Notice[] | null>(null);
  protected readonly relativeDate = relativeDate;

  private readonly branches = signal<number | null>(null);
  private readonly classes = signal<number | null>(null);
  private readonly sections = signal<number | null>(null);
  private readonly school = inject(SchoolService);
  protected readonly yearName = this.school.year;
  protected readonly schoolName = computed(() => this.school.name() ?? 'School portal');

  protected readonly stats = computed<Stat[]>(() => [
    {
      label: 'Branches',
      value: this.fmt(this.branches()),
      note: 'Active in this school',
      icon: 'building',
      tone: 'green',
    },
    {
      label: 'Classes',
      value: this.fmt(this.classes()),
      note: 'Across all branches',
      icon: 'book',
      tone: 'peach',
    },
    {
      label: 'Sections',
      value: this.fmt(this.sections()),
      note: 'Divisions of classes',
      icon: 'users',
      tone: 'sky',
    },
    {
      label: 'Academic year',
      value: this.yearName() ?? '—',
      note: this.yearName() ? 'Current year' : 'Not set yet',
      icon: 'calendar',
      tone: 'lavender',
    },
  ]);

  constructor() {
    this.api.branches().subscribe((b) => this.branches.set(b.length));
    this.api.classes().subscribe((c) => this.classes.set(c.length));
    this.api.sections().subscribe((s) => this.sections.set(s.length));
  }

  private fmt(value: number | null): string {
    return value === null ? '…' : String(value);
  }
}
