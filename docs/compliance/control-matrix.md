# Control matrix

Status: draft, 2026-11-03. Phase 5.8 in progress.

**How to read this.** Each row is one control. "Implemented" means the code in the file named in the evidence column does it. Anything not confirmed in code is marked **Partial**, **Planned** or **Unverified**. Nothing has been independently audited. Evidence paths are relative to the repository root.

**Frameworks.**

- OWASP ASVS (chapter numbers, v4 style) and OWASP Top 10 2021 (A01 to A10).
- Digital Personal Data Protection Act 2023 (DPDP). Section numbers are as recalled for this draft: check them against the Act and the Rules before relying on them.
- CERT-In Directions dated 28 April 2022: reporting within 6 hours, logs kept 180 days within India, clocks synchronised. Check the exact text.
- GIGW 3.0 and WCAG 2.1 AA (criteria named by number).

## 1. Authentication

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| A1 | Passwords hashed with argon2 | ASVS V2 (password storage), A02 | Implemented | `backend/app/core/security.py` | |
| A2 | Password policy: at least 10 characters (school may raise to 64), common-password list, sequences, username, email and name rejected | ASVS V2, A07 | Implemented | `backend/app/core/password_policy.py`, `backend/app/modules/settings/registry.py` | No breached-password list check (planned). |
| A3 | Generic sign-in error for every failure; timing equalised for unknown accounts | ASVS V2, A07; DPDP s.8(5) | Implemented | `backend/app/modules/auth/router.py` (`_invalid`), `backend/app/modules/auth/service.py`, `backend/app/core/security.py` (`DUMMY_HASH`) | |
| A4 | Per-account lockout, configurable per school within platform limits | ASVS V2, A07 | Implemented | `backend/app/modules/auth/service.py`, `backend/app/modules/settings/registry.py` | Lockout can be used against a user; admins unlock early. |
| A5 | Per-IP rate limits on sign-in, refresh, password change, two-factor, exports and other API paths | ASVS V2, A04 | Partial | `backend/app/core/rate_limit.py`, `backend/app/core/middleware.py` | In memory, per process. Client address is wrong behind a proxy unless `TRUST_PROXY_HEADERS` is set (see gap G4). |
| A6 | CAPTCHA or progressive delay on repeated sign-in failures | ASVS V2 | Planned | none | Not built. |
| A7 | Forced password change for admin-created and reset accounts | ASVS V2, A07 | Implemented | `backend/app/modules/users/service.py`, `backend/app/core/deps.py` (`password_change_required`) | Setting `security.force_password_change_new_accounts` (default on). |
| A8 | Student starter password from name and date of birth, always forced to change | ASVS V2; DPDP s.8(5) | Partial | `backend/app/modules/students/service.py` (`_student_login`) | Guessable by people who know the child. Random passwords are the roadmap's safer option (open decision). |
| A9 | Two-factor (TOTP) for super admin and school owner by default, optional for other roles, required by policy setting | ASVS V2 (MFA), A07 | Implemented | `backend/app/modules/auth/mfa.py`, `backend/app/modules/auth/mfa_router.py`, `backend/app/core/deps.py` (`mfa_setup_required`), `backend/app/modules/settings/registry.py` | Management, headmaster and accountant can be required by a school setting (off by default). Teachers and clerks have no required setting; they may still turn it on for themselves. |
| A10 | Two-factor secret encrypted; recovery codes hashed and single use; code replay refused | ASVS V2, A02 | Implemented | `backend/app/modules/auth/mfa.py`, `backend/app/modules/settings/crypto.py` | |
| A11 | Two-factor reset by school owner (own school) or super admin, with session revocation | ASVS V2 | Implemented | `backend/app/modules/users/service.py` (`reset_mfa`), `backend/app/modules/users/router.py` | |
| A12 | Sign-in events audited (success, failure, lockout, two-factor failure) | ASVS V7, A09 | Implemented | `backend/app/modules/auth/service.py` (`_audit_failure`), `backend/app/modules/auth/router.py` | |
| A13 | Sign-in alerts to the user, new device or location | ASVS V2 | Planned | none | |
| A14 | Forgot-password flow with single-use hashed reset links | ASVS V2 | Planned | `backend/app/modules/auth/router.py` (`_password_reset_enabled` returns false) | Needs an email or SMS adapter (phase 11). |

## 2. Sessions

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| S1 | Access token valid 15 minutes, held in browser memory only | ASVS V3, A07 | Implemented | `backend/app/core/config.py` (`access_token_minutes`), `frontend/src/app/core/auth/auth.service.ts` | |
| S2 | Refresh token in httpOnly cookie, `Secure` in production, `SameSite=Strict`, path `/api/v1/auth` | ASVS V3 | Implemented | `backend/app/modules/auth/router.py` (`_set_refresh_cookie`) | |
| S3 | Refresh-token rotation with reuse detection that revokes the whole family | ASVS V3 | Implemented | `backend/app/modules/auth/service.py` (`rotate_session`) | |
| S4 | Server-side session revocation on logout, password change, reset, deactivation and two-factor reset | ASVS V3 | Implemented | `backend/app/modules/auth/service.py` (`end_session`, `revoke_user_sessions`), `backend/app/modules/users/service.py` | |
| S5 | Every request re-checks the account is active, the token version matches, and the school is active | ASVS V3, A01 | Implemented | `backend/app/core/deps.py` (`get_current_user`) | |
| S6 | Session length: 12 hours default; "keep me signed in" only if the school allows, capped by platform limit | ASVS V3 | Implemented | `backend/app/core/config.py`, `backend/app/modules/settings/registry.py` (`security.remember_me_days`, `limits.remember_me_max_days`) | |
| S7 | Inactivity sign-out in the browser | ASVS V3 | Planned | none (no idle timer in `frontend/src`) | |
| S8 | Token types kept apart (access, refresh, two-factor) | ASVS V3 | Implemented | `backend/app/core/security.py` (`_decode`) | |
| S9 | CSRF protection: required header and allowed origin on cookie endpoints | ASVS V4 (CSRF), A01 | Implemented | `backend/app/core/deps.py` (`require_cookie_request`) | API uses bearer tokens, not cookies. |
| S10 | "Sign out other devices" for users | ASVS V3 | Unverified | Not located in the backend (`/auth/change-password` ends all sessions) | Frontend not checked for this draft. |

## 3. Access control and tenancy

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| T1 | Scope by school and branch derived from the token, not the client | ASVS V4, A01 | Implemented | `backend/app/core/tenant.py`, `backend/app/core/deps.py` | Application level only. |
| T2 | Row-level security in PostgreSQL as a second layer | ASVS V4, A01 | Planned | none | Phase 12. |
| T3 | Role checks on every endpoint | ASVS V4, A01 | Partial | `backend/app/core/deps.py` (`require_roles`), module routers | No full endpoint sweep yet. The phase 5.8 sweep is not recorded. |
| T4 | Cross-school and cross-branch checks | ASVS V4, A01 | Partial | `docs/roadmap.md` (phase 5.6 and 5.7 follow-ups: 43 checks by hand) | Not in the repository. No automated tests (by design, `CLAUDE.md`). |
| T5 | Parents see only linked children; students see only self | ASVS V4 | Implemented | `backend/app/core/tenant.py` (`scope_students`) | |
| T6 | Fee data limited to fee staff in scope; parents and students reach it only through their children | ASVS V4 | Implemented | `backend/app/core/tenant.py` (`scope_fees`) | |
| T7 | Roles a user may create are limited by the actor's role | ASVS V4 | Implemented | `backend/app/modules/users/service.py` (`CREATABLE`) | |
| T8 | Settings readable and editable only by the roles listed for each setting | ASVS V4 | Implemented | `backend/app/modules/settings/registry.py` (`edit_roles`, `view_roles`) | |
| T9 | Audit viewer limited by role and scope | ASVS V4, A01 | Implemented | `backend/app/modules/audit/service.py` (`_scoped`) | |
| T10 | Full student record export limited to owner, management, headmaster, parent and super admin | ASVS V4; DPDP s.11 | Implemented | `backend/app/modules/datarights/export.py` (`STUDENT_EXPORT_ROLES`) | |
| T11 | Personal data export for each user's own account | DPDP s.11 | Implemented | `backend/app/modules/datarights/export.py` (`me_export`) | Excludes password hash, tokens and two-factor secrets. |
| T12 | Direct object references return "not found" when out of scope | ASVS V4, A01 | Implemented | `backend/app/modules/students/service.py` (`_get_student`), `backend/app/modules/consent/service.py` (`_student`) | Pattern used in the modules reviewed. Full sweep pending (T3). |

## 4. Input handling and injection

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| I1 | Database queries use bound parameters (ORM) | ASVS V5, A03 | Partial | `backend/app/db/session.py`; module services use SQLAlchemy | No sweep for string-built SQL recorded. Unverified for every path. |
| I2 | Request bodies validated with typed schemas, with length limits | ASVS V5 | Partial | module `schemas.py` files; `backend/app/core/schema_types.py` | Not swept for every field. |
| I3 | Validation errors do not echo submitted values | ASVS V7; DPDP s.8(5) | Implemented | `backend/app/main.py` (`_validation_error`) | |
| I4 | CSV formula injection neutralised in exports | ASVS V5, A03 | Implemented | `_csv_cell` in `backend/app/modules/students/service.py`, `backend/app/modules/audit/service.py`, `backend/app/modules/attendance/service.py`, `backend/app/modules/fees/service.py` | |
| I5 | Request body size limit (12 MB default), enforced while streaming | ASVS V13, A04 | Implemented | `backend/app/core/middleware.py` (`BodySizeLimitMiddleware`) | |
| I6 | Filename in download headers sanitised | ASVS V5 | Implemented | `backend/app/modules/fees/router.py` (receipt file name) | |
| I7 | Search and filter input has length limits | ASVS V5 | Partial | e.g. `backend/app/modules/audit/router.py`, `backend/app/modules/users/router.py` (`q` max 100) | Not every endpoint checked. |

## 5. Cryptography and data protection

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| C1 | TLS in transit | ASVS V9, A02 | Partial | Host terminates TLS (`render.yaml`). HSTS in production (`backend/app/core/middleware.py`) | No HTTP-to-HTTPS redirect in code (G9). |
| C2 | Security headers: HSTS (production), `nosniff`, frame deny, referrer policy, permissions policy, cross-origin opener policy | ASVS V14, A05 | Implemented | `backend/app/core/middleware.py` (`SecurityHeadersMiddleware`) | |
| C3 | Strict content security policy | ASVS V14, A03 | Implemented | `backend/app/core/middleware.py` (`CSP`), `frontend/angular.json` (`inlineCritical: false`) | `style-src 'unsafe-inline'` accepted. Browser console check not recorded. |
| C4 | Integration secrets encrypted at rest; never returned by the API; refused without a key in production | ASVS V6, A02 | Implemented | `backend/app/modules/settings/crypto.py`, `backend/app/modules/settings/schemas.py` | |
| C5 | Encryption key rotation procedure | ASVS V6 | Planned | none | |
| C6 | Database encryption at rest | ASVS V6, A02 | Unverified | Depends on the hosting provider | |
| C7 | Secrets kept out of git (`.env` ignored, `*.db` ignored) | ASVS V14, A02 | Implemented | `.gitignore`, `.env.example` | `.env.example` documents each variable. |
| C8 | Random values from a secure generator (tokens, recovery codes) | ASVS V6 | Implemented | `backend/app/modules/auth/service.py` (`secrets.token_urlsafe`), `backend/app/modules/auth/mfa.py` (`secrets.choice`) | |

## 6. Logging, errors and monitoring

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| L1 | Generic 500 responses with request id; no stack trace to the client | ASVS V7, A05 | Implemented | `backend/app/core/middleware.py` (`ErrorBoundaryMiddleware`) | |
| L2 | Query strings removed from access logs | ASVS V7; DPDP s.8(5) | Implemented | `backend/app/core/logging_setup.py` | |
| L3 | Error logs carry exception type and request id only | ASVS V7 | Implemented | `backend/app/core/middleware.py`, `backend/app/modules/audit/service.py` | |
| L4 | Audit trail of security events and personal data changes | ASVS V7, A09 | Partial | `backend/app/modules/audit/service.py` and calls in each module | Not every read is audited (L8). |
| L5 | Audit rows immutable (UPDATE and DELETE blocked) | ASVS V7, A09 | Partial | `backend/alembic/versions/0012_consent_audit_mfa.py` | PostgreSQL only. TRUNCATE not blocked. Table owner can drop the trigger. |
| L6 | Audit `detail` free of personal values | ASVS V7; DPDP s.8(5) | Partial | Convention in `backend/app/modules/audit/service.py` docstring | Enforced by review only, not by the database. |
| L7 | Audit viewer and export available to the right roles | ASVS V7 | Implemented | `backend/app/modules/audit/router.py` | |
| L8 | Audit covers reads of personal data | ASVS V7, A09; DPDP s.8(5) | Partial | Audited: full student profile, student CSV, student JSON. Not audited: attendance CSV, dues CSV, receipt PDF, audit CSV, list views | See gap G3. |
| L9 | Alerting on suspicious events | ASVS V7, A09 | Planned | none | |
| L10 | Log retention for 180 days, kept within India | CERT-In (logs) | Planned | `docs/compliance/retention-schedule.md` | Owner has noted Render cannot keep logs in India (gap G1). |
| L11 | Clocks synchronised to an approved time source | CERT-In | Unverified | Host setting not in repository | |

## 7. Secure configuration and deployment

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| D1 | Production start-up guards: strong `SECRET_KEY`, no `*` for origins or hosts | ASVS V14, A05 | Implemented | `backend/app/core/config.py` (`_production_guards`) | |
| D2 | `TRUSTED_HOSTS` set in production | ASVS V14, A05 | Partial | `backend/app/main.py`; **not set in `render.yaml`** | Service refuses to start until set (G2). |
| D3 | Trusted proxy setting set correctly for the host | ASVS V14 | Partial | `backend/app/core/rate_limit.py` (`client_ip`); **not set in `render.yaml`** | See gap G4. |
| D4 | API documentation off in production | ASVS V14, A05 | Implemented | `backend/app/main.py` | |
| D5 | CORS limited to configured origins | ASVS V14, A05 | Implemented | `backend/app/main.py`, `backend/app/core/config.py` | |
| D6 | API responses not cached by browsers or proxies | ASVS V8 | Implemented | `backend/app/core/middleware.py` (`Cache-Control: no-store`) | |
| D7 | Service worker does not cache personal data | ASVS V8 | Implemented | `frontend/ngsw-config.json` | |
| D8 | Migrations run before the app starts | ASVS V14 | Implemented | `render.yaml` start command | |
| D9 | Dependencies pinned by lockfile | ASVS V14, A06 | Implemented | `backend/uv.lock`, `frontend/package-lock.json` | |
| D10 | Dependency vulnerability scan (`pip-audit`, `npm audit`) | ASVS V14, A06 | Unverified | Roadmap says done in phase 5.3. No script, CI or report in repository | Re-run and keep the output outside the repo. |
| D11 | Continuous integration with lint and type checks | ASVS V14 | Unverified | No CI configuration in repository | Lint and type checks are run by hand (`CLAUDE.md`). |
| D12 | Database backups and a tested restore | A04, DPDP s.8(5), CERT-In | Planned | `docs/roadmap.md` (phase 5.8 drill, phase 12 automation) | No procedure in repository. |
| D13 | Hosting plan checked for backups and retention | A04 | Unverified | `render.yaml` (`plan: free` for the database) | |
| D14 | First super admin created from start-up variables, only when no users exist | ASVS V2 | Partial | `backend/app/main.py` (`_seed_super_admin`), `render.yaml` (`sync: false`) | Creation is implemented. Removing the variables afterwards is an operator instruction in `.env.example` and `render.yaml`, not enforced by code. |
| D15 | Platform-level settings changes audited | ASVS V7 | Implemented | `backend/app/modules/settings/service.py` (`settings.changed`) | |

## 8. Data protection and consent (DPDP Act 2023)

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| P1 | Privacy policy and terms published as pages | DPDP s.5 (notice); GIGW | Implemented | `frontend/src/app/app.routes.ts` (`privacy`, `terms`, `children`, `cookies`, `accessibility`, `grievance`, `security`), `backend/app/modules/public/service.py` | Text needs legal review. |
| P2 | Privacy policy and terms acceptance recorded per user, with version | DPDP s.5, s.6 | Implemented | `backend/app/modules/consent/service.py` (`accept_policy`), `backend/app/modules/consent/models.py` | |
| P3 | Use blocked until the current policy is accepted | DPDP s.5 | Implemented | `backend/app/core/deps.py` (`POLICY_ACCEPTANCE_EXEMPT`, `_policies_accepted`) | |
| P4 | New policy version requires new acceptance | DPDP s.5 | Implemented | `backend/app/modules/settings/registry.py` (`legal.privacy_version`, `legal.terms_version`) | |
| P5 | Parental consent recorded per student and purpose, with withdrawal | DPDP s.9 | Partial | `backend/app/modules/consent/models.py`, `backend/app/modules/consent/service.py` | Recorded and shown. Not enforced as a gate on any processing yet. |
| P6 | Verifiable parental consent | DPDP s.9 | Partial | Online consent is given through the parent's login. Paper and in-person consent are recorded by staff | Not identity-verified. Method to be decided with legal review. |
| P7 | No tracking or targeted advertising of children | DPDP s.9 | Implemented | No analytics or advertising script in `frontend/src` (see `frontend/src/app/features/legal/cookies-notice.html`); no outbound calls in `backend/app` | Re-check whenever a dependency or integration is added. |
| P8 | Access request handled (own data export, student record export, workflow) | DPDP s.11 | Implemented | `backend/app/modules/datarights/service.py`, `backend/app/modules/datarights/export.py` | |
| P9 | Correction and erasure requests handled as a workflow | DPDP s.12 | Partial | `backend/app/modules/datarights/service.py` | Erasure is not carried out by the app (G5). |
| P10 | Grievance route and response time | DPDP s.13; IT Act and SPDI Rules | Partial | `frontend/src/app/features/legal/grievances.ts`, `legal.grievance_response_days` (`backend/app/modules/settings/registry.py`), due date on `data_requests` | Response time tracked by due date, not reminders. |
| P11 | Retention limits applied automatically | DPDP s.8(7) | Planned | `docs/compliance/retention-schedule.md` | Only refresh tokens are purged (P12). |
| P12 | Expired refresh tokens removed | DPDP s.8(7) | Implemented | `backend/app/modules/auth/service.py` (`_purge_old_tokens`, 30 days) | |
| P13 | Data minimisation: only fields needed for school records are collected | DPDP s.6 (purpose limitation) | Partial | `backend/app/modules/students/models.py` | Government ID fields are not collected yet. Planned fields need consent (phase 5.9). |
| P14 | Breach notice route and contacts configured | DPDP s.8(6) | Partial | Contacts in settings (`backend/app/modules/settings/registry.py`), `/.well-known/security.txt` (`backend/app/modules/public/router.py`) | Procedure in `incident-response.md`. Not tested. |
| P15 | Security contact published | GIGW; RFC 9116 | Implemented | `backend/app/modules/public/service.py` (`security_txt`) | Returns 404 until a contact is set. |
| P16 | Data location declared | DPDP s.16 (transfers); CERT-In | Partial | `legal.hosting_region` setting | Declared by the operator. Not verified against the host. |

## 9. Incident response and reporting

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| R1 | Written incident response procedure | CERT-In; DPDP s.8(6) | Implemented (draft) | `docs/compliance/incident-response.md` | Draft, legal review needed. |
| R2 | Tabletop exercise held | CERT-In; DPDP s.8(5) | Planned | none | Before first real student record. |
| R3 | Report to CERT-In within 6 hours | CERT-In Directions | Planned | Procedure in `incident-response.md` | Channel and contact to be confirmed. |
| R4 | Intimation to the Data Protection Board and affected people | DPDP s.8(6) | Planned | Procedure in `incident-response.md` | Depends on the Rules. Check the form and timing. |
| R5 | Containment tools in the app: lock account, lock school, reset password, reset two-factor, revoke sessions | ASVS V7; DPDP s.8(5) | Implemented | `backend/app/modules/users/router.py`, `backend/app/modules/schools/service.py`, `backend/app/core/deps.py` | No single kill switch (G8). |
| R6 | Evidence export for investigations | ASVS V7 | Implemented | `backend/app/modules/audit/router.py` (`/audit/export.csv`, 10,000 rows) | Export itself not audited (G3). |

## 10. Accessibility and government web (GIGW 3.0, WCAG 2.1 AA)

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| G-A1 | Accessibility statement published | GIGW 3.0 | Implemented | `frontend/src/app/features/legal/accessibility-statement.html` | Statement must match what has been tested. |
| G-A2 | Labels and ARIA on controls | WCAG 1.3.1, 4.1.2 | Partial | About 135 ARIA attributes in `frontend/src/app/features` | Not audited with a screen reader. |
| G-A3 | Text alternatives for images and logos | WCAG 1.1.1 | Partial | `frontend/src/app/features` (not checked line by line for this draft) | Not audited. |
| G-A4 | Colour contrast | WCAG 1.4.3 | Partial | Roadmap says contrast fixed in the verification pass | No measured report. |
| G-A5 | Keyboard operation and focus | WCAG 2.1.1, 2.4.7 | Unverified | None recorded | Browser check not recorded for this draft. |
| G-A6 | Automated accessibility scan (axe) | WCAG 2.1 AA | Planned | none | Required before go-live. |
| G-A7 | Reflow at 320 px width and zoom | WCAG 1.4.10, 1.4.4 | Unverified | Design rules in `CLAUDE.md` (16 px gutter, no horizontal scroll) | Not measured. |
| G-A8 | Language declared; Marathi and English strings | WCAG 3.1.1; GIGW | Partial | `frontend/src/app/core/i18n` | Marathi text written by an agent; native review pending (roadmap). |
| G-A9 | Error messages identify the field and the problem | WCAG 3.3.1, 3.3.3 | Partial | Field errors from the API (`backend/app/main.py`) | Not all screens checked. |

## 11. Assurance and governance

| # | Control | Reference | Status | Evidence | Note |
|---|---|---|---|---|---|
| X1 | Automated tests (unit, integration, end to end) | ASVS V14 | Planned | None in repository (by design, `CLAUDE.md` rule 7) | Phase 12. |
| X2 | Independent security audit or penetration test | ASVS; CERT-In empanelled audit (where needed) | Planned | None | Phase 12, before go-live. This draft does not replace it. |
| X3 | Schema changes through migrations | ASVS V14 | Implemented | `backend/alembic/versions/` (migrations 0001 to 0012) | |
| X4 | Commits recorded in git history | ASVS V7 | Implemented | `git log` | |
| X5 | Vendor list with security and location details | DPDP s.8 (processors) | Planned | None | Phase 5.8 deliverable, not yet written. |
| X6 | Policy owner and review date for these documents | ISO-style governance | Planned | None | Assign before go-live. |
| X7 | Staff training on data protection | DPDP s.8(5) | Planned | None | |

## 12. Known gaps (must be closed or accepted before real student data is entered)

| Gap | Description | Where it applies | Owner decision |
|---|---|---|---|
| G1 | **Render cannot keep logs inside India.** CERT-In log retention in India is not met while logs stay on Render. (Owner's note in the roadmap.) | L10, hosting | Choose a log store in India or accept the risk in writing. |
| G2 | **`TRUSTED_HOSTS` is not set in `render.yaml`.** The production start-up guard refuses `*`, so the service will not start until it is set. | D2 | Set the host name in Render before the first deploy. |
| G3 | **Some reads and exports are not audited**: attendance CSV, fee dues CSV, receipt PDF, audit CSV export, list views. | L8 | Add audit calls, or accept the risk. |
| G4 | **`TRUST_PROXY_HEADERS` is not set in `render.yaml`.** With the default `false`, the app sees the proxy's address for every request, so per-IP rate limits are shared by all users and audit IP addresses are wrong. | A5, D3 | Confirm Render's proxy behaviour, then set `true`. |
| G5 | **No automatic data deletion.** Erasure requests are a workflow only. Nothing is deleted on a schedule (`data.retention_days` has no effect). | P9, P11 | Approve the retention schedule and build the jobs. |
| G6 | **PostgreSQL row-level security not done** (phase 12). Tenant isolation is application-level only. | T2 | Phase 12. |
| G7 | **TRUNCATE is not blocked on the append-only tables** (`audit_log`, `guardian_consents`). The table owner can also drop the trigger. | L5 | Revoke TRUNCATE and restrict the owner role on PostgreSQL. |
| G8 | **No kill switch, no alerting, no on-call** in the repository. | R5, L9 | Operator to define. |
| G9 | **No HTTP-to-HTTPS redirect in code**; relies on the host. | C1 | Confirm on Render. |
| G10 | **Rate-limit and lockout counters are per process.** Limits do not hold across several instances. | A5 | Move counters to shared storage if the service is scaled. |
| G11 | **Backup procedure drafted (`backup-restore.md`); restore drill not yet run** (phase 5.8 drill, phase 12 automation). | D12 | Build and test before real data. |
| G12 | **No formal tests and no independent audit** (phase 12). | X1, X2 | Phase 12. |
| G13 | **Dependency audit and CI not recorded in the repository.** | D10, D11 | Add a documented, repeatable check. |
| G14 | **Student starter password is guessable** (name and date of birth pattern). | A8 | Owner decision: random passwords (roadmap). |
| G15 | **Parental consent is recorded but not enforced**, and the verification method is not decided. | P5, P6 | Legal review and phase 5.9 design. |
| G16 | **Access log and audit rows hold IP addresses.** Retention not set. | Retention schedule | Set a period once G1 is decided. |
| G17 | **Marathi text needs native review; legal text needs legal review.** | G-A8, P1 | Owner and lawyer. |
| G18 | **Accessibility not measured** with axe, a screen reader or keyboard tests. | G-A2 to G-A7 | Run checks before go-live. |
| G19 | **No inactivity sign-out and no breached-password check.** | S7, A2 | Planned. |
| G20 | **Forgot-password and sign-in alerts not built.** | A13, A14 | Phase 11. |

## 13. Changes to this matrix

When a row changes status, update the evidence path, the date at the top of the file and the matching gap. A row may move to Implemented only when the code path is named.
