# Incident response and breach notification

Status: draft, 2026-11-03. Not yet tested by a tabletop exercise. Legal review needed before reliance. Timelines marked "check" must be confirmed against the current official text, because the rules are new or changing.

## 1. Scope

This procedure covers:

- a **security incident**: any event that threatens the confidentiality, integrity or availability of the platform, its data or its accounts;
- a **personal data breach**: an incident that leads to accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to, personal data.

Both apply to the platform (code, hosting, database) and to any school's data inside it. Every school is a separate data fiduciary, so the school is told about any incident affecting its data.

## 2. Roles

Contact details are **not** written in this document. They are read from the application's settings at the time of the incident. Use the Settings page, or the public endpoint `GET /api/v1/public/legal` (with the school code for school-level values). The security contact is also published in `/.well-known/security.txt`.

| Role | Who | Where the contact is stored | Responsibilities |
|---|---|---|---|
| Incident lead (platform) | The platform operator's security contact | Settings, platform level: "Security contact email" (`legal.security_contact_email`) and "Operator name, email and phone" (`legal.operator_*`) | Runs the response, keeps the timeline, decides containment, leads notices to the school and to CERT-In |
| Platform admin on duty | A user with the `super_admin` role (with two-factor on) | Named by the operator. Not stored in the app | Executes containment in the app (deactivation, resets, lock) and collects evidence |
| School data contact | The school owner, for each affected school | Settings, school level: "Privacy contact email" (`legal.privacy_contact_email`) | Tells staff and decides what the school tells parents |
| Grievance officer | Named by the school | Settings, school level: "Grievance officer name, email, phone" (`legal.grievance_officer_*`) | Receives complaints from data principals about the incident. Keeps a record of complaints |
| Hosting provider | Render support | Not in the app. Operator's account | Platform and log access, restores, provider incidents |
| Legal adviser | Named by the operator and the school | Not in the app | Decides on notices and wording, and on what must be reported and when |

Placeholders to fill in before use (outside the repository, in the operator's incident file):

- `[INCIDENT LEAD NAME AND CONTACT]`
- `[PLATFORM ON-CALL CONTACT, OUT OF HOURS]`
- `[HOSTING SUPPORT CONTACT]`
- `[LEGAL ADVISER CONTACT]`
- `[CERT-In REPORTING CHANNEL, CONFIRMED ON THE CERT-IN WEBSITE]`

Gap: the settings have no separate incident hotline or out-of-hours number. The security contact is the only route for reporting. Add a setting if the operator needs one.

## 3. Severity levels

| Level | Meaning | Examples | Start |
|---|---|---|---|
| S1 Critical | Confirmed or likely exposure, change or loss of personal data of many people, or full control of a privileged account, or the platform is down because of an attack | Super admin account taken over; a database dump in public; ransomware on the host; data of several schools exposed | Immediately. Incident lead and legal adviser within 1 hour (proposal) |
| S2 High | Confirmed unauthorised access to one school's or branch's data, or a compromised account with data access, or suspected tampering with fee records | A school owner's password phished; one branch's student list read by an outsider; an invoice changed without a record | Within 4 hours (proposal) |
| S3 Medium | An attempt that was blocked, or a contained exposure with no evidence of data being read | Brute-force attempts locking several accounts; rate-limit floods; a page showing another user's name for a short time, fixed quickly | Same working day |
| S4 Low | Suspicious activity with no evidence of harm, or a security finding with no data exposure | A failed-sign-in spike from one address; a vulnerability report that needs no change to data | Next working day |

Clock: CERT-In requires reporting of notifiable cyber incidents **within 6 hours of noticing them** (CERT-In Directions, 28 April 2022). The clock starts when the operator notices, not when the investigation ends. Check the list of reportable incident types in the Directions themselves.

## 4. Steps

Work through the steps in order. Several can run at once. Record every action with a time (IST) in the incident file.

### 4.1 Detect

Sources in the code:

- `audit_log` rows: `auth.login_failed`, `auth.locked`, `mfa.verify_failed`, `mfa.disabled`, `mfa.reset`, `user.password_reset`, `user.unlocked`, `student.viewed`, `student.exported`, `user.exported`, `school.logo_uploaded`, `settings.changed`. Viewable by super admin (all), school owner (own school), and management or headmaster (own branch) through `/api/v1/audit`.
- Process logs: access log with client address, method, path and status (query strings removed by `backend/app/core/logging_setup.py`); error log with exception type and request id only (`backend/app/core/middleware.py`). Each response carries `X-Request-ID`.
- HTTP 429 responses from the rate limiter (`backend/app/core/middleware.py`).
- Hosting provider alerts and status pages.

Limits: the audit log records only what the code records. Several reads are not audited (see section 6). Nothing alerts automatically: there is no monitoring or paging in the repository.

### 4.2 Contain

Use the fastest effective step. Each step is in the app unless marked otherwise.

- Lock one account: deactivate it (`is_active` false). This ends its sessions at once, because every request checks the account and token version (`backend/app/core/deps.py`).
- Stop one school: deactivate the school. Its users fail the active-school check on every request (`backend/app/core/deps.py`).
- Force sign-out of one user: reset their password (also revokes their sessions), or reset their two-factor (`POST /users/{id}/mfa/reset`, school owner and super admin).
- Unlock an account after a brute-force attack: an admin can unlock early (`POST /users/{id}/unlock`).
- Stop a feature: switch the module off for the school (`feature.*` settings, super admin), or disable an integration.
- Stop all sessions everywhere: change `SECRET_KEY` on the host. This invalidates every access token and refresh token, because both are signed with it. Every user signs in again. Plan for it, because it is disruptive.
- Stop the service: **no kill switch exists in the app.** The operator stops or suspends the service on the host. The platform maintenance message setting only shows text. It does not block use.
- Rotate `SETTINGS_ENCRYPTION_KEY` only with a plan. Changing it makes stored integration secrets unreadable. They must be entered again.

### 4.3 Preserve evidence

- Before changing data, take a database snapshot (provider snapshot or a manual dump, by the operator).
- Export the audit log in date ranges (`/api/v1/audit/export.csv`, at most 10,000 rows per export). Store exports with access restricted to the incident team.
- Keep process logs and the hosting provider's logs. Note their retention period.
- Do not edit or delete audit rows. On PostgreSQL the trigger blocks it. Do not drop the trigger either. Record every action taken on the platform in the incident file.

### 4.4 Assess

Answer these in writing:

1. What happened, when it started, when it was found, and when it stopped.
2. Which systems, which schools and which branches were involved (use `school_id` and `branch_id` in the audit rows).
3. What personal data was involved. Were children's records involved? Were credentials, ID numbers or fee records involved?
4. Was the data read, changed, deleted or copied? Use the audit rows, the database snapshot and logs. Note what cannot be shown.
5. How many data principals are affected, and how to contact each one.
6. Is it a personal data breach under the Digital Personal Data Protection Act 2023? Is it a reportable incident under the CERT-In Directions? Ask the legal adviser to confirm both.
7. What is the likely harm to the people affected?

### 4.5 Notify

Each notice below is made by the person named. Use the wording agreed with the legal adviser. Do not put personal data in subject lines, public posts or chat groups.

**CERT-In.** Report within 6 hours of noticing a reportable incident, using the reporting channel on the CERT-In website (check the current channel). Keep the report, the reference number and the time it was sent. Owner: the incident lead, for the operator and the school together.

**Data Protection Board of India and affected people (DPDP Act 2023, section 8(6)).** The fiduciary must give intimation of a personal data breach to the Board and to each affected data principal, in the form and manner the Rules prescribe. Check the current Rules for the form and the timelines. For a child, the notice goes to the child's parent or guardian. Owner: the school as data fiduciary, with the operator's help as processor.

**The school (data fiduciary).** The operator tells the school owner and the school's privacy contact as soon as it is confirmed. The contract with each school should set the time (proposal: within 24 hours of confirmation). Owner: the incident lead.

**Affected parents, students and staff.** Explain in plain language: what happened, what data, what it could mean for them, what they should do, and who to contact (the grievance officer). Owner: the school, with the wording approved by the legal adviser.

**Police and other authorities.** The school or the operator decides, on the legal adviser's advice.

**Record of notices.** Keep a log of each notice: who, to whom, when, the channel and the reference. The app has no feature for this; keep it in the incident file.

### 4.6 Recover

- Restore from a backup only after the cause is closed. A restore procedure and a restore drill are planned (phase 5.8) and are not yet in the repository. Until the drill is done, recovery time is unknown.
- Reset credentials that may have been exposed. Use forced password change (`must_change_password`) for the affected accounts.
- Re-enable accounts and schools only after checks. Keep the containment record.
- Check the audit log for further unexpected activity for at least a set period after recovery (proposal: 30 days).

### 4.7 Post-incident review

Hold a review within 10 working days of closing the incident (proposal). Write it down and keep it with the incident file. Cover:

- a timeline in IST, with the time each step above was done;
- the root cause, and which control failed or was missing (refer to control-matrix.md rows);
- whether CERT-In and the Board were told in time, and any gap in the notices;
- what the audit log showed, and what it did not show;
- actions with an owner and a date, and whether each one changes the code, the settings, the documents or the training;
- an update to the control matrix and the threat model, and a roadmap entry where a fix is needed.

## 5. Communication rules

- Use the names of roles, not of individuals, in public text.
- Never confirm a suspicion as fact before the assessment says so.
- Do not publish technical detail that would help a repeat attack until the fix is in place.
- Keep one channel of truth: the incident file.

## 6. Known gaps in this procedure

- No automatic alerting, paging or on-call rota in the repository.
- No kill switch in the app.
- No incident register in the app.
- Some reads are not audited, so a data exposure through them would not show in the audit log: the attendance CSV export, the fee dues CSV export, the receipt PDF download, the audit CSV export and the student list views (only the full student profile is logged). See threat-model.md.
- The restore drill is not done, so recovery is unproven.
- Render cannot keep logs inside India (owner's note). CERT-In log retention in India is not solved (see control-matrix.md).
- Tabletop exercise not yet held. Hold one before the first real student record is entered, then at least once a year (proposal).
