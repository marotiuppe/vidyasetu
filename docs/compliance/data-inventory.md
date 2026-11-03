# Data inventory

Status: draft, 2026-11-03. Table and column names are as in the models. Paths are relative to the repository root.

Subjects: students (minors), parents and guardians, staff (school owner, management, headmaster, teacher, accountant, clerk), platform admins (super admin).

Sensitivity is the working judgement of this draft: **Very high** = credentials or security material; **High** = identifies a child or an adult in a way that matters if leaked; **Medium** = personal or financial context with lower harm; **Low** = public or operational data.

## 1. Personal data stored today

| Category | Data (column names) | Where stored (table) | Purpose | Who can access (enforced in code) | Sensitivity |
|---|---|---|---|---|---|
| Student identity | admission_no, first_name, last_name, gender, date_of_birth, admission_date, status, address, previous_school | `students` (`backend/app/modules/students/models.py`) | Enrolment and school records | Staff in the student's branch (`scope_students`, `backend/app/core/tenant.py`); school owner sees the whole school; super admin all; linked parents see their own children; the student sees self | High |
| Enrolment | academic_year_id, class_id, section_id, roll_no | `enrollments` | Class placement per year | Same as student identity | Medium |
| Parent or guardian contact | full_name, relation, phone, email, is_primary, user_id | `guardians` | Contact and link to the parent login | Staff in scope; linked parents and the student see the child's profile (`backend/app/modules/students/service.py`) | High |
| Staff, parent and student accounts | username, email, full_name, phone, role, school_id, branch_id, is_active | `users` (`backend/app/modules/users/models.py`) | Sign-in and role | Super admin: all. School owner: own school. Management and headmaster: own branch, only roles they may create (`CREATABLE` in `backend/app/modules/users/service.py`). A user sees own record via `/auth/me` | High |
| Credentials | password_hash (argon2), must_change_password | `users` | Authentication | Not returned by any endpoint. Read only by the sign-in code (`backend/app/modules/auth/service.py`) | Very high |
| Account lockout state | failed_login_count, locked_until, token_version | `users` | Lockout and forced sign-out | Not returned by any endpoint | High |
| Two-factor secret and codes | mfa_enabled, mfa_secret_encrypted (Fernet), mfa_last_step; code_hash of each recovery code, used_at | `users`, `mfa_recovery_codes` (`backend/app/modules/auth/models.py`) | Second sign-in step | Not returned by any endpoint. Secret is encrypted with `SETTINGS_ENCRYPTION_KEY` (`backend/app/modules/settings/crypto.py`) | Very high |
| Sessions | user_id, family_id, jti, expires_at, revoked_at | `refresh_tokens` | Refresh-token rotation and revocation. The token itself is not stored, only its jti | Server only | Very high |
| Browser session | Access token (15 minutes) | Browser memory only (`frontend/src/app/core/auth/auth.service.ts`). Refresh token in an httpOnly cookie. `localStorage` holds only a "session started" flag with no token | Authenticating each request | The user's own browser | High |
| Policy acceptance | user_id, policy (privacy or terms), version, accepted_at, ip | `policy_acceptances` (`backend/app/modules/consent/models.py`) | Evidence that the user accepted the current policy | The user (own records); audited | High |
| Parental consent | student_id, purpose (data_processing, communication, photos, government_ids), status (granted, refused, withdrawn), given_by_user_id, recorded_by_user_id, method, note, recorded_at | `guardian_consents` | Evidence of parental consent for a student | Staff in scope record and view; shown on the student profile (`backend/app/modules/consent/service.py`); included in the student export | High |
| Data-rights requests | requester_user_id, student_id, type, message (free text), response_note, status, handled_by_user_id, due_on | `data_requests` (`backend/app/modules/datarights/models.py`) | Access, correction and erasure workflow | Requester (own requests); school owner, management and headmaster of the branch, super admin (`HANDLER_ROLES`) | High |
| Audit trail | at, school_id, branch_id, actor_user_id, actor_role, action, entity_type, entity_id, outcome, **ip**, request_id, detail | `audit_log` (`backend/app/modules/audit/models.py`) | Accountability and security investigation | Viewer: super admin (all), school owner (school), management and headmaster (branch) (`backend/app/modules/audit/service.py`). Users can see their own actions in `/me/export` | High |
| Personal preferences | key, value (language, notification choices, density) | `user_preferences` (`backend/app/modules/settings/models.py`) | Personal settings | Owner only | Low |
| Attendance | student_id, date, status, remark (up to 200 characters, free text) | `attendance_records`; staff attendance in `staff_attendance`; holidays in `holidays` | Attendance registers | Staff in scope; parents and students see their own (subject to the parent portal settings) | Medium |
| Notices | title, body (free text), target, expiry; read tracking with user_id and read_at | `notices`, `notice_reads` (`backend/app/modules/notices/models.py`) | Communication | Visibility by school, branch, class and section (`scope_notices`, `backend/app/core/tenant.py`) | Medium (body is free text and may hold personal data) |
| Fees and receipts | invoice_no, title, amounts (paise), discount_reason, cancel_reason; payment receipt_no, amount, method, reference, note, received_by, reversal fields | `invoices`, `invoice_lines`, `payments` (`backend/app/modules/fees/models.py`) | Fee collection, receipts, dues | Fee staff in branch (`scope_fees`); school owner the whole school; parents see their own children's fees; teachers, parents, students and super admin have no direct fee-table access | Medium-High (financial) |
| School details | name, code, board, contact fields, is_active | `schools` (`backend/app/modules/schools/models.py`) | Tenant record | School owner and super admin; name and branding are public | Low |
| School logo | content_type, data (PNG, metadata removed) | `school_logos` | Branding | Public read by design (`backend/app/modules/schools/router.py`) | Low |
| Settings | scope, key, value; secret values hold a Fernet token | `settings` (`backend/app/modules/settings/models.py`) | Configuration | Per setting: `edit_roles` and `view_roles` in `backend/app/modules/settings/registry.py`. Secret values are never returned by the API (`is_set` only) | High for secrets |
| Access log (operational) | client IP, method, path (query string removed), status, request id | Written to the process log by uvicorn (`backend/app/core/logging_setup.py` strips query strings) | Operations and security | Whoever can read the host's logs (platform operator) | Medium-High (IP addresses) |
| Error log (operational) | Exception type and request id only, never the message (`backend/app/core/middleware.py`) | Process log | Operations | Platform operator | Low |
| Exports and downloads | Student CSV, attendance CSV, dues CSV, audit CSV, personal JSON export, student JSON export, receipt PDF | Not stored on the server. Generated on request and downloaded | Portability and records | Roles listed in each module. Student JSON export: `STUDENT_EXPORT_ROLES` in `backend/app/modules/datarights/export.py` | High (the file leaves the system) |

## 2. Data that is not stored (checked)

- Plain-text passwords. Passwords are hashed with argon2 (`backend/app/core/security.py`). Generated starter passwords are returned once in the API response to the admin and are not stored in plain text.
- Plain-text refresh tokens. Only the jti is stored (`backend/app/modules/auth/service.py`).
- Card or bank details. No payment gateway exists yet (phase 11).
- Third-party analytics or tracking data. No analytics or advertising script is in the frontend (`frontend/src/app/features/legal/cookies-notice.html` says the same).
- Outbound messages (SMS, WhatsApp, email). No provider adapter exists yet (phase 11), so no message log exists.

## 3. Planned, not collected yet

These will change this inventory when built. Do not collect them before the matching phase is reviewed.

- PEN, APAAR ID and the optional Aadhaar-matching name, date of birth and gender check (phase 5.9). Sensitive: needs its own consent and masking.
- Admissions documents and applicant data (phase 5.9).
- Payment gateway references and webhooks (phase 11).
- SMS, WhatsApp and email delivery logs (phase 11).
- Exam marks and report cards (phase 6). Marks are personal data about a child.

## 4. Where the data lives and who runs it

- Application and database: the platform host (Render, per `render.yaml`). Region is configured by `HOSTING_REGION` and is shown on the privacy page. The owner has noted that Render cannot keep logs inside India (see control-matrix.md, gap list).
- Local development: SQLite file `backend/sms.db` (git-ignored). A developer machine can hold personal data if real records are loaded. Use test data only.
- Third-party processors that receive personal data today: the hosting provider only. The vendor list is part of phase 5.8 and is not written yet.

## 5. Gaps in this inventory

- The `detail` column of `audit_log` is meant to hold non-personal facts only. This is a rule followed in code review, not enforced by the database.
- Some reads and exports are not audited (see control-matrix.md and threat-model.md): attendance CSV export, dues CSV export, receipt PDF download and audit CSV export. The student CSV export, the student JSON export and the student profile view are audited.
- Staff reads of personal data in lists are not logged; only the full student profile view is.
