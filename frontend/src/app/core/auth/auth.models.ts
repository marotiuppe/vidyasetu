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
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  school_id: number | null;
  branch_id: number | null;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}
