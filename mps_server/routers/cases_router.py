from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel as _BaseModel

class VetterReturnBody(_BaseModel):
    comment: str

from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import joinedload
from ..database import Case, Session, Letter, Resident, get_db, User
from ..auth import require_volunteer, require_vetter, get_current_user
from ..services.audit import log_event
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/cases", tags=["cases"])

class CaseCreateRequest(BaseModel):
    session_id:     str
    resident_id:    str
    case_type:      str
    agency:         str
    urgency:        str = "normal"
    is_new_issue:   bool = True
    parent_case_id: Optional[str] = None

@router.get("/mine")
def my_cases(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_volunteer),
):
    """Tonight's cases assigned to this volunteer."""
    # Get current active session
    session = (db.query(Session)
               .filter(Session.status.in_(["open", "active"]))
               .order_by(Session.opened_at.desc()).first())
    if not session:
        return {"cases": [], "message": "No active session"}

    cases = (db.query(Case)
             .filter(Case.session_id == session.id,
                     Case.volunteer_id == current_user.id)
             .order_by(Case.urgency.desc(), Case.created_at.asc())
             .all())
    return {"session_id": session.id, "cases": [_fmt(c) for c in cases]}

@router.get("/queue")
def vetter_queue(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    """Letters ready for vetter review."""
    session = (db.query(Session)
               .filter(Session.status.in_(["open", "active"]))
               .order_by(Session.opened_at.desc()).first())
    if not session:
        return {"cases": []}

    cases = (db.query(Case)
             .filter(Case.session_id == session.id,
                     Case.status == "drafted")
             .all())
    return {"session_id": session.id, "pending_count": len(cases),
            "cases": [_fmt(c) for c in cases]}

@router.post("/")
def create_case(
    req: CaseCreateRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_volunteer),
):
    resident = db.query(Resident).filter(Resident.id == req.resident_id).first()
    if not resident:
        raise HTTPException(404, "Resident not found")
    session = db.query(Session).filter(Session.id == req.session_id).first()
    if not session or session.status not in ("open", "active"):
        raise HTTPException(400, "No active session found")

    case = Case(
        session_id=req.session_id,
        resident_id=req.resident_id,
        case_type=req.case_type,
        agency=req.agency,
        urgency=req.urgency,
        is_new_issue=req.is_new_issue,
        parent_case_id=req.parent_case_id,
        volunteer_id=current_user.id,
        status="assigned",
    )
    db.add(case)
    session.total_cases = (session.total_cases or 0) + 1
    db.commit()
    log_event(db, "case_created", user_id=current_user.id, role=current_user.role,
              session_id=req.session_id, case_id=case.id,
              client_ip=request.client.host if request.client else None,
              details={"case_type": req.case_type, "agency": req.agency})
    return _fmt(case)

@router.post("/{case_id}/submit")
def submit_for_vetting(
    case_id: str,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_volunteer),
):
    case = _get_own_case(case_id, current_user.id, db)
    if case.status not in ("assigned", "drafting", "drafted"):
        raise HTTPException(400, "Case is not in a submittable state")
    case.status = "drafted"
    db.commit()
    log_event(db, "case_submitted", user_id=current_user.id, role=current_user.role,
              case_id=case_id, client_ip=request.client.host if request.client else None)
    return {"case_id": case_id, "status": case.status}

@router.post("/{case_id}/vetter-pass")
def vetter_pass(
    case_id: str,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.status != "drafted":
        raise HTTPException(400, "Case not in review queue")
    case.status = "vetted"
    letter = _latest_letter(case)
    if letter:
        letter.status = "vetted"
        letter.vetted_at = datetime.now(timezone.utc)
    db.commit()
    log_event(db, "vetter_passed", user_id=current_user.id, role=current_user.role,
              case_id=case_id, client_ip=request.client.host if request.client else None)
    return {"case_id": case_id, "status": "vetted"}

@router.post("/{case_id}/vetter-return")
def vetter_return(
    case_id: str,
    body: VetterReturnBody,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_vetter),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.status != "drafted":
        raise HTTPException(400, "Case not in review queue")
    case.status = "assigned"
    letter = _latest_letter(case)
    if letter:
        letter.status = "returned"
        letter.vetter_comment = body.comment
    db.commit()
    log_event(db, "vetter_returned", user_id=current_user.id, role=current_user.role,
              case_id=case_id, details={"comment": body.comment},
              client_ip=request.client.host if request.client else None)
    return {"case_id": case_id, "status": "returned", "comment": body.comment}

def _get_own_case(case_id: str, user_id: str, db: DBSession) -> Case:
    case = db.query(Case).filter(Case.id == case_id,
                                  Case.volunteer_id == user_id).first()
    if not case:
        raise HTTPException(404, "Case not found or not assigned to you")
    return case

def _latest_letter(case: Case):
    if not case.letters:
        return None
    return sorted(case.letters, key=lambda l: l.version, reverse=True)[0]

def _fmt(c: Case) -> dict:
    letter = _latest_letter(c)
    # Include resident inline so GTK4 client can display name/NRIC without extra call
    res = None
    if hasattr(c, "resident") and c.resident:
        r = c.resident
        res = {"id": r.id, "name": r.name, "nric_masked": r.nric_masked,
               "contact": r.contact or ""}
    return {
        "id": c.id, "case_type": c.case_type, "agency": c.agency,
        "status": c.status, "urgency": c.urgency,
        "is_new_issue": c.is_new_issue, "parent_case_id": c.parent_case_id,
        "resident_id": c.resident_id, "session_id": c.session_id,
        "resident": res,
        "vetter_comment": letter.vetter_comment if letter else None,
        # GTK4 client uses "letter_id"
        "letter_id": letter.id if letter else None,
        "latest_letter_id": letter.id if letter else None,
        "letter_status": letter.status if letter else None,
    }
