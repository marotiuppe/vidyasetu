import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { SchoolService } from '../api/school.service';
import { AuthService } from '../auth/auth.service';
import { Icon } from '../ui/icon';
import { NAV_ITEMS, ROLE_LABELS } from './nav';

const PRODUCT_NAME = 'Vidyasetu';

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

  protected readonly menuOpen = signal(false);
  protected readonly userMenuOpen = signal(false);
  protected readonly year = this.school.year;

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
    this.school.load();
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
