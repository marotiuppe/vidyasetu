from collections.abc import Awaitable, Callable

from fastapi import status

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ApiError
from app.modules.settings import service
from app.modules.users.models import Role


def require_feature(feature: str) -> Callable[[DbSession, CurrentUser], Awaitable[None]]:
    """Router dependency: 403 `feature_disabled` when the module is off for the user's school.

    Platform admins are exempt.
    """

    async def checker(db: DbSession, user: CurrentUser) -> None:
        if user.role == Role.SUPER_ADMIN or user.school_id is None:
            return
        if not await service.feature_enabled(db, user.school_id, feature):
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "This module is switched off for your school",
                "feature_disabled",
            )

    return checker
