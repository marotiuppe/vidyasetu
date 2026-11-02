from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: Role
    school_id: int | None
    branch_id: int | None
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    # Super admin must give school_id; school owner's school is implied.
    school_id: int | None = None
    # Required for branch-bound roles when the creator is not tied to one branch.
    branch_id: int | None = None
