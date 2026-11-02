from pydantic import BaseModel, ConfigDict, Field


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    name: str
    code: str
    is_active: bool


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    # Only used by the platform super admin; school owners always use their own school.
    school_id: int | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
