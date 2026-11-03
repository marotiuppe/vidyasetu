import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AdminApi, Branch } from '../../core/api/admin.api';
import { apiErrorMessage } from '../../core/api/api-error';
import {
  ImportsApi,
  UserCredential,
  UserImportResult,
  UserImportRow,
} from '../../core/api/imports.api';
import { Role } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { I18n } from '../../core/i18n/i18n';
import { ROLE_LABELS } from '../../core/layout/nav';
import { copyText } from '../../core/ui/clipboard';
import { headerName } from '../../core/ui/csv';
import { ImportFile, LoadedCsv } from '../../core/ui/import-file';
import { ImportReport } from '../../core/ui/import-report';
import { Icon } from '../../core/ui/icon';

export const USER_IMPORT_MAX_ROWS = 500;
const PREVIEW_ROWS = 5;
const REQUIRED_COLUMNS = ['username', 'full_name', 'role'];
const COLUMNS = ['username', 'full_name', 'role', 'email', 'mobile'];
const BRANCH_LEVEL_CREATORS: Role[] = ['teacher', 'accountant', 'clerk', 'student', 'parent'];
const ALL_ROLES = Object.keys(ROLE_LABELS) as Role[];

/** Bulk creation of staff and parent or student accounts from a CSV file (UX only; the backend enforces it). */
@Component({
  selector: 'sms-users-import',
  imports: [RouterLink, ImportFile, ImportReport, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './users-import.html',
  styleUrl: './users-import.css',
})
export class UsersImport {
  private readonly api = inject(ImportsApi);
  private readonly admin = inject(AdminApi);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18n);

  protected readonly columns = COLUMNS;
  protected readonly templateRows = [COLUMNS];
  protected readonly maxRows = USER_IMPORT_MAX_ROWS;

  /** Roles this user may create, as the users screen offers them. Only these may be imported. */
  protected readonly roles = computed<Role[]>(() => {
    switch (this.auth.user()?.role) {
      case 'school_owner':
        return ALL_ROLES.filter((r) => r !== 'super_admin');
      case 'management':
      case 'headmaster':
        return BRANCH_LEVEL_CREATORS;
      default:
        return [];
    }
  });
  /** A school owner has no branch of their own, so the branch is chosen here. */
  protected readonly canPickBranch = computed(() => this.auth.user()?.branch_id == null);

  protected readonly branchId = signal(0);
  protected readonly branchChoices = signal<Branch[]>([]);
  protected readonly rows = signal<UserImportRow[]>([]);
  protected readonly fileName = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly checked = signal<UserImportResult | null>(null);
  protected readonly result = signal<UserImportResult | null>(null);
  protected readonly checking = signal(false);
  protected readonly submitting = signal(false);
  /** Result of the last copy: 'ok', 'failed' or 'idle' (nothing to say yet). */
  protected readonly copyState = signal<'idle' | 'ok' | 'failed'>('idle');

  /** One-time sign-in details from the last real import. Kept in memory only, never stored. */
  protected readonly credentials = computed<UserCredential[]>(
    () => this.result()?.credentials ?? [],
  );
  protected readonly preview = computed(() => this.rows().slice(0, PREVIEW_ROWS));
  protected readonly tooMany = computed(() => this.rows().length > USER_IMPORT_MAX_ROWS);
  private readonly ready = computed(
    () =>
      this.rows().length > 0 &&
      !this.tooMany() &&
      (!this.canPickBranch() || this.branchId() > 0 || !this.needsBranch()),
  );
  protected readonly canCheck = computed(() => this.ready() && !this.checking());
  protected readonly canImport = computed(() => this.ready() && !this.submitting());

  /** Branch-level roles need a branch; the server checks every row, this only guides the user. */
  private needsBranch(): boolean {
    return this.rows().some((r) => BRANCH_LEVEL_CREATORS.includes(r.role));
  }

  constructor() {
    if (this.canPickBranch()) {
      this.admin.branches().subscribe({
        next: (b) => this.branchChoices.set(b),
        error: () => this.branchChoices.set([]),
      });
    }
  }

  protected roleName(role: Role): string {
    return this.i18n.t(`admin.role.${role}`);
  }

  /** "Full name (username)" for a row number (1-based), for the error report. */
  protected describe = (row: number): string => {
    const r = this.rows()[row - 1];
    return r ? `${r.full_name} (${r.username})` : '';
  };

  protected onLoaded(csv: LoadedCsv): void {
    this.reset();
    this.fileName.set(csv.fileName);
    const parsed = this.parse(csv);
    if (parsed.error) {
      this.error.set(parsed.error);
      return;
    }
    this.rows.set(parsed.rows);
    if (parsed.rows.length > USER_IMPORT_MAX_ROWS) {
      this.error.set(
        this.i18n.t('users.import.tooMany', {
          count: parsed.rows.length,
          max: USER_IMPORT_MAX_ROWS,
        }),
      );
    }
  }

  protected onCleared(): void {
    this.reset();
    this.fileName.set(null);
  }

  protected onBranch(e: Event): void {
    this.branchId.set(Number((e.target as HTMLSelectElement).value));
    this.checked.set(null);
  }

  protected check(): void {
    if (!this.canCheck()) return;
    this.checking.set(true);
    this.error.set(null);
    this.result.set(null);
    this.api.importUsers(this.body(true)).subscribe({
      next: (res) => {
        this.checking.set(false);
        this.checked.set(res);
      },
      error: (err: unknown) => {
        this.checking.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  protected submit(): void {
    if (!this.canImport()) return;
    this.submitting.set(true);
    this.error.set(null);
    this.api.importUsers(this.body(false)).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.checked.set(null);
        this.rows.set([]);
        this.result.set(res);
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.error.set(apiErrorMessage(err));
      },
    });
  }

  /** The one-time details are gone from the screen once the admin confirms they have them. */
  protected dismissCredentials(): void {
    this.result.set(null);
    this.copyState.set('idle');
  }

  protected async copyCredentials(): Promise<void> {
    const lines = this.credentials().map((c) =>
      [c.full_name, c.username, this.roleName(c.role), c.temporary_password].join('\t'),
    );
    const header = [
      this.i18n.t('users.import.cred.name'),
      this.i18n.t('users.import.cred.username'),
      this.i18n.t('users.import.cred.role'),
      this.i18n.t('users.import.cred.password'),
    ].join('\t');
    const ok = await copyText([header, ...lines].join('\n'));
    this.copyState.set(ok ? 'ok' : 'failed');
  }

  /** Print only the credentials card (the print styles hide the rest of the page). */
  protected print(): void {
    window.print();
  }

  private reset(): void {
    this.rows.set([]);
    this.error.set(null);
    this.checked.set(null);
    this.result.set(null);
    this.copyState.set('idle');
  }

  private parse(csv: LoadedCsv): { rows: UserImportRow[]; error: string | null } {
    const [header, ...body] = csv.records;
    if (!header) return { rows: [], error: this.i18n.t('import.file.empty') };
    const names = header.map(headerName);
    const missing = REQUIRED_COLUMNS.filter((c) => !names.includes(c));
    if (missing.length) {
      return {
        rows: [],
        error: this.i18n.t('import.file.missing', { columns: missing.join(', ') }),
      };
    }
    const rows: UserImportRow[] = [];
    for (const rec of body) {
      if (rec.every((c) => c.trim() === '')) continue;
      const cell = (name: string): string => {
        const idx = names.indexOf(name);
        return idx >= 0 ? (rec[idx] ?? '').trim() : '';
      };
      const row: UserImportRow = {
        username: cell('username'),
        full_name: cell('full_name'),
        role: cell('role').toLowerCase() as Role,
      };
      const email = cell('email');
      const mobile = cell('mobile');
      if (email) row.email = email;
      if (mobile) row.mobile = mobile;
      rows.push(row);
    }
    if (!rows.length) return { rows: [], error: this.i18n.t('import.file.noRows') };
    return { rows, error: null };
  }

  private body(dryRun: boolean) {
    return {
      branch_id: this.canPickBranch() && this.branchId() > 0 ? this.branchId() : null,
      dry_run: dryRun,
      rows: this.rows(),
    };
  }
}
