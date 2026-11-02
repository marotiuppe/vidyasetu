import { Routes } from '@angular/router';

import {
  authGuard,
  mustChangePasswordGuard,
  publicOnlyMatch,
  roleGuard,
} from './core/auth/auth.guard';
import { STUDENT_WRITER_ROLES } from './core/auth/permissions';

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
    canActivateChild: [mustChangePasswordGuard],
    loadComponent: () => import('./core/layout/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        pathMatch: 'full',
        data: { title: 'Overview' },
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'students',
        data: { title: 'Student records' },
        loadComponent: () => import('./features/students/student-list').then((m) => m.StudentList),
      },
      {
        path: 'students/new',
        data: { title: 'New admission' },
        canActivate: [roleGuard(...STUDENT_WRITER_ROLES)],
        loadComponent: () => import('./features/students/student-form').then((m) => m.StudentForm),
      },
      {
        path: 'students/:id',
        data: { title: 'Student profile' },
        loadComponent: () =>
          import('./features/students/student-profile').then((m) => m.StudentProfile),
      },
      {
        path: 'attendance',
        data: { title: 'Attendance' },
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
        ],
        loadComponent: () => import('./features/attendance/attendance').then((m) => m.Attendance),
      },
      {
        path: 'notices',
        data: { title: 'Noticeboard' },
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
        ],
        loadComponent: () => import('./features/notices/notices').then((m) => m.Notices),
      },
      {
        path: 'fees',
        data: { title: 'Fees' },
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
        ],
        loadComponent: () => import('./features/fees/fees').then((m) => m.Fees),
      },
      {
        path: 'setup',
        data: { title: 'School setup' },
        canActivate: [roleGuard('school_owner', 'management', 'headmaster')],
        loadComponent: () => import('./features/setup/setup').then((m) => m.Setup),
      },
      {
        path: 'school',
        data: { title: 'School profile' },
        canActivate: [roleGuard('school_owner')],
        loadComponent: () =>
          import('./features/school-profile/school-profile').then((m) => m.SchoolProfile),
      },
      {
        path: 'schools',
        data: { title: 'Schools' },
        canActivate: [roleGuard('super_admin')],
        loadComponent: () => import('./features/schools/schools').then((m) => m.Schools),
      },
      {
        path: 'branches',
        data: { title: 'Branches' },
        canActivate: [roleGuard('super_admin', 'school_owner')],
        loadComponent: () => import('./features/branches/branches').then((m) => m.Branches),
      },
      {
        path: 'users',
        data: { title: 'Users' },
        canActivate: [roleGuard('super_admin', 'school_owner', 'management', 'headmaster')],
        loadComponent: () => import('./features/users/users').then((m) => m.Users),
      },
      {
        path: 'account',
        data: { title: 'Account' },
        loadComponent: () => import('./features/account/account').then((m) => m.Account),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
