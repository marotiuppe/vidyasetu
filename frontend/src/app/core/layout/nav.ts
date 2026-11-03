import { Role } from '../auth/auth.models';
import { ADMISSION_ROLES, PRIVACY_ADMIN_ROLES, PROMOTION_ROLES } from '../auth/permissions';
import { IconName } from '../ui/icon';

export interface NavItem {
  label: string;
  path: string;
  icon: IconName;
  /** Roles that see this item. Omit for everyone. */
  roles?: Role[];
  /** Module not built yet: shown greyed out, not clickable. */
  soon?: boolean;
  /** Show the unread-notices count next to the label. */
  unreadBadge?: boolean;
  /** Translation key for the label (falls back to `label`). */
  labelKey?: string;
  /** Module switch from /settings/levels; the item is hidden when the server says it is off. */
  feature?: string;
}

const STAFF: Role[] = [
  'school_owner',
  'management',
  'headmaster',
  'teacher',
  'accountant',
  'clerk',
];
const MANAGERS: Role[] = ['school_owner', 'management', 'headmaster'];
const SCHOOL_USERS: Role[] = [...STAFF, 'parent', 'student'];
const FEE_USERS: Role[] = [
  'school_owner',
  'management',
  'accountant',
  'clerk',
  'headmaster',
  'parent',
  'student',
];
const USER_ADMINS: Role[] = ['super_admin', ...MANAGERS];

/** Sidebar navigation. When a module ships, remove its `soon` flag. */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Overview', labelKey: 'app.nav.overview', path: '/', icon: 'dashboard' },
  {
    label: 'Student records',
    labelKey: 'app.nav.students',
    path: '/students',
    icon: 'users',
    feature: 'students',
  },
  {
    label: 'Admissions',
    labelKey: 'admissions.nav',
    path: '/admissions',
    icon: 'idcard',
    roles: ADMISSION_ROLES,
    feature: 'admissions',
  },
  {
    label: 'Year-end promotion',
    labelKey: 'promotion.nav',
    path: '/promotion',
    icon: 'sparkle',
    roles: PROMOTION_ROLES,
    feature: 'students',
  },
  {
    label: 'Attendance',
    labelKey: 'app.nav.attendance',
    path: '/attendance',
    icon: 'calendar',
    roles: [...STAFF, 'parent', 'student'],
    feature: 'attendance',
  },
  {
    label: 'Academic progress',
    labelKey: 'app.nav.progress',
    path: '/progress',
    icon: 'chart',
    roles: STAFF,
    soon: true,
  },
  {
    label: 'Noticeboard',
    labelKey: 'app.nav.notices',
    path: '/notices',
    icon: 'megaphone',
    roles: SCHOOL_USERS,
    unreadBadge: true,
    feature: 'notices',
  },
  {
    label: 'Fees',
    labelKey: 'app.nav.fees',
    path: '/fees',
    icon: 'wallet',
    roles: FEE_USERS,
    feature: 'fees',
  },
  {
    label: 'Schools',
    labelKey: 'app.nav.schools',
    path: '/schools',
    icon: 'building',
    roles: ['super_admin'],
  },
  {
    label: 'Branches',
    labelKey: 'app.nav.branches',
    path: '/branches',
    icon: 'building',
    roles: ['super_admin', 'school_owner'],
  },
  {
    label: 'Users',
    labelKey: 'app.nav.users',
    path: '/users',
    icon: 'user',
    roles: USER_ADMINS,
  },
  {
    label: 'Audit log',
    labelKey: 'nav.audit',
    path: '/audit',
    icon: 'history',
    roles: PRIVACY_ADMIN_ROLES,
  },
  {
    label: 'Data requests',
    labelKey: 'nav.dataRequests',
    path: '/data-requests',
    icon: 'inbox',
    roles: PRIVACY_ADMIN_ROLES,
  },
  {
    label: 'School profile',
    labelKey: 'app.nav.schoolProfile',
    path: '/school',
    icon: 'building',
    roles: ['school_owner'],
  },
  {
    label: 'School setup',
    labelKey: 'app.nav.setup',
    path: '/setup',
    icon: 'settings',
    roles: MANAGERS,
  },
  { label: 'Settings', labelKey: 'nav.settings', path: '/settings', icon: 'gear' },
];

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'Platform admin',
  school_owner: 'School owner',
  management: 'Management',
  headmaster: 'Headmaster',
  teacher: 'Teacher',
  accountant: 'Accountant',
  clerk: 'Clerk',
  parent: 'Parent',
  student: 'Student',
};

/** Translation key for each role's label (translate with `i18n.t`). `ROLE_LABELS` stays as the English fallback. */
export const ROLE_LABEL_KEYS: Record<Role, string> = {
  super_admin: 'app.role.super_admin',
  school_owner: 'app.role.school_owner',
  management: 'app.role.management',
  headmaster: 'app.role.headmaster',
  teacher: 'app.role.teacher',
  accountant: 'app.role.accountant',
  clerk: 'app.role.clerk',
  parent: 'app.role.parent',
  student: 'app.role.student',
};
