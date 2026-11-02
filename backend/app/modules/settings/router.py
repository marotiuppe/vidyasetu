
from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession
from app.modules.settings import service
from app.modules.settings.schemas import (
    IntegrationName,
    IntegrationTestResult,
    Level,
    LevelsOut,
    SettingItem,
    SettingWrite,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/levels", response_model=LevelsOut)
async def get_levels(db: DbSession, user: CurrentUser) -> LevelsOut:
    return await service.levels(db, user)


@router.get("", response_model=list[SettingItem])
async def list_settings(
    db: DbSession,
    user: CurrentUser,
    level: Level,
    school_id: int | None = None,
    branch_id: int | None = None,
) -> list[SettingItem]:
    return await service.list_items(db, user, level, school_id, branch_id)


@router.put("/{level}/{key}", response_model=SettingItem)
async def put_setting(
    level: Level, key: str, data: SettingWrite, db: DbSession, user: CurrentUser
) -> SettingItem:
    return await service.put_value(
        db, user, level, key, data.value, data.school_id, data.branch_id
    )


@router.delete("/{level}/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    level: Level,
    key: str,
    db: DbSession,
    user: CurrentUser,
    school_id: int | None = None,
    branch_id: int | None = None,
) -> Response:
    await service.reset_value(db, user, level, key, school_id, branch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/school/integrations/{name}/test", response_model=IntegrationTestResult)
async def test_integration(
    name: IntegrationName, db: DbSession, user: CurrentUser, school_id: int | None = None
) -> IntegrationTestResult:
    return await service.check_integration(db, user, name, school_id)
