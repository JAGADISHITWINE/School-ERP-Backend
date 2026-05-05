import uuid
from pydantic import BaseModel
from datetime import date, datetime


# Academic Year
class AcademicYearCreate(BaseModel):
    institution_id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    is_current: bool = False


class AcademicYearUpdate(BaseModel):
    label: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    is_active: bool | None = None


class AcademicYearOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    is_current: bool
    is_active: bool

    class Config:
        from_attributes = True


# Course
class CourseCreate(BaseModel):
    institution_id: uuid.UUID
    name: str
    code: str
    level: str
    duration_years: int


class CourseUpdate(BaseModel):
    name: str | None = None
    level: str | None = None
    duration_years: int | None = None
    is_active: bool | None = None


class CourseOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    code: str
    level: str
    duration_years: int
    is_active: bool

    class Config:
        from_attributes = True


# Branch
class BranchCreate(BaseModel):
    course_id: uuid.UUID
    name: str
    code: str


class BranchUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class BranchOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True


# Subject
class SubjectCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    name: str
    code: str
    credits: int = 0


class SubjectUpdate(BaseModel):
    academic_year_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    credits: int | None = None
    is_active: bool | None = None


class SubjectOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID | None
    name: str
    code: str
    credits: int
    is_active: bool

    class Config:
        from_attributes = True


# Class
class ClassCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    name: str
    semester: int


class ClassUpdate(BaseModel):
    academic_year_id: uuid.UUID | None = None
    name: str | None = None
    semester: int | None = None


class ClassOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID | None
    name: str
    semester: int

    class Config:
        from_attributes = True


# Section
class SectionCreate(BaseModel):
    class_id: uuid.UUID
    name: str
    max_strength: int = 60


class SectionUpdate(BaseModel):
    name: str | None = None
    max_strength: int | None = None


class SectionOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    name: str
    max_strength: int

    class Config:
        from_attributes = True
