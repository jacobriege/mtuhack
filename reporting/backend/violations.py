import json
import uuid
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/violations", tags=["violations"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ViolationIn(BaseModel):
    type: str
    timestamp: int
    image: str
    blackbox: list[int]
    headbox: list[int]

class ViolationSummary(BaseModel):
    violationId: str
    type: str
    timestamp: int

class ViolationCount(BaseModel):
    type: str
    count: int

class ViolationImage(BaseModel):
    violationId: str
    image: str
    blackbox: list[int]
    headbox: list[int]

class ViolationMeta(BaseModel):
    violationId: str
    timestamp: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_summary(r) -> ViolationSummary:
    return ViolationSummary(violationId=r["violationId"], type=r["type"], timestamp=r["timestamp"])


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_violation(payload: ViolationIn):
    vid = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO violations (violationId, type, timestamp, image, blackbox, headbox) VALUES (?,?,?,?,?,?)",
        (vid, payload.type, payload.timestamp, payload.image,
         json.dumps(payload.blackbox), json.dumps(payload.headbox)),
    )
    db.commit()
    db.close()
    return {"violationId": vid}


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get("/unread", response_model=list[ViolationSummary])
def get_unread():
    db = get_db()
    rows = db.execute("SELECT * FROM violations WHERE read=0").fetchall()
    db.close()
    return [_row_to_summary(r) for r in rows]


@router.get("/bydate", response_model=list[ViolationSummary])
def get_by_date(startdate: int = Query(...), enddate: int = Query(...), flagged: bool = Query(None)):
    db = get_db()
    if flagged is None:
        rows = db.execute(
            "SELECT * FROM violations WHERE timestamp BETWEEN ? AND ?", (startdate, enddate)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM violations WHERE timestamp BETWEEN ? AND ? AND flagged=?",
            (startdate, enddate, int(flagged)),
        ).fetchall()
    db.close()
    return [_row_to_summary(r) for r in rows]


@router.get("/count", response_model=list[ViolationCount])
def get_counts():
    db = get_db()
    rows = db.execute("SELECT type, COUNT(*) as count FROM violations GROUP BY type").fetchall()
    db.close()
    return [ViolationCount(type=r["type"], count=r["count"]) for r in rows]


@router.get("/instance/image", response_model=ViolationImage)
def get_instance_image(violationId: str = Query(...)):
    db = get_db()
    r = db.execute("SELECT * FROM violations WHERE violationId=?", (violationId,)).fetchone()
    db.close()
    if not r:
        raise HTTPException(404, "Violation not found")
    return ViolationImage(violationId=r["violationId"], image=r["image"],
                          blackbox=json.loads(r["blackbox"]), headbox=json.loads(r["headbox"]))


@router.get("/instance/flag")
def flag_instance(violationId: str = Query(...)):
    db = get_db()
    r = db.execute("SELECT flagged FROM violations WHERE violationId=?", (violationId,)).fetchone()
    if not r:
        db.close()
        raise HTTPException(404, "Violation not found")
    new_flag = 0 if r["flagged"] else 1
    db.execute("UPDATE violations SET flagged=? WHERE violationId=?", (new_flag, violationId))
    db.commit()
    db.close()
    return {"violationId": violationId, "flagged": bool(new_flag)}


@router.get("/instance/meta", response_model=ViolationMeta)
def get_instance_meta(violationId: str = Query(...)):
    db = get_db()
    r = db.execute("SELECT violationId, timestamp FROM violations WHERE violationId=?", (violationId,)).fetchone()
    db.close()
    if not r:
        raise HTTPException(404, "Violation not found")
    return ViolationMeta(violationId=r["violationId"], timestamp=r["timestamp"])
