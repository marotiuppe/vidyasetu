# Retention schedule

**Status: PROPOSAL. Needs school and legal approval before it is relied on.**

The periods below are suggestions for the school (the data fiduciary) and its advisers to confirm or change. They are not legal advice, and no period here is taken from a statute unless it says so.

## What the code does today

- **No automatic deletion or anonymisation job exists.** Nothing removes personal data on a schedule.
- The only automatic removal: refresh-token rows are purged 30 days after they expire or are revoked (`_purge_old_tokens` in `backend/app/modules/auth/service.py`, run at each new sign-in).
- The setting `data.retention_days` is registered in `backend/app/modules/settings/registry.py`, but no code reads it. It has **no effect**.
- **Erasure requests are a workflow only.** A data request with type `erasure` is recorded, assigned and closed with a note (`backend/app/modules/datarights/service.py`). Nothing is deleted when it is closed. The school must delete or restrict the data by hand, outside the app.
- The app has **no delete endpoint for students or user accounts**. Students leave the roll by changing their status. Users are deactivated, not deleted.
- Rows that can be deleted through the app: guardians (`DELETE /students/guardians/{id}`), holidays, notices (with their read records), school logos, and settings values (reset to default). Personal-data deletion through these paths is manual and is not logged as an erasure.
- The audit log is append-only on PostgreSQL (trigger in `backend/alembic/versions/0012_consent_audit_mfa.py`). It cannot be purged through the app, which conflicts with erasure (see the audit row below).

## Proposed retention

| Record type | Where | Proposed retention (proposal) | Trigger | What happens today | Notes for approval |
|---|---|---|---|---|---|
| Student profile and enrolment | `students`, `enrollments` | Keep while enrolled. After leaving, keep the admission and transfer record for the period the school sets. Schools commonly keep admission registers for a long time. | Status changes to left, transferred or passed out | Kept indefinitely. No deletion path | School and board rules decide the period. Confirm with legal counsel. |
| Guardian contact details | `guardians` | Keep while linked to an enrolled student. After the student leaves, remove phone and email after a short period (proposal: 1 year), keeping the name and relation if the admission record needs them. | Student leaves | Kept. Staff can delete a guardian row by hand | Parents may still need to be reached for records. Balance with the admission record. |
| Staff, parent and student accounts | `users` | Deactivate on exit (done by a manager). Proposal: after 1 year inactive, remove personal fields and keep an anonymised row so foreign keys still work. | Account deactivated | Deactivation revokes sessions. No anonymisation | Foreign keys from audit rows, fees and attendance make deletion complex. Anonymise, do not delete. |
| Credentials and two-factor secrets | `users` (`password_hash`, `mfa_secret_encrypted`), `mfa_recovery_codes` | Delete when the account is removed or anonymised. Recovery codes are deleted when regenerated or when two-factor is switched off | Account change | Recovery codes are deleted on regenerate and disable (`backend/app/modules/auth/mfa.py`). Password and secret are replaced on reset, not deleted | Must follow the account rule above. |
| Refresh tokens | `refresh_tokens` | 30 days after expiry or revocation | Expiry or revocation | **Implemented**: purged at each new sign-in | Keep as is. |
| Audit log | `audit_log` | Proposal: at least 180 days for security events (see the CERT-In row in control-matrix.md, which must be confirmed), and a longer period for accountability records set by the school. Pseudonymise actor and IP fields after the period rather than delete the row | Age of row | Kept indefinitely. Append-only on PostgreSQL. **No purge exists** | The append-only trigger blocks UPDATE and DELETE, so pseudonymising needs a planned, privileged procedure. TRUNCATE is not blocked (known gap). |
| Parental consent and policy acceptance | `guardian_consents`, `policy_acceptances` | Keep for as long as the student record is kept, plus the period the school needs to show consent was given. Withdrawal is a new row, not a delete | Student record ends | Kept. Append-only trigger on `guardian_consents` (PostgreSQL) | Consent evidence may be needed after the record is closed. |
| Data-rights requests | `data_requests` | Keep closed requests for 3 years as proof of how the request was handled. Proposal only | Request closed | Kept. No purge | The request row names the student. Keep the response note short. |
| Attendance | `attendance_records`, `staff_attendance`, `holidays` | Current academic year plus a proposed 3 years, then aggregate counts only | Academic year ends | Kept indefinitely | Attendance history is often needed for later queries from parents. |
| Fees: invoices, lines, payments, receipts | `invoices`, `invoice_lines`, `payments` | Keep for the period that accounting and tax rules require. The accountant confirms the period | Financial year ends | Kept. Payments are reversed, never deleted (`reversed_reason`, `reversed_at`) | Confirm with the school's chartered accountant. |
| Notices | `notices`, `notice_reads` | Hide after expiry. Proposal: delete the notice and its read records 12 months after expiry | Expiry date | Expired notices are hidden from parents and students but not deleted. Owners and managers can delete a notice by hand (deletes its read records) | Notices may contain personal data in free text. Remind staff not to put personal data in notice bodies. |
| Personal preferences | `user_preferences` | Delete with the account | Account removed | Kept | Low risk. |
| Settings values | `settings` | Remove integration keys when the owner clears them or disables the integration | Owner action | Clearing a secret resets it to default and removes the stored token (settings `DELETE` endpoint) | Secrets are encrypted. Losing `SETTINGS_ENCRYPTION_KEY` makes them unreadable. |
| School logo | `school_logos` | Remove on request or when the school is closed | Owner action or school closure | Removable by the school owner and super admin (`DELETE /schools/{id}/logo`) | None. |
| Operational access logs (IP addresses, paths) | Host logs (Render) | Proposal: 180 days, if CERT-In log rules apply as the owner has noted. Stored in India if that is required | Age of log | Retention is set by the hosting provider, not the app | Render cannot keep logs in India (owner's note; see control-matrix.md). Decide before real data is entered. |
| Operational error logs | Host logs | Same as access logs | Age of log | Error messages contain no personal data by design | None. |
| Database backups | Hosting provider backups | Backups must follow the same rules. Proposal: a fixed backup window (for example 30 days), stated in the privacy policy. A deleted record may remain in backups until the window ends | Backup age | **No backup or restore procedure is in the repository.** The restore drill is planned in phase 5.8 | Confirm the hosting plan's backup features (the database in `render.yaml` uses the `free` plan). |
| Exports and downloads | Downloaded CSV, JSON and PDF files | Not stored on the server. The school's staff must delete copies they make | User action | Not controlled by the app | Add guidance for staff who download exports. |
| Development data | `backend/sms.db` on developer machines | Do not load real personal data. Delete development databases that contain real data | Developer action | `*.db` is git-ignored | Policy rule only. |

## Erasure and correction requests (manual steps)

The app records the request. The school does the rest by hand:

1. Check the request is from the data principal (the student, or the parent for a child) and note how identity was checked.
2. Check for a legal reason to keep the data (accounting, admission registers, a court order or an investigation). Record it in the response note.
3. Delete or restrict the rows listed above by hand, or anonymise them. Do not edit audit rows (they are append-only on PostgreSQL).
4. Write a short response note and close the request (the app requires a note before closing).
5. Tell the requester the outcome and the date.

Gaps: nothing in the app checks that step 3 was done. There is no tool that erases a student across all tables, and deleting from `audit_log` is not possible while the append-only trigger is in place.

## Review

- Review this schedule before the first real student is entered, and then each academic year.
- Each period above becomes a setting (or a job) only after it is approved. Until then the app keeps everything.
