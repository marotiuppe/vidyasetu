import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { FEE_MANAGER_ROLES, FEE_PAY_ROLES, FEE_VIEW_ROLES } from '../../core/auth/permissions';
import { FeeCollection } from './fee-collection';
import { FeeDues } from './fee-dues';
import { FeeInvoices } from './fee-invoices';
import { FeeSetup } from './fee-setup';
import { MyFees } from './my-fees';

type TabId = 'invoices' | 'dues' | 'collection' | 'setup' | 'my';

interface Tab {
  id: TabId;
  label: string;
}

@Component({
  selector: 'sms-fees',
  imports: [FeeInvoices, FeeDues, FeeCollection, FeeSetup, MyFees],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fees.html',
})
export class Fees {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly selfService = this.auth.hasRole('parent', 'student');
  protected readonly canManage = this.auth.hasRole(...FEE_MANAGER_ROLES);
  protected readonly canPay = this.auth.hasRole(...FEE_PAY_ROLES);

  protected readonly tabs: Tab[] = this.buildTabs();

  private readonly tabParam = toSignal(this.route.queryParamMap.pipe(map((p) => p.get('tab'))), {
    initialValue: null,
  });

  protected readonly active = computed<TabId>(
    () => this.tabs.find((t) => t.id === this.tabParam())?.id ?? this.tabs[0].id,
  );

  private buildTabs(): Tab[] {
    if (this.selfService) return [{ id: 'my', label: 'My fees' }];
    if (!this.auth.hasRole(...FEE_VIEW_ROLES)) return [];
    const tabs: Tab[] = [
      { id: 'invoices', label: 'Invoices' },
      { id: 'dues', label: 'Dues' },
    ];
    if (this.canManage || this.auth.hasRole('headmaster')) tabs.push({ id: 'collection', label: 'Collection' });
    if (this.canManage) tabs.push({ id: 'setup', label: 'Setup' });
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
}
