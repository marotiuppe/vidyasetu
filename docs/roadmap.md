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
| 5.1 | Branding and landing page | App logo and icons (browser tab, installed app), school logo upload (when creating or updating a school, plus a school profile page for owners), logo in the sidebar and on receipts, public landing page with animation | Done | 2026-11-02 12:29 | 2026-11-02 12:50 |
| 5.2 | Sign-in and account identity | Username required, mobile number and email optional when creating a user; sign in with username, mobile or email plus password; show/hide password (eye) on the login page; forgot password; "Remember me" (see "Requested changes" below) | Done | 2026-11-02 16:35 | 2026-11-02 16:50 |
| 5.3 | Security hardening | Security headers and strict CSP, rate limiting and account lockout (attempts and lockout time configurable per school, default 3 failed attempts then 1 hour), stronger password policy, forced password change for admin-created accounts, refresh-token rotation with server-side revocation (also fixes "sessions not revoked on password change"), CSRF/origin checks, safe error and log handling, trusted hosts, HTTPS and body-size limits, dependency audit | Done | 2026-11-02 18:05 | 2026-11-02 18:11 |
| 5.4 | Student form and login follow-ups | (a) "Create new..." option in lookup dropdowns, starting with academic year, class and section in the student enrolment form: choosing it opens the matching create screen and returns to the original form with the new record selected and the entered values kept; then rolled out to every other lookup dropdown in the app. (b) Creating a student also creates the student's login automatically (see "Requested changes" below). (c) The student form picks the parent: search and select an existing parent (siblings share one parent login) or enter a new parent, and the parent login is created together with the student. | Done | 2026-11-02 18:15 | 2026-11-02 18:25 |
| 5.5 | Legal pages | Public Privacy Policy, Terms of Use, Children's privacy notice, Cookie and storage notice, Accessibility statement, Grievance page, Security and responsible-disclosure page; operator and grievance-officer details configurable; links in footers | Done | 2026-11-02 18:26 | 2026-11-02 18:32 |
| 5.6 | Consent, audit log, data rights and MFA | Parental consent and policy-acceptance records, audit log with viewer, data access/correction/erasure requests, student data export, TOTP two-factor sign-in for privileged roles | Not started | | |
| 5.7 | Compliance pack and security review | `docs/compliance` (data protection and security policy, incident response, retention schedule, data inventory, control matrix against OWASP / DPDP / CERT-In / GIGW), threat model, authorization sweep, penetration-style checks, fixes, backup and restore drill (moved up from phase 12 so it is proven before real student data is entered) | Not started | | |
| 5.8 | Admissions and enquiries | Enquiry and lead list, online application form, status pipeline (enquiry, applied, admitted, rejected), document upload, convert an admitted applicant into a student record; government identity fields on the student record: PEN, APAAR ID (optional, with a recorded parental consent that can be refused) and optional Aadhaar-matching name, date of birth and gender check, with sensitive ones masked and access-logged | Not started | | |
| 5.9 | Promotion and year-end | Promote a whole class or section to the next academic year in one step (including the move from the primary to the secondary branch), carry over fee dues, mark leavers and detained students, undo window | Not started | | |
| 5.10 | Fee tools | Bulk invoice generation for a class or branch, concessions and scholarships, sibling discounts, late fees, fee reminders (on screen now, SMS and WhatsApp once phase 11 exists) | Not started | | |
| 5.11 | Search, import, export and language | Global search in the top bar (students, guardians, receipts, notices, scoped by role and branch), CSV import with dry-run preview and error report for staff and fees (students already done), Marathi coverage check of every screen, receipt PDF Unicode font (rupee sign, Devanagari names) | Not started | | |
| 6 | Exams and report cards | Terms, subjects, marks entry, grading (CBSE default, configurable), report card PDF, NEP-style Holistic Progress Card (academic, co-curricular and behavioural sections, configurable per school), academic progress | Not started | | |
| 7 | Timetable and homework | Per-branch timings and periods, timetable, homework | Not started | | |
| 8 | Staff | Staff records, leave, payroll | Not started | | |
| 9 | Extras | Certificates (bonafide, transfer, leaving), library, transport | Not started | | |
| 9.1 | Government reporting | UDISE+ student-level data export from live data (needs students, staff and class data from earlier phases), annual data checks and a missing-data report so schools can fix gaps before the submission deadline; format must be checked against the official UDISE+ portal and circulars before building | Not started | | |
| 10 | Dashboards and portals | Separate overview (dashboard) for every role: platform admin (super admin), school owner, management, headmaster, teacher, accountant, clerk, student and parent, each with its own real numbers and cards (see "Requested changes" below); parent and student portal views, reports, parent-teacher messages, parent leave applications with teacher approval, events and calendar, offline attendance marking (sync later) | Not started | | |
| 11 | Optional integrations | Razorpay payments, SMS and WhatsApp alerts, email, file storage (all off unless `.env` keys are set) | Not started | | |
| 12 | Release | PostgreSQL row-level security and PostgreSQL re-check of all modules (payment locking), formal tests, performance, Render deployment and automated backups (the restore drill is in phase 5.7), independent security audit before go-live | Not started | | |

(1) Phase 0 began on the evening of 2026-11-01; the exact start time was not recorded. The first recorded build of the app is 2026-11-01 22:02. Finished = time of the first commit. For phases 1 and 2, *Started* is the time of the first commit or agent launch of that phase.

## Likely gaps for a real school (added 2026-11-02)

Placed in the build order as follows. Order of the 5.x phases was set so that sign-in (5.2) and security (5.3) come first, then the student form and login follow-ups (5.4), then legal, consent and compliance (5.5 to 5.7), then the school-operations gaps (5.8 to 5.11).

| Gap | Phase |
|---|---|
| Admissions and enquiries | 5.8 |
| Promotion and year-end | 5.9 |
| Bulk fee tools (concessions, sibling discounts, late fees, reminders) | 5.10 |
| Import and export, Marathi coverage, receipt font | 5.11 |
| PEN and APAAR fields | 5.8 |
| UDISE+ student-level data export | 9.1 |
| NEP Holistic Progress Card | 6 |
| Backups and restore drill | 5.7 (automation in 12) |
| Global search | 5.11 |
| Parent-teacher messages, leave applications, events calendar, offline attendance | 10 |

Notes: the UDISE+ and APAAR points come from education blogs, not official texts, so confirm them on udiseplus.gov.in, the APAAR portal and CBSE circulars before building. PEN and APAAR are personal identifiers of minors: store them only if the school enables them, keep them out of logs and exports unless needed, and handle them under the consent rules of phase 5.6.

## Plan for phases 5.3 to 5.7 (security and compliance; planned 2026-11-02, not started)

Requested by the owner so the application can pass government and security audits. Nothing in these phases has been built yet.

**What can and cannot be promised.** The software can implement the controls auditors check and ship the documents they ask for. It cannot promise "unhackable" or certify a government audit: that needs an independent assessor (for example a CERT-In empanelled auditor) and the policy texts need legal review before they are relied on.

**Roles for the policies.** The school is the data fiduciary (controller) for its students, parents and staff; the platform operator provides the software and acts as data processor.

**Laws and guidelines to review with a lawyer:** Digital Personal Data Protection Act 2023 and its Rules (check the commencement dates; children's data needs verifiable parental consent and no tracking or targeted advertising), Information Technology Act 2000 and the SPDI Rules 2011 (privacy policy, grievance officer, reasonable security practices), CERT-In Directions 2022 (incident reporting within 6 hours, 180-day log retention in India), GIGW 3.0 and WCAG 2.1 AA (government website policies and accessibility).

**Information needed from the owner before go-live** (all configurable, nothing hard-coded): operator legal name and address, grievance officer name, email and phone, security contact email, privacy contact email, and the hosting region. Note: Render cannot keep logs inside India, which is a CERT-In gap to decide on.

**Design decisions already made**
- Phase 5.3 (security, backend plus matching frontend): strict CSP with `script-src 'self'` and `style-src 'self' 'unsafe-inline'` (Angular injects component styles at runtime) and `inlineCritical: false` in the production build so no inline handlers remain; HSTS and the other headers; `Cache-Control: no-store` on the API; in-memory rate limiter (per process, fine for one Render instance); lockout after a configurable number of failures (default 3) for a configurable time (default 1 hour), set per school (see change 5), with identical generic errors (no user enumeration); password policy of at least 10 characters with a common-password blocklist; `must_change_password` for admin-created accounts and resets; refresh-token rotation with reuse detection and a `token_version` that invalidates access tokens; `X-Requested-With` and Origin checks on cookie endpoints; SameSite=Strict cookie; generic 500 responses, validation errors that never echo submitted values, request IDs, no personal data in logs; trusted hosts, HTTPS redirect, request size limits; production start-up guards (strong secret, no wildcard origins); `pip-audit` and `npm audit`; migration `0010` (the `security.txt` file and the public legal config endpoint move to phase 5.5).
- Phase 5.5 (legal pages, frontend): public pages `/privacy`, `/terms`, `/children`, `/cookies`, `/accessibility`, `/grievance`, `/security` that describe only controls that really exist, with footer links on the landing page, login page and sidebar, and `robots.txt`.
- Phase 5.6: migration `0009` (policy acceptance and parental consent records, append-only audit log with a viewer, data-rights requests, TOTP two-factor sign-in for super admin and school owner via `pyotp`), student data export, access logging for sensitive reads.
- Phase 5.7: `docs/compliance` written after the controls exist so the control matrix is truthful (implemented, partial, planned), plus threat model, incident response and breach-notification procedure, retention schedule, data inventory, vendor list, an authorization sweep over every endpoint, penetration-style checks and fixes.
- 5.2 and 5.5 can run in parallel (backend and frontend agents); 5.4 follows because it needs its own migration.

## Requested changes (added 2026-11-02, not started)

**1. Create-from-dropdown (phase 5.4a).** Every lookup dropdown gets a "Create new..." entry. Selecting it navigates to that record's create screen, remembering where the user came from; after saving, the user returns to the original form with the new record selected and the half-filled form values restored. First target: academic year, class and section in student enrolment. Design: one reusable shared component and a small return-state service (return URL plus draft form values), so each dropdown only declares which create route it links to. The option shows only to roles allowed to create that record.

**2. Separate overview per role (phase 10).** One distinct dashboard for every role instead of a single shared one:
- Platform admin (`super_admin`): schools, branches and users across the platform.
- School owner: all branches of the school: students, attendance, fee collection and dues, notices.
- Management: the same figures for their own branch, with a branch-level summary.
- Headmaster: their branch's attendance today, staff attendance, pending items, notices.
- Teacher: own classes and sections, attendance still to mark today, later timetable, homework and marks entry.
- Accountant: today's collection, pending dues, recent payments, overdue invoices, quick links to collect a fee.
- Clerk: admissions and student records to complete, recent enrolments, quick links to add a student and import CSV.
- Student: own attendance, fees, notices, later timetable and marks.
- Parent: one card per child, plus fees due and notices.

The route stays `/`; the backend returns data per role, scoped by the token (never by client-supplied ids), and the frontend picks the dashboard component from the user's role. A user with several roles sees the one with the widest scope, with a switcher. The student and parent views can ship earlier than the rest of phase 10 if wanted.

**3. Auto-created student login (phase 5.4b).** When a student is created, a user account (role `student`) is created and linked in the same transaction.
- Username: first name + first letter of last name + date of birth.
- Initial password: first name + first letter of last name + `@` + date of birth.
- Open decisions: the date format (suggested `DDMMYYYY`), lower-casing and removing spaces, what to do when the username already exists (suggested: append a number), and what to do when the last name is empty.
- Security note: this password is guessable from public facts about a minor, so the account must be created with `must_change_password` (phase 5.3), so the first sign-in forces a new password. Until 5.2 exists, show the generated credentials once to the admin so they can be handed over, and do not log them. The existing manual "create student login" flow stays for parents.

**4. Sign-in and account identity (phase 5.2).**
- User form: username is required; mobile number and email are optional. Migration adds `mobile` (nullable) and keeps `email` nullable; both are normalised (email lower-cased, mobile stored as digits with country code).
- Login accepts username, mobile or email in one field plus the password. Because all three identify a person, each must be unique among users (partial unique indexes ignoring nulls), and a username must not look like an email or a mobile number so the lookup is never ambiguous. Mobile and email are unique across the platform, since login is not tied to a school. Failed attempts return the same generic error whichever identifier was used (no user enumeration), and the lockout from phase 5.3 counts per account.
- Login page: an eye button toggles password visibility (accessible, `aria-pressed`, label translated in English and Marathi).
- Forgot password: needs a way to reach the user, so it works through the optional email or SMS adapters (Hard rule 4). With no provider configured the link is hidden or explains that an administrator must reset the password (the existing admin reset flow). Reset links are single-use, short-lived, stored hashed, and the response is identical whether or not the account exists. Users with no email or mobile can only be reset by an admin.
- Remember me: refresh-token cookie handling already exists (httpOnly cookie), so this checkbox is not a substitute for it. Checked: persistent cookie (for example 30 days). Unchecked: session cookie that ends when the browser closes, with a shorter server-side expiry. Both stay httpOnly, rotated and revocable (phase 5.3). The tick is hidden or off by default on shared devices.
- Order: the identity change and login lookup can go with 5.2 (they share the login code and migration planning); forgot password depends on phase 11 adapters for actual sending.

**5. Configurable login lockout (phase 5.3, per school).** Default: after 3 failed sign-ins the account cannot sign in for 1 hour. Both numbers (failed attempts allowed, lockout minutes) are settings of each school, edited by the school owner on the School profile page, with sane limits (for example 3 to 10 attempts, 5 minutes to 24 hours) so a school cannot switch protection off. They are stored on the school (migration `0008`) and read from the account's own school at sign-in; platform admins and unknown identifiers use the platform defaults from `.env`/config. The counter resets on a successful sign-in, and the lockout applies to the account, not the device. The response while locked is the same generic error as a wrong password, so it does not reveal that the account exists; the user is told only that sign-in is temporarily unavailable if the identifier is valid for a school that opted into showing it (default: do not show). An admin can unlock an account early from the users screen. Lockout events go to the audit log (phase 5.6).

**6. Choose the parent while creating a student (phase 5.4c).** The guardian section of the student form gets "Select existing parent" (search by name, mobile or username within the school and the user's scope) and "Add new parent" (name, relation, mobile, optional email). Everything happens in one request and one transaction:
- Existing parent selected: the new student's guardian record is linked to that parent login; no new account, so siblings share one login. Children already linked to that parent are shown so the clerk can confirm it is the right person.
- New parent: a parent user is created with a generated username and a temporary password, linked to the guardian record. A new parent whose mobile number matches an existing parent of the school is linked, not duplicated (already supported by the API since 2026-11-02).
- The student's own login is created in the same request (change 3).
- After saving, a one-time "Login details" panel shows the student's and the parent's username and temporary password so the school can print or hand them over; they are never shown again and never logged. Both accounts get `must_change_password` once phase 5.3 provides it.
- Open decision for the owner: how the parent username and password are generated. Suggested: username = parent's first name + first letter of last name + last 4 digits of the mobile number (a number is added on a clash), password = random, shown once. A password built from public facts about a family is guessable, so a random one is safer than the student pattern.
- Secondary guardians (mother, father, guardian) can each be selected or created the same way; the primary guardian is the one that gets the login by default.

## Dependencies

- Students (2) come before attendance, fees and exams.
- Phases 5.3 to 5.7 can run at any point after the modules they protect; they should finish before real student data is entered.
- Integrations (11) plug into attendance, fees and notices once those exist.

## Known gaps to close later

- Phase 5.3 follow-ups: the shorter server-side expiry for "remember me" off is not done; uvicorn access logs include query strings (search terms), so switch them off or scrub them before real data; rate limit and lockout counters are per process (fine for one instance, revisit if scaled); migration `0010` is untested on PostgreSQL (phase 12).
- The overview page shows only counts that exist today; student, attendance and marks cards arrive with their modules.
- Search in the top bar is a disabled placeholder.
- Fees: the receipt PDF uses Helvetica and writes "Rs." (no rupee sign, no Devanagari names) until a Unicode font is bundled; there is no standalone payments list screen yet (the API exists); the currency is a single constant in the frontend (`core/ui/money.ts`) and could become a school setting; payment concurrency (`SELECT ... FOR UPDATE`) is only tested on SQLite, so recheck on PostgreSQL (phase 12). Online payment arrives in phase 11.
- The academic-year to school link is checked in services, not by a database constraint.
