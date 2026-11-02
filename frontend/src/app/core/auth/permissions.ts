import { Role } from './auth.models';
import { AuthService } from './auth.service';

export const STUDENT_WRITER_ROLES: Role[] = [
  'super_admin',
  'school_owner',
  'management',
  'headmaster',
  'clerk',
];

/** Admission, edit, enrolment, guardians, logins and import (UX only; the backend enforces it). */
export function canWriteStudents(auth: AuthService): boolean {
  return auth.hasRole(...STUDENT_WRITER_ROLES);
}

/** Fee managers: heads, structure, invoices, discounts, cancel, reverse. */
export const FEE_MANAGER_ROLES: Role[] = ['school_owner', 'management', 'accountant'];
/** Staff who can see invoices, payments and dues. */
export const FEE_VIEW_ROLES: Role[] = [...FEE_MANAGER_ROLES, 'clerk', 'headmaster'];
/** Roles that may record a payment. */
export const FEE_PAY_ROLES: Role[] = [...FEE_MANAGER_ROLES, 'clerk'];

/** Parent and student accounts only see their own records. */
export function isStudentSelfService(auth: AuthService): boolean {
  return auth.hasRole('parent', 'student');
}
