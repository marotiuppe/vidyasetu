import { Routes } from '@angular/router';

import {
  authGuard,
  mfaSetupGuard,
  mustChangePasswordGuard,
  policyGuard,
  publicOnlyMatch,
  roleGuard,
} from './core/auth/auth.guard';
import {
  ADMISSION_ROLES,
  FEE_MANAGER_ROLES,
  FEE_VIEW_ROLES,
  PRIVACY_ADMIN_ROLES,
  PROMOTION_ROLES,
  STUDENT_WRITER_ROLES,
} from './core/auth/permissions';
import { moduleGuard } from './core/api/module.guard';

const LEGAL_CHILDREN: Routes = [
  {
    path: 'privacy',
    data: { title: 'Privacy policy' },
    loadComponent: () => import('./features/legal/privacy-policy').then((m) => m.PrivacyPolicy),
  },
  {
    path: 'terms',
    data: { title: 'Terms of use' },
    loadComponent: () => import('./features/legal/terms-of-use').then((m) => m.TermsOfUse),
  },
  {
    path: 'children',
    data: { title: "Children's privacy" },
    loadComponent: () => import('./features/legal/children-privacy').then((m) => m.ChildrenPrivacy),
  },
  {
    path: 'cookies',
    data: { title: 'Cookies and storage' },
    loadComponent: () => import('./features/legal/cookies-notice').then((m) => m.CookiesNotice),
  },
  {
    path: 'accessibility',
    data: { title: 'Accessibility statement' },
    loadComponent: () =>
      import('./features/legal/accessibility-statement').then((m) => m.AccessibilityStatement),
  },
  {
    path: 'grievance',
    data: { title: 'Grievances' },
    loadComponent: () => import('./features/legal/grievances').then((m) => m.Grievances),
  },
  {
    path: 'security',
    data: { title: 'Security and disclosure' },
    loadComponent: () =>
      import('./features/legal/security-disclosure').then((m) => m.SecurityDisclosure),
  },
];

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
  },
  {
    // Forced (or voluntary) password change. Outside the shell so nothing else is reachable from it.
    path: 'change-password',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/password/change-password').then((m) => m.ChangePassword),
  },
  {
    // Blocking acceptance of the current Privacy Policy and Terms of Use (outside the shell).
    path: 'accept-policies',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/policies/accept-policies').then((m) => m.AcceptPolicies),
  },
  {
    // Online application form for one school (public, no sign-in, outside the shell).
    path: 'apply/:code',
    data: { title: 'Apply for admission' },
    loadComponent: () => import('./features/admissions/apply-page').then((m) => m.ApplyPage),
  },
  {
    // The same pages for one school, reached by its school code (public, no sign-in needed).
    path: 's/:code',
    loadComponent: () => import('./features/legal/legal-layout').then((m) => m.LegalLayout),
    children: LEGAL_CHILDREN,
  },
  {
    // Public landing page for visitors; signed-in users fall through to the shell (dashboard).
    path: '',
    pathMatch: 'full',
    canMatch: [publicOnlyMatch],
    loadComponent: () => import('./features/landing/landing').then((m) => m.Landing),
  },
  {
    // Every signed-in screen renders inside the shell (sidebar + top bar).
    // Give each child route `data: { title }` for the breadcrumb.
    path: '',
    canActivate: [authGuard],
    // Checked on every child navigation: a user who must change the password stays on that screen.
    canActivateChild: [mustChangePasswordGuard, mfaSetupGuard, policyGuard],
    loadComponent: () => import('./core/layout/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        pathMatch: 'full',
        data: { title: 'Overview', titleKey: 'app.nav.overview' },
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'students',
        data: { title: 'Student records', titleKey: 'app.nav.students' },
        canActivate: [moduleGuard('students')],
        loadComponent: () => import('./features/students/student-list').then((m) => m.StudentList),
      },
      {
        path: 'students/new',
        data: { title: 'New admission', titleKey: 'app.crumb.newAdmission' },
        canActivate: [moduleGuard('students'), roleGuard(...STUDENT_WRITER_ROLES)],
        loadComponent: () => import('./features/students/student-form').then((m) => m.StudentForm),
      },
      {
        path: 'students/:id',
        data: { title: 'Student profile', titleKey: 'app.crumb.studentProfile' },
        canActivate: [moduleGuard('students')],
        loadComponent: () =>
          import('./features/students/student-profile').then((m) => m.StudentProfile),
      },
      {
        path: 'admissions',
        data: { title: 'Admissions', titleKey: 'admissions.nav' },
        canActivate: [roleGuard(...ADMISSION_ROLES), moduleGuard('admissions')],
        loadComponent: () =>
          import('./features/admissions/admission-list').then((m) => m.AdmissionList),
      },
      {
        path: 'admissions/new',
        data: { title: 'New enquiry', titleKey: 'admissions.crumb.new' },
        canActivate: [roleGuard(...ADMISSION_ROLES), moduleGuard('admissions')],
        loadComponent: () =>
          import('./features/admissions/admission-new').then((m) => m.AdmissionNew),
      },
      {
        path: 'admissions/:id',
        data: { title: 'Application', titleKey: 'admissions.crumb.detail' },
        canActivate: [roleGuard(...ADMISSION_ROLES), moduleGuard('admissions')],
        loadComponent: () =>
          import('./features/admissions/admission-detail').then((m) => m.AdmissionDetailPage),
      },
      {
        path: 'promotion',
        data: { title: 'Year-end promotion', titleKey: 'promotion.nav' },
        canActivate: [roleGuard(...PROMOTION_ROLES), moduleGuard('students')],
        loadComponent: () => import('./features/promotion/promotion').then((m) => m.Promotion),
      },
      {
        path: 'attendance',
        data: { title: 'Attendance', titleKey: 'app.nav.attendance' },
        canActivate: [
          roleGuard(
            'school_owner',
            'management',
            'headmaster',
            'teacher',
            'accountant',
            'clerk',
            'parent',
            'student',
          ),
          moduleGuard('attendance'),
        ],
        loadComponent: () => import('./features/attendance/attendance').then((m) => m.Attendance),
      },
      {
        path: 'notices',
        data: { title: 'Noticeboard', titleKey: 'app.nav.notices' },
        canActivate: [
          roleGuard(
            'school_owner',
            'management',
            'headmaster',
            'teacher',
            'accountant',
            'clerk',
            'parent',
            'student',
          ),
          moduleGuard('notices'),
        ],
        loadComponent: () => import('./features/notices/notices').then((m) => m.Notices),
      },
      {
        path: 'fees',
        data: { title: 'Fees', titleKey: 'app.nav.fees' },
        canActivate: [
          roleGuard(
            'school_owner',
            'management',
            'accountant',
            'clerk',
            'headmaster',
            'parent',
            'student',
          ),
          moduleGuard('fees'),
        ],
        loadComponent: () => import('./features/fees/fees').then((m) => m.Fees),
      },
      {
        path: 'fees/concessions',
        data: { title: 'Concessions', titleKey: 'fees.tools.nav.concessions' },
        canActivate: [roleGuard(...FEE_VIEW_ROLES), moduleGuard('fees')],
        loadComponent: () =>
          import('./features/fees/concessions-page').then((m) => m.ConcessionsPage),
      },
      {
        path: 'fees/late-fees',
        data: { title: 'Late fees', titleKey: 'fees.tools.nav.lateFees' },
        canActivate: [roleGuard(...FEE_MANAGER_ROLES), moduleGuard('fees')],
        loadComponent: () => import('./features/fees/late-fees-page').then((m) => m.LateFeesPage),
      },
      {
        path: 'fees/reminders',
        data: { title: 'Fee reminders', titleKey: 'fees.tools.nav.reminders' },
        canActivate: [roleGuard(...FEE_VIEW_ROLES), moduleGuard('fees')],
        loadComponent: () => import('./features/fees/reminders-page').then((m) => m.RemindersPage),
      },
      {
        path: 'fees/import',
        data: { title: 'Import fee structure', titleKey: 'fees.import.crumb' },
        canActivate: [roleGuard(...FEE_MANAGER_ROLES), moduleGuard('fees')],
        loadComponent: () => import('./features/fees/fee-import').then((m) => m.FeeImport),
      },
      {
        path: 'setup',
        data: { title: 'School setup', titleKey: 'app.nav.setup' },
        canActivate: [roleGuard('school_owner', 'management', 'headmaster')],
        loadComponent: () => import('./features/setup/setup').then((m) => m.Setup),
      },
      {
        path: 'school',
        data: { title: 'School profile', titleKey: 'app.nav.schoolProfile' },
        canActivate: [roleGuard('school_owner')],
        loadComponent: () =>
          import('./features/school-profile/school-profile').then((m) => m.SchoolProfile),
      },
      {
        path: 'schools',
        data: { title: 'Schools', titleKey: 'app.nav.schools' },
        canActivate: [roleGuard('super_admin')],
        loadComponent: () => import('./features/schools/schools').then((m) => m.Schools),
      },
      {
        path: 'branches',
        data: { title: 'Branches', titleKey: 'app.nav.branches' },
        canActivate: [roleGuard('super_admin', 'school_owner')],
        loadComponent: () => import('./features/branches/branches').then((m) => m.Branches),
      },
      {
        path: 'users',
        data: { title: 'Users', titleKey: 'app.nav.users' },
        canActivate: [roleGuard('super_admin', 'school_owner', 'management', 'headmaster')],
        loadComponent: () => import('./features/users/users').then((m) => m.Users),
      },
      {
        path: 'users/import',
        data: { title: 'Import users', titleKey: 'users.import.crumb' },
        canActivate: [roleGuard('school_owner', 'management', 'headmaster')],
        loadComponent: () => import('./features/users/users-import').then((m) => m.UsersImport),
      },
      {
        path: 'settings',
        data: { title: 'Settings', titleKey: 'nav.settings' },
        loadComponent: () => import('./features/settings/settings').then((m) => m.Settings),
      },
      {
        path: 'settings/privacy',
        data: { title: 'Privacy and data', titleKey: 'app.crumb.privacyData' },
        loadComponent: () => import('./features/privacy/privacy').then((m) => m.Privacy),
      },
      {
        path: 'account/mfa',
        data: { title: 'Two-factor sign-in', titleKey: 'app.crumb.twoFactor' },
        loadComponent: () => import('./features/mfa/mfa-setup').then((m) => m.MfaSetup),
      },
      {
        path: 'audit',
        data: { title: 'Audit log', titleKey: 'nav.audit' },
        canActivate: [roleGuard(...PRIVACY_ADMIN_ROLES)],
        loadComponent: () => import('./features/audit/audit').then((m) => m.Audit),
      },
      {
        path: 'data-requests',
        data: { title: 'Data requests', titleKey: 'nav.dataRequests' },
        canActivate: [roleGuard(...PRIVACY_ADMIN_ROLES)],
        loadComponent: () =>
          import('./features/data-requests/data-requests').then((m) => m.DataRequests),
      },
      {
        path: 'account',
        data: { title: 'Account', titleKey: 'app.crumb.account' },
        loadComponent: () => import('./features/account/account').then((m) => m.Account),
      },
    ],
  },
  {
    // Public legal pages: outside the shell and without authGuard, so visitors and signed-in users can read them.
    path: '',
    loadComponent: () => import('./features/legal/legal-layout').then((m) => m.LegalLayout),
    children: LEGAL_CHILDREN,
  },
  { path: '**', redirectTo: '' },
];
