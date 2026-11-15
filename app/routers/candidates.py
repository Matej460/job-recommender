"""Endpoints for candidates: list, details, create, soft delete."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import ApplicationOut, CandidateCreate, CandidateOut

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)):
    return crud.get_candidates(db)


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = crud.get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return candidate


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db)):
    """Create a candidate. The e-mail address must be unique."""
    if crud.get_candidate_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A candidate with this email already exists")
    return crud.create_candidate(db, data)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Soft delete (optional extension): sets deleted_at, the row stays in the table."""
    candidate = crud.get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    crud.soft_delete(db, candidate)


@router.get("/{candidate_id}/applications", response_model=list[ApplicationOut])
def list_candidate_applications(candidate_id: int, db: Session = Depends(get_db)):
    """Optional extension: jobs this candidate applied for."""
    if crud.get_candidate(db, candidate_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return crud.get_applications(db, candidate_id)
