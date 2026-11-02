export type Role =
  | 'super_admin'
  | 'school_owner'
  | 'management'
  | 'headmaster'
  | 'teacher'
  | 'accountant'
  | 'clerk'
  | 'parent'
  | 'student';

export interface User {
  id: number;
  username: string;
  email: string | null;
  full_name: string;
  phone: string | null;
  role: Role;
  school_id: number | null;
  branch_id: number | null;
  is_active: boolean;
  /** Set after an admin reset or a first sign-in: the user must choose a new password first. */
  must_change_password: boolean;
  /** Too many wrong passwords. Only meaningful in the admin users list. */
  is_locked: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthOptions {
  password_reset_enabled: boolean;
}
