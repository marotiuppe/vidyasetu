import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { NoticesService } from '../api/notices.service';
import { SchoolService } from '../api/school.service';
import { SettingsService } from '../api/settings.service';
import { AuthService } from '../auth/auth.service';
import { I18n } from '../i18n/i18n';
import { LegalLinks } from '../legal/legal-links';
import { SiteNotice } from './site-notice';
import { Icon } from '../ui/icon';
import { NAV_ITEMS, ROLE_LABEL_KEYS } from './nav';

const PRODUCT_NAME = 'Vidyasetu';
const NOTICE_POLL_MS = 120_000;

@Component({
  selector: 'sms-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon, LegalLinks, SiteNotice],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.html',
  styleUrl: './shell.css',
  host: {
    '(document:click)': 'userMenuOpen.set(false)',
    '(document:keydown.escape)': 'closeOverlays()',
  },
})
export class Shell {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly school = inject(SchoolService);
  private readonly notices = inject(NoticesService);
  private readonly settings = inject(SettingsService);
  protected readonly i18n = inject(I18n);

  protected readonly menuOpen = signal(false);
  protected readonly userMenuOpen = signal(false);
  protected readonly year = this.school.year;
  protected readonly unread = this.notices.unread;
  protected readonly noticesEnabled = computed(
    () => this.auth.user()?.school_id != null && !this.auth.hasRole('super_admin'),
  );

  protected readonly logoUrl = this.school.logoUrl;
  protected readonly logoFailed = signal(false);
  protected readonly showSchoolLogo = computed(() => this.logoUrl() !== null && !this.logoFailed());

  protected readonly schoolName = computed(() => this.school.name() ?? PRODUCT_NAME);
  protected readonly roleLabel = computed(() => {
    const user = this.auth.user();
    return user ? this.i18n.t(ROLE_LABEL_KEYS[user.role]) : '';
  });
  protected readonly initials = computed(() => {
    const name = this.auth.user()?.full_name ?? '';
    return (
      name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join('') || '?'
    );
  });
  protected readonly navItems = computed(() => {
    const role = this.auth.user()?.role;
    return NAV_ITEMS.filter(
      (item) =>
        (!item.roles || (role !== undefined && item.roles.includes(role))) &&
        this.settings.isModuleOn(item.feature),
    );
  });

  /** The active route's breadcrumb: a translation key (`titleKey`) or the English `title`. */
  private readonly crumb = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.currentCrumb()),
      startWith(this.currentCrumb()),
    ),
    { initialValue: { key: 'app.nav.overview', title: 'Overview' } as Crumb },
  );

  /** Re-translated when the language changes. */
  protected readonly title = computed(() => {
    const crumb = this.crumb();
    return crumb.key !== undefined ? this.i18n.t(crumb.key) : (crumb.title ?? '');
  });

  constructor() {
    effect(() => {
      this.logoUrl();
      this.logoFailed.set(false);
    });
    // While a forced step (two-factor setup, password change) is pending the API refuses these
    // calls, so they run once, as soon as nothing is pending any more.
    let started = false;
    effect(() => {
      const user = this.auth.user();
      if (started || !user || user.mfa_setup_required || user.must_change_password) return;
      started = true;
      untracked(() => {
        this.school.load();
        this.settings.load();
        this.notices.refresh();
      });
    });
    const timer = setInterval(() => this.notices.refresh(), NOTICE_POLL_MS);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => this.closeOverlays());
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  protected toggleUserMenu(event: Event): void {
    event.stopPropagation();
    this.userMenuOpen.update((open) => !open);
  }

  protected closeOverlays(): void {
    this.menuOpen.set(false);
    this.userMenuOpen.set(false);
  }

  private currentCrumb(): Crumb {
    let route = this.router.routerState.snapshot.root;
    while (route.firstChild) {
      route = route.firstChild;
    }
    const key: unknown = route.data['titleKey'];
    const title: unknown = route.data['title'];
    if (typeof key === 'string') {
      return { key, title: typeof title === 'string' ? title : undefined };
    }
    return { title: typeof title === 'string' ? title : 'Overview' };
  }
}

interface Crumb {
  key?: string;
  title?: string;
}
