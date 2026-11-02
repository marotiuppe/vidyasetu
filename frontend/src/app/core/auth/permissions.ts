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

/** Parent and student accounts only see their own records. */
export function isStudentSelfService(auth: AuthService): boolean {
  return auth.hasRole('parent', 'student');
}
