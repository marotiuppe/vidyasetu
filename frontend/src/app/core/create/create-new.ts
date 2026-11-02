import { AuthService } from '../auth/auth.service';
import { BRANCH_CREATOR_ROLES, SETUP_ROLES } from '../auth/permissions';

/** Kinds of lookup record that can be created from a dropdown. */
export type CreateKind = 'academic_year' | 'class' | 'section' | 'branch';

/** Value of the "Create new..." option. Real ids are positive, so -1 never clashes with one. */
export const CREATE_NEW = -1;
export const CREATE_NEW_LABEL = '+ Create new...';

/** The screen that creates each kind of record. */
export const CREATE_ROUTES: Record<CreateKind, string> = {
  academic_year: '/setup',
  class: '/setup',
  section: '/setup',
  branch: '/branches',
};

/** Human label used in the banner on the create screen. */
export const CREATE_LABELS: Record<CreateKind, string> = {
  academic_year: 'academic year',
  class: 'class',
  section: 'section',
  branch: 'branch',
};

/** Whether the signed-in user may open the create screen for this kind (UX only; the backend enforces it). */
export function canCreateRecord(auth: AuthService, kind: CreateKind): boolean {
  switch (kind) {
    case 'academic_year':
      return auth.hasRole('school_owner');
    case 'class':
    case 'section':
      return auth.hasRole(...SETUP_ROLES);
    case 'branch':
      return auth.hasRole(...BRANCH_CREATOR_ROLES);
  }
}

/** True when a DOM select's change event picked the "Create new..." option. */
export function isCreateNewChange(event: Event): boolean {
  return (event.target as HTMLSelectElement | null)?.value === String(CREATE_NEW);
}

/** Return targets must be in-app paths (no protocol, no protocol-relative host). */
export function safeReturnUrl(value: string | null | undefined): string | null {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\'))
    return null;
  return value;
}

/** Parse a positive id from a query parameter, or null. */
export function idParam(value: string | null): number | null {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/** Filter or form field names for each kind of record that a dropdown can create. */
export const FILTER_KINDS = {
  branchId: 'branch',
  yearId: 'academic_year',
  classId: 'class',
  sectionId: 'section',
} as const satisfies Record<string, CreateKind>;

/** Field names of the filter objects for each kind of record (used when a page returns from a create screen). */
export const FILTER_FIELDS = {
  branch: 'branchId',
  academic_year: 'yearId',
  class: 'classId',
  section: 'sectionId',
} as const;

/** Which "Create new..." options the signed-in user sees. */
export function createPermissions(auth: AuthService): Record<CreateKind, boolean> {
  return {
    academic_year: canCreateRecord(auth, 'academic_year'),
    class: canCreateRecord(auth, 'class'),
    section: canCreateRecord(auth, 'section'),
    branch: canCreateRecord(auth, 'branch'),
  };
}
