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
  /** Two-factor sign-in is switched on for this account. */
  mfa_enabled?: boolean;
  /** Policy requires two-factor and it is not set up yet: only the setup page is usable. */
  mfa_setup_required?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/** Sign-in answer for an account with two-factor: a short-lived token for the second step. */
export interface MfaChallenge {
  mfa_required: true;
  mfa_token: string;
}

export type LoginResult = { kind: 'signed_in'; user: User } | { kind: 'mfa'; mfaToken: string };

export interface AuthOptions {
  password_reset_enabled: boolean;
}
