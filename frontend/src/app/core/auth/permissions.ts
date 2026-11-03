import { Role } from './auth.models';
import { AuthService } from './auth.service';

export const STUDENT_WRITER_ROLES: Role[] = [
  'super_admin',
  'school_owner',
  'management',
  'headmaster',
  'clerk',
];

/** Admissions desk: enquiries, applications, documents and conversion to a student (UX only). */
export const ADMISSION_ROLES: Role[] = ['school_owner', 'management', 'headmaster', 'clerk'];

/** Roles that may see the full PEN and APAAR values (UX only; the backend enforces it). */
export const IDENTIFIER_REVEAL_ROLES: Role[] = ['school_owner', 'management', 'headmaster'];

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

/** Roles that may open School setup (classes and sections; academic years need school_owner). */
export const SETUP_ROLES: Role[] = ['school_owner', 'management', 'headmaster'];
/** Roles that may create a branch (the Branches screen). */
export const BRANCH_CREATOR_ROLES: Role[] = ['super_admin', 'school_owner'];

/** Year-end promotion: move students to the next year and undo a run (UX only; the backend enforces it). */
export const PROMOTION_ROLES: Role[] = ['school_owner', 'management', 'headmaster'];

/** Roles that read the audit log and handle data-rights requests. */
export const PRIVACY_ADMIN_ROLES: Role[] = [
  'super_admin',
  'school_owner',
  'management',
  'headmaster',
];

/** Exam setup: terms, subjects, class subjects, exams, grading scale, aspects and publish or lock (UX only). */
export const EXAM_CONFIG_ROLES: Role[] = ['school_owner', 'management', 'headmaster'];
/** Staff who enter marks and aspect grades: the setup roles plus teachers of the branch. */
export const EXAM_MARK_ROLES: Role[] = [...EXAM_CONFIG_ROLES, 'teacher'];
/** Staff who may read marks, aspects and class summaries (clerk is read-only). */
export const EXAM_VIEW_ROLES: Role[] = [...EXAM_MARK_ROLES, 'clerk'];
/** Report cards: staff (through a student's profile) and the family of that student. */
export const EXAM_RESULT_ROLES: Role[] = [...EXAM_VIEW_ROLES, 'parent', 'student'];
