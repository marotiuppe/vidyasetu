import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Title } from '@angular/platform-browser';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { LegalService } from '../../core/api/legal.service';
import { LegalLinks } from '../../core/legal/legal-links';

const PRODUCT_NAME = 'Vidyasetu';

/**
 * Public frame for every legal page. Lives outside the signed-in shell, so it works for visitors
 * and signed-in users alike. Shows the template banner when the operator details are not set.
 */
@Component({
  selector: 'sms-legal-layout',
  imports: [RouterLink, RouterOutlet, LegalLinks],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './legal-layout.html',
  styleUrl: './legal-layout.css',
})
export class LegalLayout {
  private readonly legal = inject(LegalService);
  private readonly router = inject(Router);
  private readonly title = inject(Title);

  protected readonly year = new Date().getFullYear();
  protected readonly failed = this.legal.failed;
  protected readonly notConfigured = computed(() => this.legal.info()?.configured === false);

  constructor() {
    this.legal.load();

    const previous = this.title.getTitle();
    inject(DestroyRef).onDestroy(() => this.title.setTitle(previous));
    this.applyTitle();
    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.applyTitle());
  }

  private applyTitle(): void {
    let route = this.router.routerState.snapshot.root;
    while (route.firstChild) {
      route = route.firstChild;
    }
    const title: unknown = route.data['title'];
    this.title.setTitle(typeof title === 'string' ? `${title} | ${PRODUCT_NAME}` : PRODUCT_NAME);
  }
}
