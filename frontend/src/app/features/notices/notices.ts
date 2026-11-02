import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api/api-error';
import { NOTICE_CATEGORIES, Notice, NoticeCategory, NoticesApi } from '../../core/api/notices.api';
import { NoticesService } from '../../core/api/notices.service';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { Icon } from '../../core/ui/icon';
import { CATEGORY_KEYS, relativeDateText, roleText, shortDate } from './notice-labels';
import { NoticeForm } from './notice-form';

const PAGE_SIZE = 20;
/** Bodies longer than this (or with many lines) get a "Read more" toggle. */
const LONG_BODY = 280;

@Component({
  selector: 'sms-notices',
  imports: [Icon, NoticeForm],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './notices.html',
  styleUrl: './notices.css',
})
export class Notices {
  private readonly api = inject(NoticesApi);
  private readonly shared = inject(NoticesService);
  private readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  protected readonly categories = NOTICE_CATEGORIES;
  protected readonly shortDate = shortDate;
  protected readonly canPost = this.auth.hasRole(
    'school_owner',
    'management',
    'headmaster',
    'teacher',
  );

  protected readonly q = signal('');
  protected readonly category = signal<NoticeCategory | ''>('');
  protected readonly unreadOnly = signal(false);
  protected readonly page = signal(1);
  private readonly reloadTick = signal(0);

  protected readonly items = signal<Notice[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly expanded = signal<ReadonlySet<number>>(new Set());
  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Notice | null>(null);
  protected readonly busy = signal(false);
  private readonly marking = new Set<number>();

  protected readonly from = computed(() => (this.total() ? (this.page() - 1) * PAGE_SIZE + 1 : 0));
  protected readonly to = computed(() => Math.min(this.page() * PAGE_SIZE, this.total()));
  protected readonly unread = this.shared.unread;

  constructor() {
    toObservable(
      computed(() => ({
        q: this.q().trim(),
        category: this.category(),
        unreadOnly: this.unreadOnly(),
        page: this.page(),
        tick: this.reloadTick(),
      })),
    )
      .pipe(
        debounceTime(250),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap((f) =>
          this.api
            .list({
              q: f.q,
              category: f.category,
              unread_only: f.unreadOnly,
              page: f.page,
              page_size: PAGE_SIZE,
            })
            .pipe(
              catchError((err: unknown) => {
                this.error.set(apiErrorMessage(err));
                return of(null);
              }),
            ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((res) => {
        this.loading.set(false);
        if (!res) return;
        this.items.set(res.items);
        this.total.set(res.total);
        this.shared.unread.set(res.unread_count);
      });
  }

  protected categoryName(category: NoticeCategory): string {
    return this.i18n.t(CATEGORY_KEYS[category]);
  }

  protected roleName(role: string): string {
    return roleText(role, this.i18n.t);
  }

  protected when(value: string): string {
    return relativeDateText(value, this.i18n.t);
  }

  protected isLong(n: Notice): boolean {
    return n.body.length > LONG_BODY || n.body.split('\n').length > 4;
  }

  protected isOpen(n: Notice): boolean {
    return this.expanded().has(n.id);
  }

  protected setQuery(value: string): void {
    this.q.set(value);
    this.page.set(1);
  }

  protected setCategory(value: string): void {
    this.category.set(value as NoticeCategory | '');
    this.page.set(1);
  }

  protected setUnreadOnly(value: boolean): void {
    this.unreadOnly.set(value);
    this.page.set(1);
  }

  protected prev(): void {
    this.page.update((p) => Math.max(1, p - 1));
  }

  protected next(): void {
    this.page.update((p) => p + 1);
  }

  protected toggle(n: Notice): void {
    const open = !this.isOpen(n);
    this.expanded.update((set) => {
      const copy = new Set(set);
      if (open) copy.add(n.id);
      else copy.delete(n.id);
      return copy;
    });
    if (open) this.markRead(n);
  }

  /** Mark one notice read once, and update the list and unread count locally. */
  protected markRead(n: Notice): void {
    if (n.is_read || this.marking.has(n.id)) return;
    this.marking.add(n.id);
    this.api.markRead(n.id).subscribe({
      next: () => {
        this.marking.delete(n.id);
        this.items.update((list) => list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
        this.shared.unread.update((c) => Math.max(0, c - 1));
      },
      error: (err: unknown) => {
        this.marking.delete(n.id);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected markAll(): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.markAllRead().subscribe({
      next: () => {
        this.busy.set(false);
        this.shared.unread.set(0);
        this.items.update((list) => list.map((x) => ({ ...x, is_read: true })));
        this.notice.set(this.i18n.t('ops.notice.allMarked'));
        if (this.unreadOnly()) this.reloadTick.update((t) => t + 1);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected openNew(): void {
    this.editing.set(null);
    this.formOpen.set(true);
  }

  protected openEdit(n: Notice): void {
    this.editing.set(n);
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected onSaved(message: string): void {
    this.closeForm();
    this.notice.set(message);
    this.page.set(1);
    this.reloadTick.update((t) => t + 1);
    this.shared.refresh();
  }

  protected remove(n: Notice): void {
    if (!window.confirm(this.i18n.t('ops.notice.deleteConfirm', { title: n.title }))) return;
    this.error.set(null);
    this.notice.set(null);
    this.api.remove(n.id).subscribe({
      next: () => {
        this.notice.set(this.i18n.t('ops.notice.deleted'));
        this.reloadTick.update((t) => t + 1);
        this.shared.refresh();
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }
}
