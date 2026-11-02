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
| 5.6 | Settings and configuration | One Settings area in the app with three levels: platform (platform admin), school and branch (school owner and managers) and personal (every user, including parents and students). Replaces editing `.env` for everything that is not a bootstrap secret; legal and contact details, integrations, lockout and policy limits, school rules and personal preferences all move here (see "Settings and configuration design" below) | Done | 2026-11-02 20:45 | 2026-11-02 20:51 |
| 5.7 | Consent, audit log, data rights and MFA | Parental consent and policy-acceptance records, audit log with viewer, data access/correction/erasure requests, student data export, TOTP two-factor sign-in for privileged roles | Done | 2026-11-02 20:51 | 2026-11-02 21:11 |
| 5.8 | Compliance pack and security review | `docs/compliance` (data protection and security policy, incident response, retention schedule, data inventory, control matrix against OWASP / DPDP / CERT-In / GIGW), threat model, authorization sweep, penetration-style checks, fixes, backup and restore drill (moved up from phase 12 so it is proven before real student data is entered) | Not started | | |
| 5.9 | Admissions and enquiries | Enquiry and lead list, online application form, status pipeline (enquiry, applied, admitted, rejected), document upload, convert an admitted applicant into a student record; government identity fields on the student record: PEN, APAAR ID (optional, with a recorded parental consent that can be refused) and optional Aadhaar-matching name, date of birth and gender check, with sensitive ones masked and access-logged | Not started | | |
| 5.10 | Promotion and year-end | Promote a whole class or section to the next academic year in one step (including the move from the primary to the secondary branch), carry over fee dues, mark leavers and detained students, undo window | Not started | | |
| 5.11 | Fee tools | Bulk invoice generation for a class or branch, concessions and scholarships, sibling discounts, late fees, fee reminders (on screen now, SMS and WhatsApp once phase 11 exists) | Not started | | |
| 5.12 | Search, import, export and language | Global search in the top bar (students, guardians, receipts, notices, scoped by role and branch), CSV import with dry-run preview and error report for staff and fees (students already done), Marathi coverage check of every screen, receipt PDF Unicode font (rupee sign, Devanagari names) | Not started | | |
| 6 | Exams and report cards | Terms, subjects, marks entry, grading (CBSE default, configurable), report card PDF, NEP-style Holistic Progress Card (academic, co-curricular and behavioural sections, configurable per school), academic progress | Not started | | |
| 7 | Timetable and homework | Per-branch timings and periods, timetable, homework | Not started | | |
| 8 | Staff | Staff records, leave, payroll | Not started | | |
| 9 | Extras | Certificates (bonafide, transfer, leaving), library, transport | Not started | | |
| 9.1 | Government reporting | UDISE+ student-level data export from live data (needs students, staff and class data from earlier phases), annual data checks and a missing-data report so schools can fix gaps before the submission deadline; format must be checked against the official UDISE+ portal and circulars before building | Not started | | |
| 10 | Dashboards and portals | Separate overview (dashboard) for every role: platform admin (super admin), school owner, management, headmaster, teacher, accountant, clerk, student and parent, each with its own real numbers and cards (see "Requested changes" below); parent and student portal views, reports, parent-teacher messages, parent leave applications with teacher approval, events and calendar, offline attendance marking (sync later) | Not started | | |
| 11 | Optional integrations | Razorpay payments, SMS and WhatsApp alerts, email, file storage (all off unless `.env` keys are set) | Not started | | |
| 12 | Release | PostgreSQL row-level security and PostgreSQL re-check of all modules (payment locking), formal tests, performance, Render deployment and automated backups (the restore drill is in phase 5.8), independent security audit before go-live | Not started | | |

(1) Phase 0 began on the evening of 2026-11-01; the exact start time was not recorded. The first recorded build of the app is 2026-11-01 22:02. Finished = time of the first commit. For phases 1 and 2, *Started* is the time of the first commit or agent launch of that phase.

## Likely gaps for a real school (added 2026-11-02)

Placed in the build order as follows. Order of the 5.x phases was set so that sign-in (5.2) and security (5.3) come first, then the student form and login follow-ups (5.4), then legal, consent and compliance (5.5 to 5.8), then the school-operations gaps (5.9 to 5.12).

| Gap | Phase |
|---|---|
| Admissions and enquiries | 5.9 |
| Promotion and year-end | 5.10 |
| Bulk fee tools (concessions, sibling discounts, late fees, reminders) | 5.11 |
| Import and export, Marathi coverage, receipt font | 5.12 |
| PEN and APAAR fields | 5.9 |
| UDISE+ student-level data export | 9.1 |
| NEP Holistic Progress Card | 6 |
| Backups and restore drill | 5.8 (automation in 12) |
| Global search | 5.12 |
| Parent-teacher messages, leave applications, events calendar, offline attendance | 10 |

Notes: the UDISE+ and APAAR points come from education blogs, not official texts, so confirm them on udiseplus.gov.in, the APAAR portal and CBSE circulars before building. PEN and APAAR are personal identifiers of minors: store them only if the school enables them, keep them out of logs and exports unless needed, and handle them under the consent rules of phase 5.7.

## Settings and configuration design (added 2026-11-02, phase 5.6)

**Goal.** Everything an operator, school or user may want to change is changed inside the application, on one "Settings" page, not by editing `.env` or asking a developer. `.env` keeps only bootstrap values that must exist before the app can start or that protect the settings themselves: `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`, `ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, the proxy and rate-limit switches, and a `SETTINGS_ENCRYPTION_KEY`. Every other variable (operator and grievance details added in phase 5.5, integration keys, defaults) becomes a setting with the `.env` value as a fallback default, so existing deployments keep working.

**Page.** One sidebar entry "Settings" (for everyone) opening a page with tabs for the levels the signed-in user may see: Platform, School, Branch, My settings. Each setting shows a label, help text, its current value, where the value comes from (own value, inherited from school or platform, or default) and "Reset to default". Sections are searchable, changes are validated on the server, shown with who changed them and when, and written to the audit log once phase 5.7 exists. No setting is hard-coded in the UI; the page is built from a server-side registry.

**Storage and resolution.** A typed settings registry in code (key, level, type, default, allowed range, who may edit, whether it is secret, optional `.env` fallback) and two tables: `settings` (level `platform`, `school` or `branch`, owner id, key, JSON value, updated by, updated at) and `user_preferences` (user id, key, value). Value lookup order: user, branch, school, platform, `.env` fallback, code default. Every read and write goes through one service that derives the school and branch from the token (never from the client), so isolation between schools and branches holds. Secret values (SMS, WhatsApp, SMTP and Razorpay credentials) are encrypted with `SETTINGS_ENCRYPTION_KEY`, are write-only in the UI (shown as set or not set, never returned by the API), and each integration has a "Send test" action. An integration is enabled only when its settings are filled (Hard rule 4 stays true).

**Who can edit what**

| Level | Who edits | Who can view |
|---|---|---|
| Platform | platform admin | platform admin |
| School | school owner (some items also management) | school owner, management, headmaster |
| Branch | school owner, management, headmaster of that branch | staff of that branch |
| Personal | each user for themselves | the user |

**Platform settings (platform admin)**
- Operator details for the legal pages: operator name, address, email, phone, security contact, hosting region, policy effective date and policy versions (moved from `.env`).
- Platform name and logo, support contact, an optional announcement banner and a maintenance message.
- Limits that schools may not go beyond: allowed range for lockout attempts and minutes, minimum password length (never below 10), maximum remember-me days.
- Default values new schools start with (board, language, academic year start month, lockout, feature set).
- Modules switched on or off per school (feature flags), and which integration providers are offered.
- Shared integration accounts schools may use when they bring none (SMS, email), with usage visible per school.

**School settings (school owner; the school is the data fiduciary)**
- Profile: name, logo, board, address, contact details, website (the existing School profile page becomes part of this).
- Legal and contact details for that school: grievance officer name, email, phone and response time, privacy contact, data retention note. Public legal pages for a school are reached by its school code (for example `/s/<code>/grievance`), signed-in users see their own school's details automatically, and the platform operator details come from the platform level.
- Security: failed sign-in attempts and lockout minutes (already built in phase 5.3, moved here), remember-me days, stricter password length, whether forced password change applies to new accounts, MFA required for chosen roles (phase 5.7).
- Academic: academic year start month (default April), default language, grading scheme and report card options (phase 6), attendance rules (late cut-off, how many days back staff may edit, absent alerts on or off), notice defaults (expiry days).
- Fees: receipt prefix and numbering, receipt footer text, late fee and concession rules (phase 5.11), payment link on or off, currency display.
- Parent and student portal: which sections parents and students see (fees, marks, attendance), whether students get logins, how generated passwords are formed.
- Integrations with the school's own accounts: SMS sender and templates, WhatsApp, SMTP email, Razorpay, file storage (phase 11), each with enable switch and test button.
- Data: retention periods per record type, export of the school's data.

**Branch settings (owner, management, headmaster)**
- Timings and working days per branch, headmaster and management contact, fee structure defaults, attendance start time, holiday calendar defaults, timetable periods (phase 7).

**Personal settings (every user, with parent and student views kept simple)**
- Language (English or Marathi), display preferences, change password, active sessions with "sign out other devices", optional two-factor setup (phase 5.7).
- Contact details: mobile and email with a verification step once SMS or email adapters exist.
- Notification preferences: which alerts (attendance, fees due, notices, exam results) by app, SMS, WhatsApp or email, honouring the school's consent rules.
- Parent: the children linked to the login and a request to link or unlink a child (handled by the school).
- Student: only the items that suit a minor; the school can hide the rest.
- Privacy: download my data and request correction or erasure (phase 5.7), view accepted policy versions.

**Delivery plan.** (1) Registry, tables, service, API and the Settings shell page with the personal level and the school items already built (profile, lockout). (2) Move legal and contact details from `.env` to the settings, and add the per-school legal page route. (3) Encrypted integration settings and test actions (the adapters themselves arrive in phase 11). (4) Platform level and feature flags. Later phases register their own settings in the registry instead of adding env variables or new pages, so this becomes the rule for all new configuration.

## Plan for phases 5.3 to 5.8 (security and compliance; planned 2026-11-02, not started)

Requested by the owner so the application can pass government and security audits. Nothing in these phases has been built yet.

**What can and cannot be promised.** The software can implement the controls auditors check and ship the documents they ask for. It cannot promise "unhackable" or certify a government audit: that needs an independent assessor (for example a CERT-In empanelled auditor) and the policy texts need legal review before they are relied on.

**Roles for the policies.** The school is the data fiduciary (controller) for its students, parents and staff; the platform operator provides the software and acts as data processor.

**Laws and guidelines to review with a lawyer:** Digital Personal Data Protection Act 2023 and its Rules (check the commencement dates; children's data needs verifiable parental consent and no tracking or targeted advertising), Information Technology Act 2000 and the SPDI Rules 2011 (privacy policy, grievance officer, reasonable security practices), CERT-In Directions 2022 (incident reporting within 6 hours, 180-day log retention in India), GIGW 3.0 and WCAG 2.1 AA (government website policies and accessibility).

**Information needed from the owner before go-live** (all configurable, nothing hard-coded): operator legal name and address, grievance officer name, email and phone, security contact email, privacy contact email, and the hosting region. Note: Render cannot keep logs inside India, which is a CERT-In gap to decide on.

**Design decisions already made**
- Phase 5.3 (security, backend plus matching frontend): strict CSP with `script-src 'self'` and `style-src 'self' 'unsafe-inline'` (Angular injects component styles at runtime) and `inlineCritical: false` in the production build so no inline handlers remain; HSTS and the other headers; `Cache-Control: no-store` on the API; in-memory rate limiter (per process, fine for one Render instance); lockout after a configurable number of failures (default 3) for a configurable time (default 1 hour), set per school (see change 5), with identical generic errors (no user enumeration); password policy of at least 10 characters with a common-password blocklist; `must_change_password` for admin-created accounts and resets; refresh-token rotation with reuse detection and a `token_version` that invalidates access tokens; `X-Requested-With` and Origin checks on cookie endpoints; SameSite=Strict cookie; generic 500 responses, validation errors that never echo submitted values, request IDs, no personal data in logs; trusted hosts, HTTPS redirect, request size limits; production start-up guards (strong secret, no wildcard origins); `pip-audit` and `npm audit`; migration `0010` (the `security.txt` file and the public legal config endpoint move to phase 5.5).
- Phase 5.5 (legal pages, frontend): public pages `/privacy`, `/terms`, `/children`, `/cookies`, `/accessibility`, `/grievance`, `/security` that describe only controls that really exist, with footer links on the landing page, login page and sidebar, and `robots.txt`.
- Phase 5.7: a new migration (policy acceptance and parental consent records, append-only audit log with a viewer, data-rights requests, TOTP two-factor sign-in for super admin and school owner via `pyotp`), student data export, access logging for sensitive reads.
- Phase 5.8: `docs/compliance` written after the controls exist so the control matrix is truthful (implemented, partial, planned), plus threat model, incident response and breach-notification procedure, retention schedule, data inventory, vendor list, an authorization sweep over every endpoint, penetration-style checks and fixes.
- Built so far: 5.2, 5.3, 5.4 and 5.5. Phase 5.6 (settings) comes before 5.7 so that consent, audit and MFA options are registered as settings from the start; 5.8 follows 5.7 because the control matrix must describe controls that exist.

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

**5. Configurable login lockout (phase 5.3, per school).** Default: after 3 failed sign-ins the account cannot sign in for 1 hour. Both numbers (failed attempts allowed, lockout minutes) are settings of each school, edited by the school owner on the School profile page, with sane limits (for example 3 to 10 attempts, 5 minutes to 24 hours) so a school cannot switch protection off. They are stored on the school (migration `0008`) and read from the account's own school at sign-in; platform admins and unknown identifiers use the platform defaults from `.env`/config. The counter resets on a successful sign-in, and the lockout applies to the account, not the device. The response while locked is the same generic error as a wrong password, so it does not reveal that the account exists; the user is told only that sign-in is temporarily unavailable if the identifier is valid for a school that opted into showing it (default: do not show). An admin can unlock an account early from the users screen. Lockout events go to the audit log (phase 5.7).

**6. Choose the parent while creating a student (phase 5.4c).** The guardian section of the student form gets "Select existing parent" (search by name, mobile or username within the school and the user's scope) and "Add new parent" (name, relation, mobile, optional email). Everything happens in one request and one transaction:
- Existing parent selected: the new student's guardian record is linked to that parent login; no new account, so siblings share one login. Children already linked to that parent are shown so the clerk can confirm it is the right person.
- New parent: a parent user is created with a generated username and a temporary password, linked to the guardian record. A new parent whose mobile number matches an existing parent of the school is linked, not duplicated (already supported by the API since 2026-11-02).
- The student's own login is created in the same request (change 3).
- After saving, a one-time "Login details" panel shows the student's and the parent's username and temporary password so the school can print or hand them over; they are never shown again and never logged. Both accounts get `must_change_password` once phase 5.3 provides it.
- Open decision for the owner: how the parent username and password are generated. Suggested: username = parent's first name + first letter of last name + last 4 digits of the mobile number (a number is added on a clash), password = random, shown once. A password built from public facts about a family is guessable, so a random one is safer than the student pattern.
- Secondary guardians (mother, father, guardian) can each be selected or created the same way; the primary guardian is the one that gets the login by default.

## Phase 5.6 and 5.7 follow-ups (updated 2026-11-02, after the verification pass)

- Built and verified by API (SQLite, and PostgreSQL 16 from a portable copy): settings registry and resolution, encrypted write-only secrets, feature flags, lockout limits, password minimum, MFA with replay protection, forced password change, policy acceptance (now also enforced by the backend), consent (latest wins), data requests, exports, tenant isolation (43 cross-school and cross-branch checks), audit log with append-only triggers on PostgreSQL, concurrent payments (`SELECT ... FOR UPDATE`).
- A QA click-through found and fixed: the home route showed a legal page to everyone, a 500 when privacy and terms were accepted at the same time, missing audit rows for money and attendance writes (added; the last batch for attendance, notices, schools, branches and academics is committed but not yet re-tested through the UI), naive timestamps (now UTC with offset), colour contrast, the login rate limit default (now 30 per minute).
- Still NOT click-tested in a browser: super admin screens and the forced MFA setup, student creation with the parent picker, fee, attendance and notice screens, every Settings tab, privacy page, audit and data-request screens, role navigation for management, headmaster, accountant, clerk, teacher, parent and student, PWA install, and the fix for the home route.
- Settings that are stored but have no consumer yet: portal marks visibility (needs exams), payment link (needs the Razorpay adapter), absent alerts (needs SMS/WhatsApp), branch timings, notification preferences, all integration keys, retention days, year start month, default language of a school.
- Open decision: the student starter password is built from name and date of birth (as specified in "Requested changes" item 3); a random password shown once is safer.
- Erasure requests are a workflow only; nothing is deleted automatically. A school owner can reset another owner's two-factor in the same school.
- Marathi was written by an agent and needs a native-speaker review; long legal prose stays English only.
- Audit retention and the CERT-In 180-day rule for logs in India are decided in phase 5.8. TRUNCATE is not blocked on the append-only tables.
- Check at deploy: the `uharfbuzz` wheel installs on Render's Linux.

## Dependencies

- Students (2) come before attendance, fees and exams.
- Phases 5.3 to 5.8 can run at any point after the modules they protect; they should finish before real student data is entered.
- Integrations (11) plug into attendance, fees and notices once those exist.

## Known gaps to close later

- Rate limit and lockout counters are per process (fine for one instance, revisit if scaled). Closed in the verification pass: the "remember me off" server-side expiry, access-log query strings, the receipt font (Noto Sans and Devanagari, rupee sign) and PostgreSQL testing of migrations `0010` to `0012`.
- The overview page shows only counts that exist today; student, attendance and marks cards arrive with their modules.
- Search in the top bar is a disabled placeholder (phase 5.12).
- Fees: there is no standalone payments list screen yet (the API exists); the currency is a single constant in the frontend (`core/ui/money.ts`) and could become a school setting. Online payment arrives in phase 11.
- The academic-year to school link is checked in services, not by a database constraint.
