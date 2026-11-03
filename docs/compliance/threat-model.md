# Threat model (STRIDE)

Status: draft, 2026-11-03. Based on the code in the repository. Paths are relative to the repository root. "Gap" means no mitigation in code today. "Partial" means some mitigation exists but a known hole remains. This is not a penetration test and has not been reviewed by an independent assessor.

STRIDE key: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege.

## Scope and trust boundaries

- **Browser and PWA** (Angular app, service worker) is outside the trust boundary. Anything it sends is untrusted.
- **API** (FastAPI under `/api/v1`) is the enforcement point for all access rules. Frontend checks are for usability only.
- **Database** (PostgreSQL in production, SQLite in development) holds all tenant data.
- **Host** (Render web service and managed Postgres) runs the code and stores logs.
- **Optional integrations** (payments, SMS, WhatsApp, email, storage) are configured in settings. No outbound adapter is built yet (phase 11).
- Users: parents, students, staff and platform admins. Attackers considered: outsiders (phishing, brute force, scraping), a malicious or careless user inside one school, a user of one school trying to reach another, and a compromised developer or host account.

## 1. Browser and PWA

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| S | Phishing page copies the sign-in form and steals passwords | Partial. Two-factor is required for super admins and school owners by default, and optional for other staff roles (`backend/app/modules/settings/registry.py`). No phishing-resistant method (passkeys). No warning to users about new sign-ins. |
| T | Cross-site scripting injects script that reads data | Implemented. Strict CSP: `script-src 'self'`, `default-src 'self'`, `frame-ancestors 'none'` (`backend/app/core/middleware.py`). No inline scripts in the production build (`frontend/angular.json`, `inlineCritical: false`). Partial: `style-src 'unsafe-inline'` is allowed because Angular injects component styles. |
| T | Malicious script in a legal or notice page | Partial. Notice bodies are plain text rendered by Angular (escaped by default). Not checked in a browser run. |
| R | A user denies having made a change | Partial. Audit rows carry actor, role, IP and request id (`backend/app/modules/audit/service.py`). Not every read is logged (see section 2 and the audit gaps). |
| I | Tokens are stolen from browser storage | Implemented. Access token kept in memory only (`frontend/src/app/core/auth/auth.service.ts`). Refresh token in an httpOnly cookie with `SameSite=Strict`, `Secure` in production, limited to `/api/v1/auth` (`backend/app/modules/auth/router.py`). `localStorage` holds a flag with no token. |
| I | Personal data is cached offline by the service worker | Implemented. The service worker caches the app shell and static assets only. No API data group (`frontend/ngsw-config.json`). `Cache-Control: no-store` on API responses (`backend/app/core/middleware.py`). |
| I | Data left on a shared computer | Partial. "Keep me signed in" is off by default. Without it the cookie ends with the browser session and the server session is short (12 hours default, `backend/app/core/config.py`). No automatic sign-out on inactivity (gap). |
| I | Third-party scripts leak data to a tracker | Implemented. No analytics, advertising or external script in the frontend (`frontend/src/app/features/legal/cookies-notice.html`). Fonts are self-hosted. |
| D | The page is flooded or the browser crashes | Not specifically mitigated. API rate limits apply (section 2). |
| E | A user reaches screens for another role by editing the URL | Partial. Route guards (`frontend/src/app/core/auth`) are for usability. The API enforces access (section 2). |
| E | The page is framed to trick clicks (clickjacking) | Implemented. `X-Frame-Options: DENY` and `frame-ancestors 'none'` (`backend/app/core/middleware.py`). |
| I/T | Traffic is intercepted in transit | Partial. HSTS is sent in production (`backend/app/core/middleware.py`). TLS is terminated by the host. No HTTP-to-HTTPS redirect in code (gap, relies on the host). |

## 2. API (FastAPI)

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| S | Forged access token | Implemented. Tokens signed with HS256 and `SECRET_KEY`. Token type is checked, so a refresh or two-factor token cannot be used as an access token (`backend/app/core/security.py`). Production refuses a weak or default key (`backend/app/core/config.py`, `_production_guards`). |
| S | Forged or replayed request to a cookie endpoint (CSRF) | Implemented. Login, refresh and logout require `X-Requested-With` and an allowed `Origin` (`backend/app/core/deps.py`, `require_cookie_request`). The API itself uses bearer tokens, not cookies. |
| T | Mass assignment (client sets fields it should not) | Partial. Request bodies are Pydantic schemas per module. No full sweep of every schema recorded (phase 5.8 deliverable). |
| T | Client sets `school_id` or `branch_id` to reach another tenant | Partial. Scope is derived from the token in `backend/app/core/tenant.py` and module services. Cross-school and cross-branch checks were run by hand against the API (recorded in `docs/roadmap.md`). No automated test suite in repo by design (`CLAUDE.md`). |
| R | Action without a trace | Partial. Audit rows for writes, sign-ins, exports and settings (`backend/app/modules/audit/service.py`). See section 9 for unaudited reads. |
| I | Stack traces or SQL errors reach the client | Implemented. Unhandled errors return a generic 500 with a request id, and only the exception type is logged (`backend/app/core/middleware.py`). Validation errors do not echo submitted values (`backend/app/main.py`). |
| I | API documentation exposes the surface | Implemented. OpenAPI and docs are disabled in production (`backend/app/main.py`). |
| I | Enumeration of accounts by sign-in | Implemented. Same error for wrong password, unknown account, locked account and inactive account. Password check is run on unknown accounts too (`backend/app/core/security.py`, `DUMMY_HASH`; `backend/app/modules/auth/service.py`). |
| I | Enumeration through password reset | Not applicable yet. Forgot-password is not built (`backend/app/modules/auth/router.py`, `_password_reset_enabled` returns false). |
| I | Cross-origin reads from another site | Implemented. CORS allows only configured origins, and `*` is refused in production (`backend/app/main.py`, `backend/app/core/config.py`). |
| I | Host header attacks | Implemented in code, depends on configuration. `TrustedHostMiddleware` (`backend/app/main.py`). Production refuses `*`. **`render.yaml` does not set `TRUSTED_HOSTS`**, so the production start-up guard refuses to start the service until it is added. |
| D | Brute force of passwords | Implemented. Lockout per account after the school's number of failures, default 3, lock 60 minutes, school range 3 to 10 attempts and 5 to 1440 minutes (`backend/app/modules/auth/service.py`, `backend/app/modules/settings/registry.py`). Sign-in rate limit 30 per minute per IP (`backend/app/core/rate_limit.py`). |
| D | Lockout used to deny a user access (targeted lockout) | Partial. A failed attempt can lock any account. Admins can unlock early (`POST /users/{id}/unlock`). No notification to the user. |
| D | Flooding of any endpoint | Partial. Per-IP limits on login, refresh, password change, two-factor, exports and all other API paths (`backend/app/core/rate_limit.py`, `backend/app/core/middleware.py`). Counters are in memory and per process, so limits do not hold across several instances (known gap). Behind a proxy, the client address is wrong unless `TRUST_PROXY_HEADERS` is set (see section 10). |
| D | Oversized request bodies | Implemented. 12 MB default, enforced while streaming, so a missing or false `Content-Length` does not bypass it (`backend/app/core/middleware.py`, `BodySizeLimitMiddleware`). |
| E | A user calls a manager endpoint | Implemented for the endpoints that use `require_roles` or `_writers` and similar guards (`backend/app/core/deps.py`). Full endpoint sweep not yet recorded (gap, phase 5.8). |
| E | A manager creates a super admin or an outside role | Implemented. Creatable roles per actor (`CREATABLE`, `backend/app/modules/users/service.py`). |
| E | A school owner changes platform-level settings | Implemented. Each setting has `edit_roles` (`backend/app/modules/settings/registry.py`). |
| E | Teacher, clerk or accountant takes a full student record out | Implemented. JSON export is limited to `STUDENT_EXPORT_ROLES` (`backend/app/modules/datarights/export.py`). |
| E | Mass export of student records by a staff user | Partial. The single-student JSON export (`/students/{id}/export`) and the personal JSON export (`/me/export`) are limited to 5 per minute per IP (`backend/app/core/rate_limit.py`). The student CSV list export uses the general API limit (300 per minute). Student exports are audited (`student.exported`). No cap on rows per CSV export for staff. |

## 3. Database

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| S | Database credentials leak | Partial. Credentials are in the host's environment (`DATABASE_URL`). Stored in the host, not in git (`.gitignore` excludes `.env`). Rotation procedure not written. |
| T | SQL injection | Partial. The code uses SQLAlchemy queries with bound parameters. The only raw SQL found is the SQLite transaction setup and index predicates (`backend/app/db/session.py`, model `Index` definitions). No full sweep for raw SQL concatenation recorded. |
| T | Direct edit of audit rows | Partial. Trigger blocks UPDATE and DELETE on `audit_log` on PostgreSQL only (`backend/alembic/versions/0012_consent_audit_mfa.py`). TRUNCATE is not blocked. The table owner can drop the trigger. Whether the app's database role is the table owner is not verified. |
| T | Direct edit of consent rows | Partial. Trigger blocks UPDATE on `guardian_consents` (PostgreSQL only). DELETE is not blocked. |
| R | Audit rows are lost | Partial. Audit rows are written in the same transaction as the change they record, so a rollback removes both. Audit write failure is logged by type only and does not stop the action (`backend/app/modules/audit/service.py`). |
| I | Tenant data read by a user of another school | Partial. Application-level filtering only (`backend/app/core/tenant.py`). Row-level security is planned for phase 12 and is **not** in code. |
| I | Secrets read from the database | Implemented for integration secrets: Fernet encryption, key from `SETTINGS_ENCRYPTION_KEY`, refused in production if the key is empty (`backend/app/modules/settings/crypto.py`). Password hashes are argon2 (`backend/app/core/security.py`). MFA secrets are encrypted (`backend/app/modules/auth/mfa.py`). |
| I | Database at rest or in backups is read by the provider's staff | Unverified. Depends on the host's encryption and access controls. |
| I | Backups restored into the wrong place | Gap. No backup or restore procedure in the repository. The restore drill is planned (phase 5.8). |
| D | Database unavailable | Gap. No failover or backup plan in code. The free database plan in `render.yaml` should be checked for backups and availability. |
| D | Long transactions block other writers | Implemented for SQLite (`BEGIN IMMEDIATE`) and for payments (`SELECT ... FOR UPDATE`, roadmap). |
| E | A tenant query misses its scope filter | Partial. Scope helpers are used throughout. A missing filter would expose data. Row-level security (phase 12) would be the second layer. |

## 4. Authentication and sessions

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| S | Guessed or stuffed passwords | Implemented. Argon2 hashing (`backend/app/core/security.py`). Password policy: at least 10 characters (a school may raise it to 64), common-password list, no simple sequences, no username, email or name inside the password (`backend/app/core/password_policy.py`). Lockout as in section 2. No check against a published breached-password list (gap). No CAPTCHA (gap). |
| S | Stolen password of a privileged user | Partial. Two-factor (TOTP) for super admin and school owner by default. Recovery codes are hashed and single use (`backend/app/modules/auth/mfa.py`). Replay of a used code is refused (`mfa_last_step`). |
| S | Two-factor device lost | Implemented. Reset by a school owner (own school) or super admin (`POST /users/{id}/mfa/reset`), which ends sessions. |
| S | Guessable starter password for a student's login | Partial. A starter password is built from the student's name and date of birth when the policy allows, otherwise a random one (`backend/app/modules/students/service.py`). It is guessable by anyone who knows the child. Mitigation: it is always forced to change at first sign-in. Roadmap records a decision to move to random passwords. |
| S | Admin-created or reset password is used by the admin | Implemented. Forced password change for admin-created and reset accounts (`backend/app/modules/users/service.py`, `must_change_password`). Enforced by `backend/app/core/deps.py`. |
| S | Token replay after logout | Implemented. Logout revokes the whole refresh-token family. Access tokens are checked against `token_version` on every request (`backend/app/core/deps.py`). A short access-token life of 15 minutes limits the window. |
| T | Refresh token copied and reused | Implemented. Rotation with reuse detection. A used token revokes its whole family (`backend/app/modules/auth/service.py`, `rotate_session`). |
| T | Forged refresh token | Implemented. Signed, checked against the stored jti (`backend/app/modules/auth/service.py`). |
| R | User denies signing in | Implemented. Sign-in success and failure are audited (`auth.login_ok`, `auth.login_failed`), with IP and request id. |
| I | Sign-in response reveals account existence | Implemented (see section 2). |
| I | Two-factor secret read from the database | Implemented. Encrypted (`backend/app/modules/auth/mfa.py`, `backend/app/modules/settings/crypto.py`). |
| D | Session not ended after password change, reset, deactivation or two-factor reset | Implemented. Each path calls `revoke_user_sessions` (`backend/app/modules/auth/service.py`). |
| E | Policy not accepted but data used | Implemented. Until the current privacy policy and terms are accepted, only a short list of endpoints is open (`POLICY_ACCEPTANCE_EXEMPT`, `backend/app/core/deps.py`). |
| E | Account of a deactivated school keeps working | Implemented. Each request checks the school is active (`backend/app/core/deps.py`). |

## 5. File uploads (school logo)

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| T | Malicious file (script in an image, polyglot) | Implemented. Only PNG, JPEG and WebP are accepted (`backend/app/modules/schools/service.py`, `ALLOWED_TYPES`). SVG is refused. The image is decoded and re-encoded as PNG with metadata removed (`normalise_logo`). Only the first frame is used. |
| D | Decompression bomb or very large image | Implemented. 1 MB upload cap read while streaming (`read_capped_body`). Maximum 4000 px per side. Decompression-bomb warnings are treated as errors. |
| D | Large or slow upload | Implemented. Cap enforced while streaming, so a false `Content-Length` does not bypass it. Global body limit also applies (`backend/app/core/middleware.py`). |
| I | Logo served with the wrong type | Implemented. Stored content type; `ETag` and `Cache-Control: public, max-age=300` (`backend/app/modules/schools/router.py`). |
| I | Private data exposed through the public logo URL | Not applicable. A logo is public by design. |
| E | Non-owner changes the logo | Implemented. Only super admin and school owner, and only for their school (`_logo_target`, `can_manage_logo`). |
| - | Virus scanning | Not implemented. Accepted for now because files are re-encoded before storage. Revisit when document uploads (phase 5.9) arrive. |

## 6. PDF generation (receipts)

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| T | Text in a receipt is interpreted as markup | Low risk. Receipts are drawn with ReportLab text drawing, not HTML (`backend/app/modules/fees/receipt.py`). |
| T | Font file swapped | Partial. Fonts are bundled files read from the repository (`backend/app/modules/fees/receipt.py`). Dependency and file integrity not checked at start-up. |
| I | Receipt of another family or branch downloaded | Implemented for the scope rules. `receipt_data` is scoped (`backend/app/modules/fees/service.py`). Parents see their children's receipts. Partial: the receipt download is not audited (see section 9). |
| I | Receipt file name leaks or injects headers | Implemented. The receipt number is reduced to letters, digits, underscore and dash before use in the header (`backend/app/modules/fees/router.py`). |
| D | Very slow PDF generation | Partial. Input length is bounded by settings (receipt footer 150 characters). No timeout or queue. |

## 7. CSV import and export

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| T | Spreadsheet formula injection in an export (CSV injection) | Implemented in the student, audit, attendance and fee exports. A cell starting with `=`, `+`, `-`, `@`, tab or carriage return gets a leading apostrophe (`_csv_cell` in `backend/app/modules/students/service.py`, `backend/app/modules/audit/service.py`, `backend/app/modules/attendance/service.py`, `backend/app/modules/fees/service.py`). |
| T | Bad data imported | Partial. Student import is a JSON body (`import_students`, `backend/app/modules/students/service.py`) covered by the body size limit. Its row-level validation was not reviewed for this draft. Not recorded for the other import paths (none exist yet). |
| I | Export leaves the system | Partial. Student CSV and student JSON exports are audited. Attendance CSV, dues CSV, receipt PDF and the audit CSV export are not (section 9). Exports are not stored on the server. |
| E | Staff bulk-export of students | Partial. Student CSV export is audited (`student.exported`, scope list). Its rate limit is the general API limit (section 2). |

## 8. Optional integrations (payments, SMS, WhatsApp, email, storage)

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| I | Integration keys leak | Implemented. Stored encrypted with Fernet. Write-only in the API: a saved secret is shown as set, never its value (`backend/app/modules/settings/crypto.py`, `backend/app/modules/settings/schemas.py`). Refused in production when no encryption key is set (`crypto.py`). |
| I | Integration keys leak through logs | Implemented by rule: the audit `detail` never holds setting values (`backend/app/modules/audit/service.py` docstring). The rule is enforced by review only. |
| I | Key lost, all saved secrets unreadable | Partial. `crypto.decrypt` returns None for a value it cannot read, so the saved secret is lost and must be entered again (`backend/app/modules/settings/crypto.py`). No key rotation tool. |
| S/T | Fake webhook from a payment provider (phase 11) | Not applicable yet. No webhook endpoint exists. Planned: signature check and idempotency before any payment is recorded. |
| I/E | Server-side request forgery through an integration URL | Not applicable yet. No outbound HTTP client exists in the backend (checked). Planned review before phase 11. |
| - | Vendor risk (each provider's own security and location) | Gap. Vendor list not written (phase 5.8 deliverable). |
| I | Personal data sent to a provider without consent | Not applicable yet. No provider is connected. Consent rules apply when one is added (phase 5.7 and 11). |

## 9. Logs, audit and monitoring

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| I | Personal data in access logs (query strings with names or phone numbers) | Implemented. Query strings are replaced before the line is written (`backend/app/core/logging_setup.py`). |
| I | Personal data in error logs | Implemented. Only the exception type and request id are logged (`backend/app/core/middleware.py`, `backend/app/modules/audit/service.py`). |
| I | IP addresses kept in logs and audit rows | Accepted as personal data. Retention rules are in `retention-schedule.md`. Not yet decided for CERT-In. |
| R | Audit missing for some reads and exports | Gap. Not audited: attendance CSV export (`backend/app/modules/attendance/service.py`, `export_csv`), fee dues CSV export (`dues_csv`, `backend/app/modules/fees/service.py`), receipt PDF download (`receipt_data`), audit CSV export (`backend/app/modules/audit/service.py`, `export_csv`), student list views and staff user list views. Audited: the full student profile view, the student CSV export and the student JSON export. |
| R | Audit rows altered | Partial. Append-only trigger on PostgreSQL only (section 3). |
| R | Logs altered on the host | Gap. Host-side logs are controlled by the provider. Not recorded as tamper-evident. |
| D | Silent failure of logging | Partial. Audit write failure is logged by exception type and the action, and the action continues. The operator is not alerted. |
| - | Monitoring and alerting | Gap. None in the repository. |
| - | Log retention for 180 days in India | Gap. Owner has noted Render cannot keep logs in India. Decision pending (phase 5.8). |

## 10. Hosting and deployment (Render, `render.yaml`)

| STRIDE | Threat | Mitigation (evidence) or gap |
|---|---|---|
| S/I | Client address is the proxy's, not the user's | **Gap, check before deploy.** `TRUST_PROXY_HEADERS` is not set in `render.yaml`, so it defaults to false. The app then sees the proxy's address for every request. Per-IP rate limits would then be shared by all users, and audit IP addresses would be wrong. Set it to `true` on Render only after confirming the proxy behaviour. |
| D/S | Service fails to start, or starts unsafely | **Gap, check before deploy.** `TRUSTED_HOSTS` is not set in `render.yaml`. The default is `["*"]`, which the production guard refuses, so the service does not start until it is set (`backend/app/core/config.py`). |
| I | Secrets in source | Implemented. `.env` is git-ignored (`.gitignore`). `SECRET_KEY` is generated by Render (`render.yaml`). `FIRST_SUPERADMIN_*` are set by hand (`sync: false`). |
| I | Settings encryption key not set | Partial. `SETTINGS_ENCRYPTION_KEY` is not in `render.yaml`. Secrets cannot be saved in production until it is set (fail closed, `crypto.py`). Two-factor setup also needs it. |
| D | Database plan has no backups or short life | Unverified. `render.yaml` uses `plan: free` for the database. Check the plan's backup and retention terms. |
| T | Dependencies changed or vulnerable | Partial. Lockfiles are present (`backend/uv.lock`, `frontend/package-lock.json`). The roadmap records a dependency audit in phase 5.3, but no script, CI or report is in the repository. Unverified. |
| T | Migration runs before the app is ready | Implemented. Start command runs `alembic upgrade head` before `uvicorn`. |
| - | Single instance state | Partial. Rate-limit counters are in memory per process (`backend/app/core/rate_limit.py`). Fine for one instance. |

## 11. Known weak points, in priority order

1. Host configuration gaps in `render.yaml`: `TRUSTED_HOSTS` (service will not start), `TRUST_PROXY_HEADERS` (wrong client address), `SETTINGS_ENCRYPTION_KEY` (secrets and two-factor unavailable). Fix before the first deploy.
2. No row-level security. Tenant isolation rests on application filters (phase 12).
3. Some reads are not audited (section 9).
4. No automatic sign-out on inactivity, no breached-password check, no CAPTCHA, no sign-in alerts.
5. Rate-limit counters and lockout counters are per process.
6. Audit trigger covers UPDATE and DELETE only, on PostgreSQL only. TRUNCATE is not blocked, and the table owner can drop the trigger.
7. No backup, restore procedure or restore drill yet.
8. No monitoring or alerting. No independent penetration test.
