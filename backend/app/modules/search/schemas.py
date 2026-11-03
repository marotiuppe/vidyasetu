from typing import Literal

from pydantic import BaseModel

SearchType = Literal["students", "guardians", "admissions", "invoices", "receipts", "notices"]


class SearchItem(BaseModel):
    id: int
    title: str
    # Never a phone number: guardians show their relation and the student's name.
    subtitle: str | None = None
    # A frontend route the user may open.
    url: str


class SearchGroup(BaseModel):
    type: SearchType
    items: list[SearchItem]


class SearchResponse(BaseModel):
    q: str
    groups: list[SearchGroup]
