# CLAUDE.md — Vidyasetu School Management System

Instructions for Claude Code when working in this repository. Read `README.md` for the full project description.

## Project in one paragraph

A web-based School Management System (installable, responsive PWA). Developer/owner: **Maroti Uppe**. The system is **multi-tenant**: it supports many schools, and each school has many branches (for example a primary and a secondary branch, each with its own timings and management).

**Keep the code and docs generic.** Never hard-code a school's name, location, timings, board or management in code, UI text, README or this file. Those are data entered through the app. Details about the first school using the system are in `docs/school-profile.md`; read it when you need school context (class ranges, board, branches, open questions).

**Isolation rule (non-negotiable):** one school never sees another school's data, and one branch never sees another branch's data. Only users explicitly given a school-wide role (e.g. school owner) can see all branches of their own school, and only a platform `super_admin` spans schools.

Feature scope is inspired by school ERPs like schoollog.in, but everything here must be **original** (code, copy, logos, design). Never copy another product's code, text or assets.

## Hard rules

1. **One repository only**: `backend/` and `frontend/` live together in this repo. No second repo.
2. **No unwanted files.** Do not create scratch files, notes, test dumps, screenshots, or generated reports inside the project. Only add files the app needs.
3. **Replica-pack output goes OUTSIDE the project.** When using `replica-recon`, `replica-architect`, `replica-design`, etc., write their artifacts to `C:\Users\91986\AppData\Local\Temp\claude\e--Own-Projects-SMS\...\scratchpad` (or another folder outside `E:\Own-Projects\SMS`). Only distilled decisions go into `README.md` or code.
4. **Third-party services are optional and `.env`-driven.** Payment gateway, SMS, WhatsApp, email, object storage, etc. must each be behind an adapter interface that is enabled only if its env vars are set. With no keys, the app must still run fully (features degrade gracefully, e.g. "payment link disabled", SMS skipped and logged).
5. **Never commit secrets.** Keep `.env` git-ignored; maintain `.env.example` with every variable documented.
6. **Student data is sensitive** (minors). Enforce role-based access on every endpoint, scope every query by school and branch (derived from the authenticated user's token, never from client-supplied ids), never log personal data, and hash passwords with argon2 or bcrypt.
7. **Test while developing, but don't write test cases.** Verify every change yourself by running it: start the backend/frontend, call endpoints, click through the UI in a browser, run linters and `ng build`. Do not add test case files (unit, integration, UI/e2e), test folders, test dependencies or test config to the repo. Throwaway checks go in the scratchpad outside the project. Formal backend/UI test suites and test tooling will be decided after the project is finished.
8. Ask before destructive or outward-facing actions (deleting files, pushing, deploying, sending messages).

## Tech stack (decided)

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, **FastAPI**, Pydantic v2, SQLAlchemy 2.0 (async) , Alembic migrations |
| Database | PostgreSQL (Render managed Postgres; local via Docker or SQLite for quick dev only if models stay portable) |
| Auth | JWT access + refresh tokens, role-based access control (RBAC) |
| Frontend | **Angular (latest stable)**, TypeScript strict, standalone components, signals, new control flow (`@if/@for`), Angular Material or Tailwind, **PWA** via `@angular/service-worker` (installable, offline shell) |
| i18n | English + Marathi (more languages can be added) |
| PDF | Server-side (e.g. WeasyPrint or ReportLab) for report cards, receipts, certificates |
| Deploy | **Render**: one Web Service (FastAPI serving the built frontend) + one Postgres; defined in `render.yaml` |
| Lint/format | ruff + mypy (strict) for Python; angular-eslint + prettier for frontend |

If you want to change a stack choice, discuss it first and update this table and the README.

## Current status

Foundation is in place: FastAPI backend with JWT auth (access token in memory, refresh token in an httpOnly cookie), schools, branches and users with central tenant scoping in `backend/app/core/tenant.py`; Alembic migration `0001`; Angular login page, `authInterceptor`, `authGuard`/`roleGuard`. Dev ports: backend 8080, frontend 4200 (proxy in `frontend/proxy.conf.json`). Also done: PWA (`@angular/service-worker`, manifest; no API caching), `academics` module (academic years school-wide, classes and sections per branch, migration `0002`) with a `/setup` page. Admin console (schools, branches, users, account) and the `students` module (students, guardians, enrolments, parent/student logins, CSV import/export, migration `0003`, scoping in `scope_students`) are done. The `attendance` module (student and staff attendance, holidays, daily summary, student calendar, CSV export; migration `0004`) is done too. Lesson learned: when an optional string needs a length limit, put the constraint on the `str` inside the union (`Annotated[str, StringConstraints(max_length=N)] | None`), not on the whole optional, or an explicit `null` crashes with a 500. The `notices` module (school/branch/class/section notices, pinning, expiry, read tracking, unread badge and bell, dashboard card; migration `0005`) is done too. The `fees` module (fee heads and structures, invoices, payments with reversal, PDF receipts via reportlab, dues and collection reports, parent "My fees"; all money in integer paise; migration `0006`) is done too. Branding is done too: the Vidyasetu logo (`frontend/public/brand/`, icons in `frontend/public/icons/`), school logo upload (stored in `school_logos`, normalised to PNG by Pillow, public GET so `<img>` works, shown in the sidebar and on receipts; migration `0007`), a School profile page for owners, and a public animated landing page at `/` for visitors (signed-in users still get the dashboard at `/`). Phases 5.2 to 5.12 are also done: sign-in identity, security hardening, settings, consent, audit log and MFA, the compliance pack (`docs/compliance`), admissions and PEN/APAAR identifiers, year-end promotion (migration `0014` changed the student foreign keys to school level so students can change branch), fee tools (concessions, sibling discount, late fees, reminders), global search and dry-run CSV imports. Not done yet: PostgreSQL row-level security, the backup restore drill, running migrations `0013` to `0015` on PostgreSQL, and phases 6 onward (exams and report cards next); see `docs/roadmap.md`. The Angular CLI re-adds an `analytics` id to `frontend/angular.json` whenever `ng` runs; revert it with `git checkout -- frontend/angular.json` before committing.

## Planned repository layout

```
SMS/
├─ CLAUDE.md
├─ README.md
├─ .env.example
├─ render.yaml
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/          # config (reads .env), security, deps, logging
│  │  ├─ db/            # session, base, migrations (alembic/)
│  │  ├─ modules/       # one folder per domain module (see below)
│  │  │   └─ <module>/  # models.py, schemas.py, service.py, router.py
│  │  └─ integrations/  # optional adapters: payments, sms, whatsapp, email, storage
│  └─ pyproject.toml
└─ frontend/
   ├─ src/app/
   │  ├─ core/          # auth (service, interceptor, guards), api client, config, i18n
   │  ├─ shared/        # reusable ui components, pipes, directives
   │  └─ features/      # one lazy-loaded folder per module (students, attendance, fees, ...)
   ├─ public/           # PWA manifest, icons
   └─ package.json
```

Create folders only when the first file in them is needed.

## Domain model essentials

- **School** (tenant): name, logo, board, settings. Branches, users and all data belong to one school. Every tenant table carries `school_id`.
- **Branch**: belongs to a school; has its own timings, management/headmaster, fee structure, timetable, classes and staff. Every branch-level table carries `branch_id` as well as `school_id`.
- Enforce isolation in one central place (a request-scoped tenant context applied to all queries, plus composite foreign keys or PostgreSQL row-level security as a second layer), not by remembering a filter in each query. Adding a new school or branch must need only data, no code changes.
- **Academic year** starts in **April**.
- **Class → Section → Student**; students belong to exactly one branch at a time (e.g. promotion from class 5 → 6 moves them to the secondary branch).
- **Board**: CBSE grading/report-card rules are the default and live in configuration, not hard-coded, so another scheme can be added. The board is a per-school setting; confirm each school's actual board (see `docs/school-profile.md`) before finalising report cards.
- **Roles**: `super_admin` (platform, all schools), `school_owner` (all branches of one school), `management` (per branch), `headmaster` (per branch), `teacher`, `accountant`, `clerk`, `parent`, `student`.

## Working method (phases and agents)

- The phase table in `docs/roadmap.md` is the roadmap (keep it there, not in the README). Work one phase at a time; update its status when a phase starts and when it is done, and record the real date and time (IST, from `Get-Date`) in its *Started* and *Finished* columns.
- Per phase: the main session agrees the data model and API contract first, then runs a **backend agent** (`backend/` only, including its Alembic migration) and a **frontend agent** (`frontend/` only) in parallel. Agents never touch the other side's folder, never commit or push, and never create files outside the app (no tests, notes or scratch files in the repo).
- Only one agent may create an Alembic migration per phase, and it must chain from the current head.
- The main session reviews the result, runs lint/build and a manual check, updates docs, then commits and pushes (see the memory rule on commit and push).

## Modules (build order)

The numbered list below is the original module outline; `docs/roadmap.md` has the authoritative phase order.

1. Foundation: config, auth, RBAC, multi-tenancy (schools, branches), academic years, classes/sections, audit log
2. Students and guardians, admissions, documents
3. Attendance (student and staff) with optional SMS/WhatsApp alerts
4. Notices and circulars
5. Fees: structures, invoices, receipts, dues, optional online payment
6. Exams and CBSE-style report cards (PDF)
7. Timetable (per branch timings), homework
8. Staff, leave, payroll
9. Extras: transport, library (book catalogue), certificates (bonafide, TC, LC)
10. Parent and student portals, dashboards and reports

Ship a thin vertical slice first (login → students → attendance → fees) before widening.

## Design system and layout (set up before building screens)

Reference: the owner's prototype (dark-green sidebar, warm off-white background, rounded white cards, lime active-nav pill). Every screen must follow it.

- **Fonts:** DM Sans (body) and Manrope (headings, big numbers, brand), self-hosted via `@fontsource-variable/*` so the PWA works offline. Headings use weight 650-800 with negative letter-spacing; body is 14px, nav 12px, buttons 11-12px, as in the prototype. Never go below ~10px for text. The prototype's sizes are small, so controls grow to 44px on touch screens and under 1024px.
- **Reference prototype:** a ChatGPT-made prototype is kept locally in a git-ignored folder (path in `docs/school-profile.md`). It is for reading only: its `dist/styles.css` is the source of the tokens and `dist/model.js` has demo data and workflow rules. Do not copy its data (it is fictional) or run its code.
- **Tokens** live in `frontend/src/styles.css` (`:root` variables: colours, radius, shadow, sidebar/topbar sizes, font). Use `var(--*)`; never hard-code colours in components. Rebrand by editing tokens only.
- **Shared classes** in the same file: `.page-header`, `.page-title`, `.page-subtitle`, `.card`, `.card-title`, `.btn` (`-primary`, `-ghost`, `-sm`), `.input`, `.field`, `.badge` (`-success`), `.form-error`, `.field-error`. Prefer these over per-component restyling.
- **App shell** (`core/layout/shell.*`): sidebar + sticky top bar (breadcrumb, search, notifications, user menu). Under 1024px the sidebar becomes a drawer with a menu button. All signed-in screens are children of the shell route in `app.routes.ts`.
- **New screen checklist:** add a child route with `data: { title }` (drives the breadcrumb); add or un-`soon` its entry in `core/layout/nav.ts` (with `roles`); start the template with a `.page-header`; wrap sections in `.card`; mobile-first, 44px touch targets.
- **Icons:** `<sms-icon name="..." />` (`core/ui/icon.ts`); add new stroke icons to its `ICONS` map. No icon library.
- **Search and notifications** in the top bar are placeholders (disabled) until those features exist. Do not show fake numbers; use real data or an empty state.

## Conventions

- API under `/api/v1`, REST, plural nouns, pagination on list endpoints, consistent error shape `{ "detail": ..., "code": ... }`. OpenAPI docs stay enabled in dev, disabled or protected in prod.
- Type hints everywhere; business logic in `service.py`, not in routers.
- Every schema change = an Alembic migration. Never edit a shipped migration.
- Money stored as integer paise (or `Numeric(12,2)`); never floats.
- Timestamps in UTC; display in `Asia/Kolkata`.
- Settings come only from `app/core/config.py` (pydantic-settings reading `.env`). No `os.environ` scattered around.
- **Angular standards** (follow the `angular-developer` skill; create the app with `angular-new-app`):
  - Latest stable Angular and CLI, strict TypeScript, standalone components only (no NgModules), `OnPush` change detection.
  - State with signals (`signal`, `computed`, `linkedSignal`, `resource`/`httpResource`); `input()`/`output()`/`model()` functions; `inject()` instead of constructor injection.
  - Template control flow `@if`, `@for` (with `track`), `@switch`; no `*ngIf`/`*ngFor`.
  - Routing: lazy-loaded feature routes with `loadComponent`/`loadChildren`, functional guards and resolvers.
  - Forms: typed reactive forms (or signal forms if stable in the installed version).
  - HTTP: `provideHttpClient(withInterceptors([...]))` with functional interceptors.
  - **Auth**: `AuthService` (signals for current user and roles) + functional `authInterceptor` (attach access token, refresh on 401 once, then log out) + functional `authGuard`/`roleGuard` on routes. Prefer httpOnly secure cookies for the refresh token; keep the access token in memory, not `localStorage`. Frontend checks are UX only; the backend enforces RBAC.
  - Files named per current Angular style guide, one component per file, small components, services in `core/` or the feature folder.
  - Frontend talks to the backend only through typed API services in `core/`. Mobile-first layouts, 44px touch targets, accessible forms (ARIA, AXE-clean), Marathi/English strings via i18n (no hard-coded UI text).
- Commits small and focused. Do not commit or push unless asked.

## Optional integrations (`.env`)

Each is disabled when its variables are empty. See `.env.example`.

| Integration | Example variables |
|---|---|
| Payments (Razorpay) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` |
| SMS | `SMS_PROVIDER`, `SMS_API_KEY`, `SMS_SENDER_ID`, `SMS_DLT_ENTITY_ID` |
| WhatsApp | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` |
| Email (SMTP) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| File storage (S3-compatible) | `STORAGE_BUCKET`, `STORAGE_KEY`, `STORAGE_SECRET` |

Core required variables: `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`, `SCHOOL_NAME`, `ALLOWED_ORIGINS`.

## Skills to use

- Planning/design: `writing-plans`, `api-designer`, `replica-architect`
- Backend: `fastapi-expert`, `python-pro`, `sql-pro`, `database-optimizer`
- Frontend/UI: `angular-new-app`, `angular-developer`, `ui-ux-pro-max`, `ui-styling`, `design-system`
- Security/review: `secure-code-guardian`, `security-review`, `code-reviewer`
- Deploy: `devops-engineer`, `replica-deploy` (Render)
- Debugging: `systematic-debugging`, `verification-before-completion`

## Definition of done

Feature works end to end (verified by running it), passes ruff/mypy and `ng lint`/`ng build`, has a migration if the schema changed, is documented in `README.md` if user-visible, and introduces no stray files.
