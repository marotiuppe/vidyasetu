from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.modules.consent import service
from app.modules.consent.schemas import (
    ConsentCreate,
    ConsentsOut,
    PoliciesOut,
    PolicyAccept,
)
from app.modules.settings.deps import require_feature

# Policy acceptance applies to every signed-in user; student consent needs the students module.
router = APIRouter(tags=["consent"])
student_router = APIRouter(tags=["consent"], dependencies=[Depends(require_feature("students"))])


@router.get("/consent/policies", response_model=PoliciesOut)
async def get_policies(db: DbSession, user: CurrentUser) -> PoliciesOut:
    return await service.policies_for(db, user)


@router.post("/consent/policies/accept", response_model=PoliciesOut)
async def accept_policy(data: PolicyAccept, db: DbSession, user: CurrentUser) -> PoliciesOut:
    return await service.accept_policy(db, user, data)


@student_router.get("/students/{student_id}/consents", response_model=ConsentsOut)
async def get_consents(student_id: int, db: DbSession, actor: CurrentUser) -> ConsentsOut:
    return await service.get_consents(db, actor, student_id)


@student_router.post(
    "/students/{student_id}/consents",
    response_model=ConsentsOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_consent(
    student_id: int, data: ConsentCreate, db: DbSession, actor: CurrentUser
) -> ConsentsOut:
    return await service.record_consent(db, actor, student_id, data)
