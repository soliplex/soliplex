"""Pydantic models for Moodle REST API responses."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class Course(BaseModel):
    id: int
    shortname: str
    fullname: str
    categoryid: int = 0
    summary: str = ""
    startdate: int = 0
    enddate: int = 0
    visible: int = 1
    format: str = ""
    enablecompletion: int = 0


class UserProfile(BaseModel):
    id: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    email: str = ""
    department: str = ""
    firstaccess: int = 0
    lastaccess: int = 0


class Role(BaseModel):
    roleid: int
    name: str = ""
    shortname: str = ""


class EnrolledUser(BaseModel):
    id: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    email: str = ""
    department: str = ""
    roles: list[Role] = Field(default_factory=list)


class CompletionDetails(BaseModel):
    type: str = ""
    criteria: str = ""
    requirement: str = ""
    status: str = ""


class CompletionCriteria(BaseModel):
    type: int = 0
    title: str = ""
    status: str = ""
    complete: bool = False
    timecompleted: int | None = None
    details: CompletionDetails | None = None


class CompletionStatus(BaseModel):
    completed: bool
    aggregation: int = 0
    completions: list[CompletionCriteria] = Field(
        default_factory=list,
    )
