"""Data exports: a user's own account data and a student's record (JSON download).

Never included: password hashes, tokens, two-factor secrets or recovery codes.
"""

from typing import Any

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.base import utcnow
from app.modules.attendance.models import AttendanceRecord
from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog
from app.modules.consent import service as consent_service
from app.modules.consent.models import PolicyAcceptance
from app.modules.datarights.models import DataRequest
from app.modules.fees.models import Invoice, Payment
from app.modules.settings import service as settings_service
from app.modules.settings.models import UserPreference
from app.modules.students import service as students_service
from app.modules.users.models import Role, User

AUDIT_LIMIT = 500
# Who may download a whole student record: the school owner, the branch's management and
# headmaster, the family (parents) and platform admins. Teachers, clerks and accountants can see
# a student but cannot take the record out. A student's own login never can.
STUDENT_EXPORT_ROLES = frozenset(
    {Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.PARENT}
)


async def me_export(db: AsyncSession, user: User) -> dict[str, Any]:
    prefs = await db.scalars(select(UserPreference).where(UserPreference.user_id == user.id))
    accepted = await db.scalars(
        select(PolicyAcceptance)
        .where(PolicyAcceptance.user_id == user.id)
        .order_by(PolicyAcceptance.id)
    )
    requests = await db.scalars(
        select(DataRequest)
        .where(DataRequest.requester_user_id == user.id)
        .order_by(DataRequest.id)
    )
    entries = await db.scalars(
        select(AuditLog)
        .where(AuditLog.actor_user_id == user.id)
        .order_by(AuditLog.id.desc())
        .limit(AUDIT_LIMIT)
    )
    data: dict[str, Any] = {
        "exported_at": utcnow(),
        "account": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role.value,
            "school_id": user.school_id,
            "branch_id": user.branch_id,
            "is_active": user.is_active,
            "mfa_enabled": user.mfa_enabled,
            "created_at": user.created_at,
        },
        "preferences": [{"key": p.key, "value": p.value} for p in prefs],
        "policy_acceptances": [
            {"policy": a.policy.value, "version": a.version, "accepted_at": a.accepted_at}
            for a in accepted
        ],
        "data_requests": [
            {
                "id": r.id,
                "type": r.type.value,
                "status": r.status.value,
                "student_id": r.student_id,
                "message": r.message,
                "response_note": r.response_note,
                "created_at": r.created_at,
                "due_on": r.due_on,
            }
            for r in requests
        ],
        "audit_entries_as_actor": [
            {
                "at": e.at,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "outcome": e.outcome,
                "ip": e.ip,
                "detail": e.detail,
            }
            for e in entries
        ],
    }
    await audit.record(db, user, "user.exported", "user", user.id, commit=True)
    return jsonable_encoder(data)  # type: ignore[no-any-return]


async def student_export(db: AsyncSession, actor: User, student_id: int) -> dict[str, Any]:
    if actor.role not in STUDENT_EXPORT_ROLES:
        raise ApiError(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")
    detail = await students_service.get_student(
        db, actor, student_id, log_view=False
    )  # 404 out of scope
    student = detail.model_dump(mode="json")
    guardians = [
        {k: v for k, v in g.items() if k not in ("user_id", "student_id")}
        for g in student.pop("guardians")
    ]
    student.pop("user_id", None)
    enrollments = student.pop("enrollments")
    student.pop("current_enrollment", None)
    student.pop("primary_guardian", None)

    omitted: list[str] = []
    portal = {"fees": True, "attendance": True}
    if actor.role == Role.PARENT:
        v = await settings_service.resolve_many(
            db,
            ["portal.parent_sees_fees", "portal.parent_sees_attendance"],
            settings_service.Ctx(school_id=actor.school_id),
        )
        portal = {
            "fees": bool(v["portal.parent_sees_fees"]),
            "attendance": bool(v["portal.parent_sees_attendance"]),
        }

    attendance: list[dict[str, Any]] | None = None
    if portal["attendance"]:
        rows = await db.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.student_id == student_id)
            .order_by(AttendanceRecord.date)
        )
        attendance = [
            {"date": r.date, "status": r.status.value, "remark": r.remark} for r in rows
        ]
    else:
        omitted.append("attendance")

    fees: dict[str, Any] | None = None
    if portal["fees"]:
        invoices = (
            await db.scalars(
                select(Invoice).where(Invoice.student_id == student_id).order_by(Invoice.id)
            )
        ).all()
        numbers = {i.id: i.invoice_no for i in invoices}
        payments = await db.scalars(
            select(Payment).where(Payment.student_id == student_id).order_by(Payment.id)
        )
        fees = {
            "invoices": [
                {
                    "invoice_no": i.invoice_no,
                    "title": i.title,
                    "due_date": i.due_date,
                    "gross_paise": i.gross_paise,
                    "discount_paise": i.discount_paise,
                    "cancelled": i.status_cancelled,
                }
                for i in invoices
            ],
            "payments": [
                {
                    "receipt_no": p.receipt_no,
                    "invoice_no": numbers.get(p.invoice_id),
                    "amount_paise": p.amount_paise,
                    "method": p.method.value,
                    "paid_on": p.paid_on,
                    "status": p.status.value,
                }
                for p in payments
            ],
        }
    else:
        omitted.append("fees")

    consents = await consent_service.get_consents(db, actor, student_id)
    data: dict[str, Any] = {
        "exported_at": utcnow(),
        "student": student,
        "guardians": guardians,
        "enrollments": enrollments,
        "attendance": attendance,
        "fees": fees,
        "consents": consents.model_dump(mode="json"),
        "omitted_sections": omitted,
    }
    await audit.record(
        db, actor, "student.exported", "student", student_id,
        detail={"scope": "single"}, school_id=detail.school_id, branch_id=detail.branch_id,
        commit=True,
    )
    return jsonable_encoder(data)  # type: ignore[no-any-return]
