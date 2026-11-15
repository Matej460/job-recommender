"""Endpoints that return ranked job recommendations."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import Candidate
from app.schemas import RecommendationResponse
from app.scoring import recommend

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=RecommendationResponse)
def recommend_by_location_and_skills(
    lat: float = Query(..., ge=-90, le=90, description="Your latitude, e.g. 41.9981"),
    lon: float = Query(..., ge=-180, le=180, description="Your longitude, e.g. 21.4254"),
    skills: str = Query(..., description="Comma-separated skills, e.g. Python,SQL,Git"),
    category: str | None = None,
    employment_type: str | None = None,
    remote_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Recommendations for a visitor who is not saved as a candidate.

    Only location and skills are known, so only the criteria that can be checked
    (skills, distance, availability) are used for the score.
    """
    skill_list = [skill.strip() for skill in skills.split(",") if skill.strip()]
    if not skill_list:
        raise HTTPException(422, "Provide at least one skill")  # 422 = invalid input

    # A temporary candidate object. It is never added to the database session,
    # so nothing is saved. All the other fields stay None.
    visitor = Candidate(latitude=lat, longitude=lon, skills=skill_list)

    jobs = crud.get_jobs(db, category, employment_type, remote_only)
    return {
        "candidate_id": None,
        "candidate_name": None,
        "recommendations": recommend(visitor, jobs, date.today(), limit),
    }


@router.get("/{candidate_id}", response_model=RecommendationResponse)
def recommend_for_candidate(
    candidate_id: int,
    category: str | None = None,
    employment_type: str | None = None,
    remote_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Ranked recommendations for a saved candidate. The job filters are optional."""
    candidate = crud.get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    jobs = crud.get_jobs(db, category, employment_type, remote_only)

    # Jobs the candidate already applied for are not recommended again.
    applied_job_ids = crud.get_applied_job_ids(db, candidate_id)
    jobs = [job for job in jobs if job.id not in applied_job_ids]

    return {
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "recommendations": recommend(candidate, jobs, date.today(), limit),
    }
