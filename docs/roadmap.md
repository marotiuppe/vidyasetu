# Roadmap

Phases are built in order; each phase ends with a commit and push. Within a phase, backend and frontend are built in parallel against an agreed API (see "Working method" in [CLAUDE.md](../CLAUDE.md)).

**Keeping this file up to date:** when a phase starts, fill in *Started*; when it is finished (verified, committed and pushed), fill in *Finished* and set the status to Done. Use real local time (India Standard Time, IST) from `Get-Date`, in the form `YYYY-MM-DD HH:mm`.

| # | Phase | Scope | Status | Started (IST) | Finished (IST) |
|---|---|---|---|---|---|
| 0 | Foundation | Scaffold, auth (JWT + refresh cookie), multi-tenancy (schools, branches), users and roles, academic years, classes and sections, app shell and design system, PWA | Done | 2026-11-01 evening (1) | 2026-11-02 10:56 |
| 1 | Admin console | Generic branding (school name from data), screens to create schools (platform admin), branches (owner) and users (managers), user edit / deactivate / password reset, change password | Done | 2026-11-02 11:11 | 2026-11-02 11:24 |
| 2 | Students | Student and guardian records, admission, class and section enrolment per academic year, parent login linked to children (across branches), student profile, CSV import and export | Done | 2026-11-02 11:26 | 2026-11-02 11:38 |
| 3 | Attendance | Daily student attendance (present / absent / leave) per section, staff attendance, summaries and calendar view, holidays | Done | 2026-11-02 11:39 | 2026-11-02 11:53 |
| 4 | Notices | School, branch and class notices, pinning, read status, parent and student view | Done | 2026-11-02 11:54 | 2026-11-02 12:01 |
| 5 | Fees | Fee heads and structures per class, invoices, receipts (PDF), dues and reports | Done | 2026-11-02 12:03 | 2026-11-02 12:17 |
| 6 | Exams and report cards | Terms, subjects, marks entry, grading (CBSE default, configurable), report card PDF, academic progress | Not started | | |
| 7 | Timetable and homework | Per-branch timings and periods, timetable, homework | Not started | | |
| 8 | Staff | Staff records, leave, payroll | Not started | | |
| 9 | Extras | Certificates (bonafide, transfer, leaving), library, transport | Not started | | |
| 10 | Dashboards and portals | Real dashboard numbers, parent and student portal views, reports | Not started | | |
| 11 | Optional integrations | Razorpay payments, SMS and WhatsApp alerts, email, file storage (all off unless `.env` keys are set) | Not started | | |
| 12 | Hardening and release | Audit log, PostgreSQL row-level security, revoke sessions on password change or reset (tokens are currently not revoked), custom app icons, formal tests, performance, Render deployment, backups | Not started | | |

(1) Phase 0 began on the evening of 2026-11-01; the exact start time was not recorded. The first recorded build of the app is 2026-11-01 22:02. Finished = time of the first commit. For phases 1 and 2, *Started* is the time of the first commit or agent launch of that phase.

## Dependencies

- Students (2) come before attendance, fees and exams.
- Integrations (11) plug into attendance, fees and notices once those exist.

## Known gaps to close later

- Sessions are not revoked on password change or reset (phase 12).
- The overview page shows only counts that exist today; student, attendance and marks cards arrive with their modules.
- Search in the top bar is a disabled placeholder.
- Fees: the receipt PDF uses Helvetica and writes "Rs." (no rupee sign, no Devanagari names) until a Unicode font is bundled; there is no standalone payments list screen yet (the API exists); the currency is a single constant in the frontend (`core/ui/money.ts`) and could become a school setting; payment concurrency (`SELECT ... FOR UPDATE`) is only tested on SQLite, so recheck on PostgreSQL (phase 12). Online payment arrives in phase 11.
- The academic-year to school link is checked in services, not by a database constraint.
