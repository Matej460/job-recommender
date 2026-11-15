"""Pydantic schemas: validate what comes into the API and shape what goes out."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The only values that are allowed for these two fields.
EmploymentType = Literal["Internship", "Full-time", "Part-time"]
WorkMode = Literal["On-site", "Hybrid", "Remote"]


# ---------- Jobs ----------


class JobCreate(BaseModel):
    """Body of POST /jobs."""

    title: str = Field(min_length=2, max_length=150)
    description: str = Field(min_length=2)
    category: str = Field(min_length=2, max_length=100)
    employer: str = Field(min_length=2, max_length=150)
    location_name: str = Field(min_length=2, max_length=150)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    employment_type: EmploymentType
    work_mode: WorkMode
    required_skills: list[str] = Field(min_length=1)
    target_audience: str = Field(min_length=2, max_length=100)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    application_deadline: date
    vacancies: int = Field(ge=1)
    filled_positions: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_ranges(self):
        """Rules that compare two fields with each other."""
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot be greater than salary_max")
        if self.filled_positions > self.vacancies:
            raise ValueError("filled_positions cannot be greater than vacancies")
        return self


class JobOut(BaseModel):
    """A job as returned by the API."""

    # from_attributes=True lets Pydantic read the values straight from a SQLAlchemy object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: str
    employer: str
    location_name: str
    latitude: float
    longitude: float
    employment_type: str
    work_mode: str
    required_skills: list[str]
    target_audience: str
    salary_min: int | None
    salary_max: int | None
    application_deadline: date
    vacancies: int
    filled_positions: int
    available_positions: int
    created_at: datetime
    updated_at: datetime


# ---------- Candidates ----------


class CandidateCreate(BaseModel):
    """Body of POST /candidates."""

    name: str = Field(min_length=2, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    study_area: str = Field(min_length=2, max_length=100)
    year_of_study: int = Field(ge=1, le=5, description="1-4 = student, 5 = recent graduate")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    skills: list[str] = Field(min_length=1)
    interests: list[str] = Field(default_factory=list)
    preferred_employment_type: EmploymentType
    preferred_work_mode: WorkMode
    available_from: time
    available_to: time
    min_salary: int = Field(ge=0)

    @model_validator(mode="after")
    def check_availability(self):
        if self.available_from >= self.available_to:
            raise ValueError("available_from must be earlier than available_to")
        return self


class CandidateOut(BaseModel):
    """A candidate as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    study_area: str
    year_of_study: int
    latitude: float
    longitude: float
    skills: list[str]
    interests: list[str]
    preferred_employment_type: str
    preferred_work_mode: str
    available_from: time
    available_to: time
    min_salary: int
    created_at: datetime
    updated_at: datetime


# ---------- Recommendations ----------


class ScoreDetail(BaseModel):
    """One row of the score breakdown, e.g. skills: 20 of 30 points."""

    criterion: str
    points: float
    max_points: int


class RecommendationItem(BaseModel):
    job_id: int
    title: str
    category: str
    employer: str
    employment_type: str
    work_mode: str
    location_name: str
    distance_km: float | None  # None for remote jobs
    salary_min: int | None
    salary_max: int | None
    application_deadline: date
    available_positions: int
    score: float
    reason: str
    score_breakdown: list[ScoreDetail]


class RecommendationResponse(BaseModel):
    candidate_id: int | None  # None when the request came without a saved candidate
    candidate_name: str | None
    recommendations: list[RecommendationItem]


# ---------- Job applications (optional extension) ----------


class ApplicationCreate(BaseModel):
    """Body of POST /applications."""

    candidate_id: int
    job_id: int


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    job_id: int
    application_datetime: datetime
    status: str
