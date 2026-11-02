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
}

const STAFF: Role[] = ['school_owner', 'management', 'headmaster', 'teacher', 'accountant', 'clerk'];
const MANAGERS: Role[] = ['school_owner', 'management', 'headmaster'];
const USER_ADMINS: Role[] = ['super_admin', ...MANAGERS];

/** Sidebar navigation. When a module ships, remove its `soon` flag. */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Overview', path: '/', icon: 'dashboard' },
  { label: 'Student records', path: '/students', icon: 'users' },
  { label: 'Attendance', path: '/attendance', icon: 'calendar', roles: STAFF, soon: true },
  { label: 'Academic progress', path: '/progress', icon: 'chart', roles: STAFF, soon: true },
  { label: 'Noticeboard', path: '/notices', icon: 'megaphone', soon: true },
  { label: 'Schools', path: '/schools', icon: 'building', roles: ['super_admin'] },
  { label: 'Branches', path: '/branches', icon: 'building', roles: ['super_admin', 'school_owner'] },
  { label: 'Users', path: '/users', icon: 'user', roles: USER_ADMINS },
  { label: 'School setup', path: '/setup', icon: 'settings', roles: MANAGERS },
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
