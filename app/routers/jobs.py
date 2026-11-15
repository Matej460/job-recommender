"""Endpoints for jobs: list with filters, details, create, soft delete."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import JobCreate, JobOut

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    category: str | None = Query(None, description="Example: Software Development"),
    employment_type: str | None = Query(None, description="Internship, Full-time or Part-time"),
    remote_only: bool = Query(False, description="true = only fully remote jobs"),
    db: Session = Depends(get_db),
):
    """All active jobs. The three filters are optional and can be combined."""
    return crud.get_jobs(db, category, employment_type, remote_only)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(data: JobCreate, db: Session = Depends(get_db)):
    """Create a job. The body is validated by the JobCreate schema."""
    return crud.create_job(db, data)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Soft delete (optional extension): sets deleted_at, the row stays in the table."""
    job = crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    crud.soft_delete(db, job)
