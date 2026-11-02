# Vidyasetu: School Management System

A responsive, installable (PWA) web application to run the daily work of a school: admissions, attendance, fees, exams and notices. It supports many schools, and each school can have many branches (for example a primary and a secondary section with their own timings and management).

- **Developer:** Maroti Uppe
- **Status:** Early development. Login, schools, branches, users, academic years, classes and sections are working.
- **Claude Code instructions:** see [CLAUDE.md](CLAUDE.md)
- **Per-school notes:** details about individual schools are kept in [docs/](docs/), not in this README.

## Goals

- Replace paper registers for admissions, attendance, fees, exams and notices.
- Give parents a simple phone-friendly view of attendance, fees, homework and notices.
- Work on any phone or PC browser and install to the home screen. No app store is needed.
- Run on free or low-cost hosting (Render) with minimal upkeep.

## Features

**MVP (first release)**
- Login with roles: super admin, management, headmaster, teacher, accountant, clerk, parent, student
- Multi-tenancy: add new schools and new branches without code changes
- Academic years, classes and sections
- Student and guardian records, admissions
- Daily attendance for students and staff
- Notices and circulars
- Fee structures, invoices, receipts and dues

**Next**
- Exams, marks entry and CBSE-style report cards (PDF)
- Timetable per branch and homework
- Staff records, leave and payroll
- Certificates (bonafide, transfer, leaving)
- Library, transport
- Parent and student portals, dashboards and reports

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL |
| Frontend | Angular (latest), standalone components, signals, PWA |
| Languages | English, Marathi |
| Hosting | Render (one web service plus one Postgres) |

One repository holds both `backend/` and `frontend/`. In production, FastAPI serves the built frontend, so a single Render service is enough.

## Optional integrations

Everything below is **optional**. Leave the variables empty and that feature stays off; the rest of the app keeps working.

- Online fee payment (Razorpay)
- SMS and WhatsApp alerts
- Email (SMTP)
- File storage (S3-compatible)

Configure them in `.env` (copy `.env.example`, which will be added with the backend). The variable list is in [CLAUDE.md](CLAUDE.md).

## Planned structure

```
SMS/
├─ backend/    FastAPI app, migrations
├─ frontend/   Angular PWA
├─ docs/       Per-school notes and other documentation
├─ render.yaml Render deployment blueprint
├─ .env.example
├─ CLAUDE.md
└─ README.md
```

## Getting started

Prerequisites: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you) and Node 20+. Local development uses SQLite, so no database server is needed.

```powershell
# 1. Config (optional locally; set the first platform admin to be able to log in)
copy .env.example .env      # then fill FIRST_SUPERADMIN_EMAIL / FIRST_SUPERADMIN_PASSWORD

# 2. Backend (http://localhost:8080, API docs at /api/docs)
cd backend
uv sync --python 3.12
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080

# 3. Frontend (http://localhost:4200, proxies /api to the backend)
cd frontend
npm install
npm start
```

Create a new school (platform admin only) with `POST /api/v1/schools`; this also creates the school's owner login. The owner then adds branches (`POST /api/v1/branches`) and users (`POST /api/v1/users`).

For production, `ng build` output is served by FastAPI, so one Render web service is enough. `render.yaml` describes it; it has **not been deployed or checked on Render yet**.

## Roadmap

The full phase-by-phase plan and current status are in [docs/roadmap.md](docs/roadmap.md). In short: foundation and admin console are done; students are in progress; then attendance, notices, fees, exams, timetable, staff, extras, dashboards, optional integrations, and a final hardening and release phase.

## Notes

- Student data belongs to minors. Access is role-based. One school never sees another school's data, and one branch never sees another branch's data.
- The design is inspired by common school-ERP features but is an original work.

## License

MIT. See [LICENSE](LICENSE).
