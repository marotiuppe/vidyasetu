from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    board: str
    is_active: bool


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    board: str = Field(default="CBSE", max_length=50)
    owner_email: EmailStr
    owner_full_name: str = Field(min_length=1, max_length=200)
    owner_password: str = Field(min_length=8, max_length=128)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    board: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
