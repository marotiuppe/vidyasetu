# Compliance documents (drafts)

Working drafts for data protection and security, written from the code as it stands on 2026-11-03 (phase 5.8 in progress). Paths in these documents are relative to the repository root.

## Index

| Document | What it covers |
|---|---|
| [data-inventory.md](data-inventory.md) | Personal data types, where each is stored, why, who can reach it, and how sensitive it is |
| [retention-schedule.md](retention-schedule.md) | Proposed retention per record type, what the code does today, and the deletion gaps |
| [incident-response.md](incident-response.md) | Roles, severity levels, response steps, reporting clocks, contacts read from settings, and the post-incident review |
| [threat-model.md](threat-model.md) | STRIDE analysis per component, with the mitigation in code or a gap |
| [control-matrix.md](control-matrix.md) | Controls mapped to OWASP ASVS and Top 10, DPDP Act 2023, CERT-In Directions 2022 and GIGW 3.0 / WCAG 2.1 AA, with status and evidence, plus the known gaps |

## Status words

- **Implemented**: the control exists in code and the file shown is the evidence.
- **Partial**: the control exists but does not cover everything it should.
- **Planned**: the control is on the roadmap and is not in code.
- **Unverified**: the control may exist, but nothing in the repository confirms it. It is not claimed.
- **Not applicable**: the control does not apply to the current code.

## Important disclaimer

- These documents are **drafts**. They need **legal review** before anyone relies on them, and the policy texts need review by a lawyer who knows the Digital Personal Data Protection Act 2023, the Information Technology Act 2000 and the SPDI Rules 2011, CERT-In Directions 2022, and GIGW 3.0.
- They **do not constitute certification**. No CERT-In empanelled audit, independent penetration test or DPDP compliance assessment has been done. Phase 12 includes an independent security audit before go-live.
- Roles: the **school is the data fiduciary** (controller) for its students, parents and staff. The **platform operator** provides the software and acts as the **data processor**. Where a document says "the school decides", it means the school's own decision, made with its own advisers.
- No school is named anywhere in these documents. Contact details and legal names come from the application's settings, not from these files.
- Statements about the code were checked against the repository on the date above. They must be re-checked when the code changes.
