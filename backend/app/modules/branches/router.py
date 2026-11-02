from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.branches import service
from app.modules.branches.schemas import BranchCreate, BranchOut, BranchUpdate
from app.modules.users.models import Role

router = APIRouter(prefix="/branches", tags=["branches"])

_owners = require_roles(Role.SUPER_ADMIN, Role.SCHOOL_OWNER)


@router.get("", response_model=list[BranchOut])
async def list_branches(db: DbSession, actor: CurrentUser) -> list[BranchOut]:
    return [BranchOut.model_validate(b) for b in await service.list_branches(db, actor)]


@router.post(
    "",
    response_model=BranchOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_owners)],
)
async def create_branch(data: BranchCreate, db: DbSession, actor: CurrentUser) -> BranchOut:
    return BranchOut.model_validate(await service.create_branch(db, actor, data))


@router.get("/{branch_id}", response_model=BranchOut)
async def get_branch(branch_id: int, db: DbSession, actor: CurrentUser) -> BranchOut:
    return BranchOut.model_validate(await service.get_branch(db, actor, branch_id))


@router.patch("/{branch_id}", response_model=BranchOut, dependencies=[Depends(_owners)])
async def update_branch(
    branch_id: int, data: BranchUpdate, db: DbSession, actor: CurrentUser
) -> BranchOut:
    return BranchOut.model_validate(await service.update_branch(db, actor, branch_id, data))
