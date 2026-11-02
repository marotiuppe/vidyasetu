# Rani-Laxmibai-High-School: School Management System

A responsive, installable (PWA) web application to run the daily work of **Rani-Laxmibai-High-School**, Yeshwant Nagar, Nanded, Maharashtra.

- **Developer:** Maroti Uppe
- **Status:** Planning. Repository setup and project instructions are in place; no application code yet.
- **Claude Code instructions:** see [CLAUDE.md](CLAUDE.md)

## About the school

| | |
|---|---|
| Name | Rani-Laxmibai-High-School (Rani Laxmibai H.S.) |
| Location | Yeshwant Nagar / Ganesh Nagar, Nanded, Maharashtra, 431602 / 431605 |
| Map | https://www.mappls.com/y5abcv (about 19.1712 N, 77.2968 E) |
| Established | 1987 (per public listing) |
| Management | Private aided (per public listing) |
| Classes | 1st to 10th, split into two branches (below) |
| Medium | Marathi (per public listing); the app supports English and Marathi |
| Board | CBSE rules are the app default. Public listings say State Board, so **confirm with the school**. |
| Academic year | Starts in April |
| UDISE code | 27151703405 |
| Library | About 630 books (per listing) |

Sources used (public, user-generated, may be outdated; verify with the school):
[schools.org.in](https://schools.org.in/nanded/27151703405/rani-laxmibai-h-s-yeshwant-nagar.html),
[Mappls](https://www.mappls.com/y5abcv),
[JustDial](https://www.justdial.com/Nanded/Rani-Laxmibai-High-School-Ganesh-Nager-Yeshwantnagar-Nanded/9999P2462-2462-161117224624-R1E2_BZDET) and
[Facebook group](https://www.facebook.com/groups/1124408375654979/).
JustDial and Facebook could not be read automatically, so their details still need to be added by hand.

### Two branches

The school runs two branches with **separate timings and separate management**. The system keeps their data apart. Timings and management will be entered later through the app.

| Branch | Classes | Timings | Management |
|---|---|---|---|
| Primary | 1 to 5 | *to be filled* | *to be filled* |
| Secondary | 6 to 10 | *to be filled* | *to be filled* |

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

1. [x] Project instructions (`CLAUDE.md`) and README
2. [ ] Confirm school details later: board, branch timings, management, fee heads, grading scheme
3. [x] Scaffold backend (FastAPI) and frontend (Angular), add `.env.example` and `render.yaml`
4. [ ] Auth, roles, multi-tenancy. Done: login/refresh/logout, schools, branches, users, Angular login and route guards, PWA (installable), academic years, classes and sections with a School setup page. Left: audit log, PostgreSQL row-level security, custom app icons (the PWA icons are Angular's defaults).
5. [ ] Students and attendance
6. [ ] Fees and notices
7. [ ] Deploy MVP to Render and pilot with one class
8. [ ] Exams, report cards, timetable and remaining modules

## Notes

- Student data belongs to minors. Access is role-based. One school never sees another school's data, and one branch never sees another branch's data.
- The design is inspired by common school-ERP features but is an original work.

## License

To be decided by the owner.
