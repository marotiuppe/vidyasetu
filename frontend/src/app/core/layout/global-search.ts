import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Subject, catchError, debounceTime, map, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../api/api-error';
import { SearchApi, SearchItem } from '../api/search.api';
import { I18n } from '../i18n/i18n';
import { Icon } from '../ui/icon';

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;
const LIMIT_PER_GROUP = 5;
const LISTBOX_ID = 'global-search-listbox';
const INPUT_ID = 'global-search-input';

interface ViewItem {
  item: SearchItem;
  index: number;
}

interface ViewGroup {
  type: string;
  label: string;
  items: ViewItem[];
}

/** Routes from the server are used only when they are app paths (no scheme, no protocol-relative). */
function isAppRoute(url: string): boolean {
  return url.startsWith('/') && !url.startsWith('//');
}

/**
 * Search box in the top bar. Results are grouped by kind and the combobox works with the keyboard:
 * arrows move, Enter opens, Escape closes.
 */
@Component({
  selector: 'sms-global-search',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './global-search.html',
  styleUrl: './global-search.css',
  host: { '(document:click)': 'onDocumentClick($event)' },
})
export class GlobalSearch {
  private readonly api = inject(SearchApi);
  private readonly router = inject(Router);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  protected readonly i18n = inject(I18n);

  private readonly input = viewChild.required<ElementRef<HTMLInputElement>>('input');
  private readonly typed = new Subject<string>();

  protected readonly listboxId = LISTBOX_ID;
  protected readonly inputId = INPUT_ID;
  protected readonly minChars = MIN_CHARS;

  protected readonly query = signal('');
  protected readonly open = signal(false);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly groups = signal<{ type: string; items: SearchItem[] }[]>([]);
  protected readonly active = signal(-1);
  /** Below the tablet width the field is hidden until the search button opens it. */
  protected readonly mobileOpen = signal(false);

  protected readonly count = computed(() =>
    this.groups().reduce((sum, g) => sum + g.items.length, 0),
  );
  protected readonly tooShort = computed(
    () => this.query().trim().length > 0 && this.query().trim().length < MIN_CHARS,
  );
  protected readonly showPanel = computed(
    () => this.open() && this.query().trim().length >= MIN_CHARS,
  );
  protected readonly showEmpty = computed(
    () => this.showPanel() && !this.loading() && this.error() === null && this.count() === 0,
  );

  /** Groups with a running index per hit, so the active option can be found by number. */
  protected readonly view = computed<ViewGroup[]>(() => {
    let index = 0;
    return this.groups().map((g) => ({
      type: g.type,
      label: this.i18n.server('search.group', g.type, g.type),
      items: g.items.map((item) => ({ item, index: index++ })),
    }));
  });

  /** Spoken after each search (polite live region). */
  protected readonly announcement = computed(() => {
    if (!this.showPanel() || this.loading()) return '';
    if (this.error() !== null) return this.error() ?? '';
    const n = this.count();
    if (n === 0) return this.i18n.t('search.none');
    return this.i18n.t(n === 1 ? 'search.count.one' : 'search.count.other', { count: n });
  });

  constructor() {
    this.typed
      .pipe(
        debounceTime(DEBOUNCE_MS),
        switchMap((text) => {
          const term = text.trim();
          if (term.length < MIN_CHARS) {
            this.loading.set(false);
            this.error.set(null);
            this.groups.set([]);
            return of(null);
          }
          this.loading.set(true);
          this.error.set(null);
          return this.api.search(term, LIMIT_PER_GROUP).pipe(
            map((res) => res.groups),
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err));
              return of([] as { type: string; items: SearchItem[] }[]);
            }),
            tap(() => this.loading.set(false)),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((groups) => {
        if (groups === null) return;
        this.groups.set(groups);
        this.active.set(-1);
      });
  }

  protected onInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.query.set(value);
    this.open.set(true);
    this.typed.next(value);
  }

  protected onKeydown(event: KeyboardEvent): void {
    const total = this.count();
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.open.set(true);
        if (total > 0) this.active.set((this.active() + 1) % total);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.open.set(true);
        if (total > 0) this.active.set(this.active() <= 0 ? total - 1 : this.active() - 1);
        break;
      case 'Enter': {
        const hit = this.itemAt(this.active());
        if (hit) {
          event.preventDefault();
          this.choose(hit);
        }
        break;
      }
      case 'Escape':
        if (this.open()) {
          event.preventDefault();
          event.stopPropagation();
        }
        this.close();
        break;
      case 'Tab':
        this.close();
        break;
    }
  }

  protected choose(item: SearchItem): void {
    if (!isAppRoute(item.url)) return;
    this.close();
    this.query.set('');
    this.groups.set([]);
    this.typed.next('');
    void this.router.navigateByUrl(item.url);
  }

  protected toggleMobile(): void {
    const next = !this.mobileOpen();
    this.mobileOpen.set(next);
    if (next) {
      setTimeout(() => this.input().nativeElement.focus(), 0);
    } else {
      this.close();
    }
  }

  protected optionId(index: number): string {
    return `global-search-opt-${index}`;
  }

  protected activeOptionId(): string | null {
    const index = this.active();
    return index >= 0 && index < this.count() ? this.optionId(index) : null;
  }

  protected onDocumentClick(event: Event): void {
    if (!this.host.nativeElement.contains(event.target as Node)) this.close();
  }

  /** Focus left the search (for example with Tab): close the list. Clicks inside keep focus on the field. */
  protected onFocusOut(event: FocusEvent): void {
    const next = event.relatedTarget as Node | null;
    if (!next || !this.host.nativeElement.contains(next)) this.close();
  }

  private close(): void {
    this.open.set(false);
    this.active.set(-1);
    this.mobileOpen.set(false);
  }

  private itemAt(index: number): SearchItem | null {
    if (index < 0) return null;
    let i = 0;
    for (const g of this.groups()) {
      for (const item of g.items) {
        if (i++ === index) return item;
      }
    }
    return null;
  }
}
