from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..database import get_db, FeedbackEntry, Case, User
from ..auth import get_current_user, require_volunteer, require_vetter
from ..services.audit import log_event

router = APIRouter(prefix="/feedback", tags=["feedback"])

# ── Schemas ──────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    case_id: int
    agency_code: str          # HDB, CPF, MSF, MOH, MOM, ICA
    incorrect_claim: str      # what the agent said that was wrong
    correct_answer: str       # the correct information
    session_id: Optional[int] = None

class FeedbackValidate(BaseModel):
    action: str               # "approve" or "reject"
    reject_reason: Optional[str] = None

class FeedbackOut(BaseModel):
    id: int
    session_id: Optional[int]
    case_id: int
    agency_code: str
    incorrect_claim: str
    correct_answer: str
    status: str               # pending, approved, rejected
    logged_by: int
    validated_by: Optional[int]
    reject_reason: Optional[str]
    created_at: datetime
    validated_at: Optional[datetime]

    class Config:
        from_attributes = True

# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=FeedbackOut)
async def log_feedback(
    body: FeedbackCreate,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_volunteer),
):
    """
    Volunteer or vetter logs a case where the LLM produced wrong information.
    Status starts as 'pending' — a vetter must validate before it reaches Hermes.
    """
    # Resolve session_id from case if not provided
    session_id = body.session_id
    if session_id is None:
        case = db.query(Case).filter(Case.id == body.case_id).first()
        if case:
            session_id = case.session_id

    entry = FeedbackEntry(
        session_id=session_id,
        case_id=body.case_id,
        agency_code=body.agency_code.upper(),
        incorrect_claim=body.incorrect_claim,
        correct_answer=body.correct_answer,
        logged_by=current_user.id,
        status="pending",
    )
    db.add(entry)
    db.flush()

    log_event(
        db,
        event_type="FEEDBACK_LOGGED",
        user_id=current_user.id,
        role=current_user.role,
        session_id=session_id,
        case_id=body.case_id,
        client_ip=request.client.host if request.client else None,
        details=f"agency={body.agency_code} feedback_id={entry.id}",
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/pending", response_model=List[FeedbackOut])
async def list_pending_feedback(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    """Vetter sees all feedback entries awaiting validation."""
    entries = (
        db.query(FeedbackEntry)
        .filter(FeedbackEntry.status == "pending")
        .order_by(FeedbackEntry.created_at.asc())
        .all()
    )
    return entries


@router.get("/approved", response_model=List[FeedbackOut])
async def list_approved_feedback(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    """
    Hermes GEPA reads approved feedback to improve SKILL files.
    Only approved entries — no constituent data passes through.
    """
    entries = (
        db.query(FeedbackEntry)
        .filter(FeedbackEntry.status == "approved")
        .order_by(FeedbackEntry.validated_at.asc())
        .all()
    )
    return entries


@router.post("/{feedback_id}/validate", response_model=FeedbackOut)
async def validate_feedback(
    feedback_id: int,
    body: FeedbackValidate,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    """
    Vetter approves or rejects a feedback entry.
    Only approved entries are forwarded to Hermes GEPA.
    Rejected entries are archived with a reason.
    """
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    entry = db.query(FeedbackEntry).filter(FeedbackEntry.id == feedback_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Feedback entry not found")
    if entry.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Entry is already '{entry.status}' — cannot re-validate",
        )

    if body.action == "reject" and not body.reject_reason:
        raise HTTPException(
            status_code=422,
            detail="reject_reason is required when rejecting feedback",
        )

    entry.status = "approved" if body.action == "approve" else "rejected"
    entry.validated_by = current_user.id
    entry.validated_at = datetime.utcnow()
    if body.reject_reason:
        entry.reject_reason = body.reject_reason

    log_event(
        db,
        event_type=f"FEEDBACK_{entry.status.upper()}",
        user_id=current_user.id,
        role=current_user.role,
        session_id=entry.session_id,
        case_id=entry.case_id,
        client_ip=request.client.host if request.client else None,
        details=f"feedback_id={feedback_id} action={body.action}",
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/my", response_model=List[FeedbackOut])
async def my_feedback(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_volunteer),
):
    """Returns feedback entries logged by the current user."""
    entries = (
        db.query(FeedbackEntry)
        .filter(FeedbackEntry.logged_by == current_user.id)
        .order_by(FeedbackEntry.created_at.desc())
        .limit(50)
        .all()
    )
    return entries
