# Roadmap

Phases are built in order; each phase ends with a commit and push. Within a phase, backend and frontend are built in parallel against an agreed API (see "Working method" in [CLAUDE.md](../CLAUDE.md)). Update the status column when a phase changes state.

| # | Phase | Scope | Status |
|---|---|---|---|
| 0 | Foundation | Scaffold, auth (JWT + refresh cookie), multi-tenancy (schools, branches), users and roles, academic years, classes and sections, app shell and design system, PWA | Done |
| 1 | Admin console | Generic branding (school name from data), screens to create schools (platform admin), branches (owner) and users (managers), user edit / deactivate / password reset, change password | Done |
| 2 | Students | Student and guardian records, admission, class and section enrolment per academic year, parent login linked to children (across branches), student profile, CSV import and export | In progress |
| 3 | Attendance | Daily student attendance (present / absent / leave) per section, staff attendance, summaries and calendar view | |
| 4 | Notices | School, branch and class notices, pinning, read status, parent and student view | |
| 5 | Fees | Fee heads and structures per class, invoices, receipts (PDF), dues and reports | |
| 6 | Exams and report cards | Terms, subjects, marks entry, grading (CBSE default, configurable), report card PDF, academic progress | |
| 7 | Timetable and homework | Per-branch timings and periods, timetable, homework | |
| 8 | Staff | Staff records, leave, payroll | |
| 9 | Extras | Certificates (bonafide, transfer, leaving), library, transport | |
| 10 | Dashboards and portals | Real dashboard numbers, parent and student portal views, reports | |
| 11 | Optional integrations | Razorpay payments, SMS and WhatsApp alerts, email, file storage (all off unless `.env` keys are set) | |
| 12 | Hardening and release | Audit log, PostgreSQL row-level security, revoke sessions on password change or reset (tokens are currently not revoked), custom app icons, formal tests, performance, Render deployment, backups | |

## Dependencies

- Students (2) come before attendance, fees and exams.
- Integrations (11) plug into attendance, fees and notices once those exist.

## Known gaps to close later

- Sessions are not revoked on password change or reset (phase 12).
- The overview page shows only counts that exist today; student, attendance and marks cards arrive with their modules.
- Search and notifications in the top bar are disabled placeholders.
