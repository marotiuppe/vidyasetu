import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { NoticesService } from '../api/notices.service';
import { SchoolService } from '../api/school.service';
import { AuthService } from '../auth/auth.service';
import { Icon } from '../ui/icon';
import { NAV_ITEMS, ROLE_LABELS } from './nav';

const PRODUCT_NAME = 'Vidyasetu';
const NOTICE_POLL_MS = 120_000;

@Component({
  selector: 'sms-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
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
  private readonly school = inject(SchoolService);
  private readonly notices = inject(NoticesService);

  protected readonly menuOpen = signal(false);
  protected readonly userMenuOpen = signal(false);
  protected readonly year = this.school.year;
  protected readonly unread = this.notices.unread;
  protected readonly noticesEnabled = computed(() => this.auth.user()?.school_id != null && !this.auth.hasRole('super_admin'));

  protected readonly logoUrl = this.school.logoUrl;
  protected readonly logoFailed = signal(false);
  protected readonly showSchoolLogo = computed(() => this.logoUrl() !== null && !this.logoFailed());

  protected readonly schoolName = computed(() => this.school.name() ?? PRODUCT_NAME);
  protected readonly roleLabel = computed(() => {
    const user = this.auth.user();
    return user ? ROLE_LABELS[user.role] : '';
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
    return NAV_ITEMS.filter((item) => !item.roles || (role !== undefined && item.roles.includes(role)));
  });

  protected readonly title = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.currentTitle()),
      startWith(this.currentTitle()),
    ),
    { initialValue: 'Overview' },
  );

  constructor() {
    effect(() => {
      this.logoUrl();
      this.logoFailed.set(false);
    });
    this.school.load();
    this.notices.refresh();
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

  private currentTitle(): string {
    let route = this.router.routerState.snapshot.root;
    while (route.firstChild) {
      route = route.firstChild;
    }
    const title: unknown = route.data['title'];
    return typeof title === 'string' ? title : 'Overview';
  }
}
