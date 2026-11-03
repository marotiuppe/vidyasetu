import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { RouterLink } from '@angular/router';

import { AcademicsApi } from '../../core/api/academics.api';
import { Notice, NoticesApi } from '../../core/api/notices.api';
import { SchoolService } from '../../core/api/school.service';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { localeOf } from '../../core/ui/dates';
import { Icon, IconName } from '../../core/ui/icon';
import { relativeDateText } from '../notices/notice-labels';

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
  protected readonly i18n = inject(I18n);

  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly today = computed(() =>
    new Date().toLocaleDateString(localeOf(this.i18n.lang()), {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }),
  );

  private readonly noticesApi = inject(NoticesApi);
  protected readonly showNotices = !this.auth.hasRole('super_admin');
  protected readonly latest = signal<Notice[] | null>(null);
  protected relativeDate(value: string): string {
    return relativeDateText(value, this.i18n.t, this.i18n.lang());
  }

  private readonly branches = signal<number | null>(null);
  private readonly classes = signal<number | null>(null);
  private readonly sections = signal<number | null>(null);
  private readonly school = inject(SchoolService);
  protected readonly yearName = this.school.year;
  protected readonly schoolName = computed(
    () => this.school.name() ?? this.i18n.t('app.shell.portal'),
  );

  protected readonly stats = computed<Stat[]>(() => [
    {
      label: this.i18n.t('app.dash.branches'),
      value: this.fmt(this.branches()),
      note: this.i18n.t('app.dash.branchesNote'),
      icon: 'building',
      tone: 'green',
    },
    {
      label: this.i18n.t('app.dash.classes'),
      value: this.fmt(this.classes()),
      note: this.i18n.t('app.dash.classesNote'),
      icon: 'book',
      tone: 'peach',
    },
    {
      label: this.i18n.t('app.dash.sections'),
      value: this.fmt(this.sections()),
      note: this.i18n.t('app.dash.sectionsNote'),
      icon: 'users',
      tone: 'sky',
    },
    {
      label: this.i18n.t('app.dash.academicYear'),
      value: this.yearName() ?? '—',
      note: this.yearName()
        ? this.i18n.t('app.dash.currentYear')
        : this.i18n.t('app.dash.notSetYet'),
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
