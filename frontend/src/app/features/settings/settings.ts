import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { AdminApi, School } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import { Branch } from '../../core/api/academics.api';
import {
  IntegrationName,
  IntegrationTestResult,
  LevelAccess,
  SettingItem,
  SettingLevel,
  SettingScope,
  SettingsApi,
} from '../../core/api/settings.api';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { SettingItemView } from './setting-item';

interface Group {
  name: string;
  items: SettingItem[];
  /** Set for `integrations.<name>` groups: the integration a "Send test" button talks to. */
  integration: IntegrationName | null;
}

const INTEGRATIONS: readonly string[] = ['sms', 'whatsapp', 'smtp', 'razorpay', 'storage'];

function integrationOf(group: string): IntegrationName | null {
  const [head, name] = group.toLowerCase().split('.');
  return head === 'integrations' && name && INTEGRATIONS.includes(name)
    ? (name as IntegrationName)
    : null;
}

@Component({
  selector: 'sms-settings',
  imports: [RouterLink, SettingItemView],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class Settings {
  private readonly api = inject(SettingsApi);
  private readonly admin = inject(AdminApi);
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  protected readonly levels = signal<LevelAccess[]>([]);
  protected readonly levelsLoading = signal(true);
  protected readonly tab = signal<SettingLevel | null>(null);

  protected readonly schools = signal<School[]>([]);
  protected readonly branches = signal<Branch[]>([]);
  protected readonly schoolId = signal<number | null>(null);
  protected readonly branchId = signal<number | null>(null);

  protected readonly items = signal<SettingItem[]>([]);
  protected readonly loading = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly query = signal('');
  protected readonly collapsed = signal<ReadonlySet<string>>(new Set());
  protected readonly tests = signal<Record<string, IntegrationTestResult | 'busy' | undefined>>({});

  private readonly isSuper = computed(() => this.auth.user()?.role === 'super_admin');
  private readonly isOwner = computed(() => this.auth.user()?.role === 'school_owner');

  protected readonly needsSchoolPick = computed(
    () => this.isSuper() && (this.tab() === 'school' || this.tab() === 'branch'),
  );
  protected readonly needsBranchPick = computed(
    () => this.tab() === 'branch' && (this.isSuper() || this.isOwner()),
  );
  protected readonly visibleBranches = computed(() => {
    const school = this.schoolId();
    return this.isSuper() ? this.branches().filter((b) => b.school_id === school) : this.branches();
  });

  /** The school or branch the list applies to; null while a required picker is still empty. */
  protected readonly scope = computed<SettingScope | null>(() => {
    const tab = this.tab();
    const school = this.schoolId();
    const branch = this.branchId();
    if (tab === 'school' && this.isSuper()) return school === null ? null : { school_id: school };
    if (tab === 'branch' && (this.isSuper() || this.isOwner())) {
      if (branch === null) return null;
      return this.isSuper() ? { school_id: school, branch_id: branch } : { branch_id: branch };
    }
    return {};
  });

  protected readonly canEditLevel = computed(
    () => this.levels().find((l) => l.level === this.tab())?.can_edit ?? false,
  );

  protected readonly groups = computed<Group[]>(() => {
    const q = this.query().trim().toLowerCase();
    const map = new Map<string, SettingItem[]>();
    for (const item of this.items()) {
      const label = this.i18n.server('settings', item.key, item.label).toLowerCase();
      if (
        q &&
        !label.includes(q) &&
        !item.label.toLowerCase().includes(q) &&
        !item.help.toLowerCase().includes(q)
      ) {
        continue;
      }
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()].map(([name, items]) => ({
      name,
      items,
      integration: integrationOf(name),
    }));
  });

  private loadToken = 0;

  constructor() {
    this.api.levels().subscribe({
      next: (res) => {
        this.levels.set(res.levels);
        this.tab.set(res.levels[0]?.level ?? null);
        this.levelsLoading.set(false);
      },
      error: (err: unknown) => {
        this.loadError.set(apiErrorMessage(err));
        this.levelsLoading.set(false);
      },
    });
    if (this.isSuper()) {
      this.admin.schools().subscribe((s) => this.schools.set(s));
    }
    if (this.isSuper() || this.isOwner()) {
      this.admin.branches().subscribe((b) => this.branches.set(b));
    }

    effect(() => {
      const tab = this.tab();
      const scope = this.scope();
      untracked(() => this.load(tab, scope));
    });
  }

  protected selectTab(level: SettingLevel): void {
    this.tab.set(level);
    this.query.set('');
    this.tests.set({});
  }

  protected onTabKey(event: KeyboardEvent, index: number): void {
    const count = this.levels().length;
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % count;
    else if (event.key === 'ArrowLeft') next = (index - 1 + count) % count;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = count - 1;
    else return;
    event.preventDefault();
    this.selectTab(this.levels()[next].level);
    queueMicrotask(() =>
      document.getElementById('settings-tab-' + this.levels()[next].level)?.focus(),
    );
  }

  protected pickSchool(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.schoolId.set(value === '' ? null : Number(value));
    this.branchId.set(null);
  }

  protected pickBranch(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.branchId.set(value === '' ? null : Number(value));
  }

  protected onSearch(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  protected toggleGroup(name: string): void {
    this.collapsed.update((set) => {
      const next = new Set(set);
      if (!next.delete(name)) next.add(name);
      return next;
    });
  }

  protected replace(updated: SettingItem): void {
    this.items.update((list) => list.map((i) => (i.key === updated.key ? updated : i)));
    // Several settings can depend on each other (inherited values), so refresh the list quietly.
    const tab = this.tab();
    const scope = this.scope();
    if (tab && scope) {
      this.api.list(tab, scope).subscribe({
        next: (items) => this.items.set(items),
        error: () => undefined,
      });
    }
  }

  protected groupTitle(name: string): string {
    return this.i18n.server('settings.group', name, name.replace(/[._]/g, ' '));
  }

  protected groupId(name: string): string {
    return 'group-' + name.replace(/\W/g, '-');
  }

  protected sendTest(group: Group): void {
    const name = group.integration;
    const scope = this.scope();
    if (!name || !scope) return;
    this.tests.update((t) => ({ ...t, [group.name]: 'busy' }));
    this.api.testIntegration(name, scope).subscribe({
      next: (res) => this.tests.update((t) => ({ ...t, [group.name]: res })),
      error: (err: unknown) =>
        this.tests.update((t) => ({
          ...t,
          [group.name]: { ok: false, detail: apiErrorMessage(err) },
        })),
    });
  }

  protected testResult(group: Group): IntegrationTestResult | null {
    const r = this.tests()[group.name];
    return r && r !== 'busy' ? r : null;
  }

  protected testBusy(group: Group): boolean {
    return this.tests()[group.name] === 'busy';
  }

  private load(tab: SettingLevel | null, scope: SettingScope | null): void {
    const token = ++this.loadToken;
    this.items.set([]);
    this.loadError.set(null);
    if (!tab || !scope) {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.api.list(tab, scope).subscribe({
      next: (items) => {
        if (token !== this.loadToken) return;
        this.items.set(items);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        if (token !== this.loadToken) return;
        this.loadError.set(apiErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
