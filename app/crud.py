"""All database queries in one place. The routers call these functions.

Every query filters on ``deleted_at IS NULL``, so soft-deleted rows are never returned.
"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Candidate, Job, JobApplication
from app.schemas import CandidateCreate, JobCreate

# ---------- Jobs ----------


def get_jobs(
    db: Session,
    category: str | None = None,
    employment_type: str | None = None,
    remote_only: bool = False,
) -> list[Job]:
    """Active jobs. Every filter that is given is added to the query, so they combine with AND."""
    query = db.query(Job).filter(Job.deleted_at.is_(None))
    if category:
        # lower() on both sides makes the filter case-insensitive
        query = query.filter(func.lower(Job.category) == category.strip().lower())
    if employment_type:
        query = query.filter(func.lower(Job.employment_type) == employment_type.strip().lower())
    if remote_only:
        query = query.filter(Job.work_mode == "Remote")
    return query.order_by(Job.id).all()


def get_job(db: Session, job_id: int) -> Job | None:
    return db.query(Job).filter(Job.id == job_id, Job.deleted_at.is_(None)).first()


def create_job(db: Session, data: JobCreate) -> Job:
    job = Job(**data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)  # reload the row to get the id and timestamps set by the database
    return job


def soft_delete(db: Session, row) -> None:
    """Hide a job or a candidate without removing the row from the table."""
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()


# ---------- Candidates ----------


def get_candidates(db: Session) -> list[Candidate]:
    return db.query(Candidate).filter(Candidate.deleted_at.is_(None)).order_by(Candidate.id).all()


def get_candidate(db: Session, candidate_id: int) -> Candidate | None:
    return (
        db.query(Candidate)
        .filter(Candidate.id == candidate_id, Candidate.deleted_at.is_(None))
        .first()
    )


def get_candidate_by_email(db: Session, email: str) -> Candidate | None:
    return db.query(Candidate).filter(func.lower(Candidate.email) == email.lower()).first()


def create_candidate(db: Session, data: CandidateCreate) -> Candidate:
    candidate = Candidate(**data.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


# ---------- Job applications (optional extension) ----------


def get_applications(db: Session, candidate_id: int) -> list[JobApplication]:
    return (
        db.query(JobApplication)
        .filter(JobApplication.candidate_id == candidate_id, JobApplication.deleted_at.is_(None))
        .order_by(JobApplication.id)
        .all()
    )


def get_applied_job_ids(db: Session, candidate_id: int) -> set[int]:
    """Ids of the jobs the candidate already applied for."""
    return {application.job_id for application in get_applications(db, candidate_id)}


def create_application(db: Session, candidate_id: int, job_id: int) -> JobApplication:
    application = JobApplication(candidate_id=candidate_id, job_id=job_id, status="submitted")
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
