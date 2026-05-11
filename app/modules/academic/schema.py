import uuid
from pydantic import BaseModel, field_validator
from datetime import date, datetime


def clean_words(value: str | None) -> str | None:
    if value is None:
        return value
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def clean_code(value: str | None) -> str | None:
    if value is None:
        return value
    return " ".join(value.strip().split()).upper()


# Academic Year
class AcademicYearCreate(BaseModel):
    institution_id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    is_current: bool = False

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value):
        return clean_words(value)


class AcademicYearUpdate(BaseModel):
    label: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    is_active: bool | None = None

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value):
        return clean_words(value)


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

    @field_validator("name", "level", mode="before")
    @classmethod
    def normalize_words(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


class CourseUpdate(BaseModel):
    institution_id: uuid.UUID
    name: str | None = None
    code: str | None = None
    level: str | None = None
    duration_years: int | None = None
    is_active: bool | None = None

    @field_validator("name", "level", mode="before")
    @classmethod
    def normalize_words(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


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

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


class BranchUpdate(BaseModel):
    course_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


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
    course_id: uuid.UUID
    class_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    semester: int | None = None
    academic_year_id: uuid.UUID | None = None
    name: str
    code: str
    credits: int = 0

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


class SubjectUpdate(BaseModel):
    course_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    semester: int | None = None
    academic_year_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    credits: int | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return clean_code(value)


class SubjectOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    class_id: uuid.UUID
    branch_id: uuid.UUID | None
    semester: int | None
    academic_year_id: uuid.UUID | None
    name: str
    code: str
    credits: int
    is_active: bool

    class Config:
        from_attributes = True


# Class
class ClassCreate(BaseModel):
    course_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    name: str
    year_no: int | None = None
    semester: int | None = None
    intake_capacity: int = 60

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)


class ClassUpdate(BaseModel):
    course_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    name: str | None = None
    year_no: int | None = None
    semester: int | None = None
    intake_capacity: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)


class ClassOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    branch_id: uuid.UUID | None
    academic_year_id: uuid.UUID | None
    name: str
    year_no: int | None
    semester: int | None
    intake_capacity: int

    class Config:
        from_attributes = True


# Section
class SectionCreate(BaseModel):
    class_id: uuid.UUID
    name: str
    max_strength: int = 60

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)


class SectionUpdate(BaseModel):
    name: str | None = None
    max_strength: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return clean_words(value)


class SectionOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    name: str
    max_strength: int

    class Config:
        from_attributes = True
