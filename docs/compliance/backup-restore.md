# Backup and restore procedure (draft)

Status: **procedure written, drill NOT yet executed.** Do the drill against a scratch PostgreSQL database before real student data is entered, then record the date and the measured restore time here.

## Backup
- Managed Postgres on the hosting provider: enable its automated backups (check the plan; the `free` plan in `render.yaml` may not keep any).
- Extra copy: `pg_dump --format=custom --no-owner "$DATABASE_URL" > sms-YYYYMMDD.dump`, stored encrypted, outside the repository, kept for the backup window in the retention schedule.
- Uploaded files (school logos) live in the database (`school_logos`), so they are included.
- Never store dumps in the repository or paste them into tickets: they contain data of minors.

## Restore drill
1. Create an empty scratch database (never the live one).
2. `pg_restore --no-owner --dbname "$SCRATCH_URL" sms-YYYYMMDD.dump`
3. Point a local backend at it (`DATABASE_URL`), run `alembic current` (must equal the head) and `alembic upgrade head`.
4. Sign in, open students, a receipt PDF and the audit log; check the audit-log append-only triggers exist.
5. Record: date, dump size, restore time, problems found. Delete the scratch database.

## Open points
- Which backup window and recovery time the school accepts (see `retention-schedule.md`).
- Backups keep deleted records until the window ends; say so in the privacy policy.
