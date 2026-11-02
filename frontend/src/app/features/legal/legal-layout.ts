import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Title } from '@angular/platform-browser';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';

import { LegalService } from '../../core/api/legal.service';
import { I18n } from '../../core/i18n/i18n';
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
  private readonly route = inject(ActivatedRoute);
  protected readonly i18n = inject(I18n);

  /** Set on the public `/s/:code/...` pages; null on the general legal pages. */
  protected readonly code = toSignal(this.route.paramMap.pipe(map((p) => p.get('code'))), {
    initialValue: this.route.snapshot.paramMap.get('code'),
  });
  protected readonly schoolName = computed(() =>
    this.code() ? (this.legal.info()?.school_name ?? null) : null,
  );

  protected readonly year = new Date().getFullYear();
  protected readonly failed = this.legal.failed;
  protected readonly notConfigured = computed(() => this.legal.info()?.configured === false);

  constructor() {
    this.legal.load(this.code());

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
