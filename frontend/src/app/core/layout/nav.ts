import { Role } from '../auth/auth.models';
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
  { label: 'Overview', path: '/', icon: 'dashboard' },
  { label: 'Student records', path: '/students', icon: 'users', feature: 'students' },
  {
    label: 'Attendance',
    path: '/attendance',
    icon: 'calendar',
    roles: [...STAFF, 'parent', 'student'],
    feature: 'attendance',
  },
  { label: 'Academic progress', path: '/progress', icon: 'chart', roles: STAFF, soon: true },
  {
    label: 'Noticeboard',
    path: '/notices',
    icon: 'megaphone',
    roles: SCHOOL_USERS,
    unreadBadge: true,
    feature: 'notices',
  },
  { label: 'Fees', path: '/fees', icon: 'wallet', roles: FEE_USERS, feature: 'fees' },
  { label: 'Schools', path: '/schools', icon: 'building', roles: ['super_admin'] },
  {
    label: 'Branches',
    path: '/branches',
    icon: 'building',
    roles: ['super_admin', 'school_owner'],
  },
  { label: 'Users', path: '/users', icon: 'user', roles: USER_ADMINS },
  { label: 'School profile', path: '/school', icon: 'building', roles: ['school_owner'] },
  { label: 'School setup', path: '/setup', icon: 'settings', roles: MANAGERS },
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
