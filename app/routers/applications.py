"""Optional extension: a candidate applies for a job."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import ApplicationCreate, ApplicationOut
from app.scoring import is_eligible

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_for_job(data: ApplicationCreate, db: Session = Depends(get_db)):
    if crud.get_candidate(db, data.candidate_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    job = crud.get_job(db, data.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    # The same rule as for recommendations: expired or filled jobs are closed.
    if not is_eligible(job, date.today()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This job no longer accepts applications")

    if data.job_id in crud.get_applied_job_ids(db, data.candidate_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "The candidate already applied for this job")

    return crud.create_application(db, data.candidate_id, data.job_id)
