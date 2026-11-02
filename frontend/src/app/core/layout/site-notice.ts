import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { SiteService } from '../api/site.service';

/** Shows the maintenance message and the announcement banner, when the platform has set them. */
@Component({
  selector: 'sms-site-notice',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './site-notice.html',
  styleUrl: './site-notice.css',
})
export class SiteNotice {
  protected readonly site = inject(SiteService);

  constructor() {
    this.site.load();
  }
}
