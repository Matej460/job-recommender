"""SQLAlchemy models = the database tables."""

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)

from app.database import Base


class TimestampMixin:
    """Three columns that every table must have (required by the project brief).

    created_at - set by the database when the row is inserted
    updated_at - set by the database on insert and refreshed on every update
    deleted_at - "soft delete": NULL means the row is active; a timestamp means
                 the row is hidden from the application but still kept in the table
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    study_area = Column(String(100), nullable=False)
    year_of_study = Column(Integer, nullable=False)  # 1-4 = student, 5 = recent graduate
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    skills = Column(JSON, nullable=False)  # list of strings, e.g. ["Python", "SQL"]
    interests = Column(JSON, nullable=False)  # list of job categories
    preferred_employment_type = Column(String(20), nullable=False)
    preferred_work_mode = Column(String(20), nullable=False)
    available_from = Column(Time, nullable=False)
    available_to = Column(Time, nullable=False)
    min_salary = Column(Integer, nullable=False)  # MKD per month


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    employer = Column(String(150), nullable=False)
    location_name = Column(String(150), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    employment_type = Column(String(20), nullable=False, index=True)
    work_mode = Column(String(20), nullable=False)
    required_skills = Column(JSON, nullable=False)  # list of strings
    target_audience = Column(String(100), nullable=False)
    salary_min = Column(Integer, nullable=True)  # NULL = salary not advertised
    salary_max = Column(Integer, nullable=True)
    application_deadline = Column(Date, nullable=False)
    vacancies = Column(Integer, nullable=False)
    filled_positions = Column(Integer, nullable=False, default=0)

    @property
    def available_positions(self) -> int:
        """How many positions are still open (never negative)."""
        return max(self.vacancies - self.filled_positions, 0)


class JobApplication(TimestampMixin, Base):
    """Optional table: a candidate applied for a job."""

    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    application_datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), nullable=False, default="submitted")
