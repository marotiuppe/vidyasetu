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
| 5.2 | Security hardening | Security headers and strict CSP, rate limiting and account lockout, stronger password policy, forced password change for admin-created accounts, refresh-token rotation with server-side revocation (also fixes "sessions not revoked on password change"), CSRF/origin checks, safe error and log handling, trusted hosts, HTTPS and body-size limits, dependency audit | Not started | | |
| 5.3 | Legal pages | Public Privacy Policy, Terms of Use, Children's privacy notice, Cookie and storage notice, Accessibility statement, Grievance page, Security and responsible-disclosure page; operator and grievance-officer details configurable; links in footers | Not started | | |
| 5.4 | Consent, audit log, data rights and MFA | Parental consent and policy-acceptance records, audit log with viewer, data access/correction/erasure requests, student data export, TOTP two-factor sign-in for privileged roles | Not started | | |
| 5.5 | Compliance pack and security review | `docs/compliance` (data protection and security policy, incident response, retention schedule, data inventory, control matrix against OWASP / DPDP / CERT-In / GIGW), threat model, authorization sweep, penetration-style checks, fixes | Not started | | |
| 6 | Exams and report cards | Terms, subjects, marks entry, grading (CBSE default, configurable), report card PDF, academic progress | Not started | | |
| 7 | Timetable and homework | Per-branch timings and periods, timetable, homework | Not started | | |
| 8 | Staff | Staff records, leave, payroll | Not started | | |
| 9 | Extras | Certificates (bonafide, transfer, leaving), library, transport | Not started | | |
| 10 | Dashboards and portals | Real dashboard numbers, parent and student portal views, reports | Not started | | |
| 11 | Optional integrations | Razorpay payments, SMS and WhatsApp alerts, email, file storage (all off unless `.env` keys are set) | Not started | | |
| 12 | Release | PostgreSQL row-level security and PostgreSQL re-check of all modules (payment locking), formal tests, performance, Render deployment and backups, independent security audit before go-live | Not started | | |

(1) Phase 0 began on the evening of 2026-11-01; the exact start time was not recorded. The first recorded build of the app is 2026-11-01 22:02. Finished = time of the first commit. For phases 1 and 2, *Started* is the time of the first commit or agent launch of that phase.

## Plan for phases 5.2 to 5.5 (security and compliance; planned 2026-11-02, not started)

Requested by the owner so the application can pass government and security audits. Nothing in these phases has been built yet.

**What can and cannot be promised.** The software can implement the controls auditors check and ship the documents they ask for. It cannot promise "unhackable" or certify a government audit: that needs an independent assessor (for example a CERT-In empanelled auditor) and the policy texts need legal review before they are relied on.

**Roles for the policies.** The school is the data fiduciary (controller) for its students, parents and staff; the platform operator provides the software and acts as data processor.

**Laws and guidelines to review with a lawyer:** Digital Personal Data Protection Act 2023 and its Rules (check the commencement dates; children's data needs verifiable parental consent and no tracking or targeted advertising), Information Technology Act 2000 and the SPDI Rules 2011 (privacy policy, grievance officer, reasonable security practices), CERT-In Directions 2022 (incident reporting within 6 hours, 180-day log retention in India), GIGW 3.0 and WCAG 2.1 AA (government website policies and accessibility).

**Information needed from the owner before go-live** (all configurable, nothing hard-coded): operator legal name and address, grievance officer name, email and phone, security contact email, privacy contact email, and the hosting region. Note: Render cannot keep logs inside India, which is a CERT-In gap to decide on.

**Design decisions already made**
- Phase 5.2 (security, backend plus matching frontend): strict CSP with `script-src 'self'` and `style-src 'self' 'unsafe-inline'` (Angular injects component styles at runtime) and `inlineCritical: false` in the production build so no inline handlers remain; HSTS and the other headers; `Cache-Control: no-store` on the API; in-memory rate limiter (per process, fine for one Render instance); lockout after 5 failures for 15 minutes with identical generic errors (no user enumeration); password policy of at least 10 characters with a common-password blocklist; `must_change_password` for admin-created accounts and resets; refresh-token rotation with reuse detection and a `token_version` that invalidates access tokens; `X-Requested-With` and Origin checks on cookie endpoints; SameSite=Strict cookie; generic 500 responses, validation errors that never echo submitted values, request IDs, no personal data in logs; trusted hosts, HTTPS redirect, request size limits; production start-up guards (strong secret, no wildcard origins); `pip-audit` and `npm audit`; `/.well-known/security.txt` and a public `/api/v1/public/legal` config endpoint. Migration `0008`.
- Phase 5.3 (legal pages, frontend): public pages `/privacy`, `/terms`, `/children`, `/cookies`, `/accessibility`, `/grievance`, `/security` that describe only controls that really exist, with footer links on the landing page, login page and sidebar, and `robots.txt`.
- Phase 5.4: migration `0009` (policy acceptance and parental consent records, append-only audit log with a viewer, data-rights requests, TOTP two-factor sign-in for super admin and school owner via `pyotp`), student data export, access logging for sensitive reads.
- Phase 5.5: `docs/compliance` written after the controls exist so the control matrix is truthful (implemented, partial, planned), plus threat model, incident response and breach-notification procedure, retention schedule, data inventory, vendor list, an authorization sweep over every endpoint, penetration-style checks and fixes.
- 5.2 and 5.3 can run in parallel (backend and frontend agents); 5.4 follows because it needs its own migration.

## Dependencies

- Students (2) come before attendance, fees and exams.
- Phases 5.2 to 5.5 can run at any point after the modules they protect; they should finish before real student data is entered.
- Integrations (11) plug into attendance, fees and notices once those exist.

## Known gaps to close later

- Sessions are not revoked on password change or reset (fixed in phase 5.2).
- The overview page shows only counts that exist today; student, attendance and marks cards arrive with their modules.
- Search in the top bar is a disabled placeholder.
- Fees: the receipt PDF uses Helvetica and writes "Rs." (no rupee sign, no Devanagari names) until a Unicode font is bundled; there is no standalone payments list screen yet (the API exists); the currency is a single constant in the frontend (`core/ui/money.ts`) and could become a school setting; payment concurrency (`SELECT ... FOR UPDATE`) is only tested on SQLite, so recheck on PostgreSQL (phase 12). Online payment arrives in phase 11.
- The academic-year to school link is checked in services, not by a database constraint.
