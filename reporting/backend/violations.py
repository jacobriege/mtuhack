import base64
import json
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from PIL import Image, ImageDraw
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/violations", tags=["violations"])

IMAGES_DIR = Path("violation_images")
IMAGES_DIR.mkdir(exist_ok=True)


class _ConnectionManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, data: dict):
        dead: set[WebSocket] = set()
        for ws in self._clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead


_manager = _ConnectionManager()


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
    imageUrl: str
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


def _apply_sad_emoji(image_b64: str, blackbox: list[int]) -> bytes:
    """Return JPEG bytes with the blackbox region replaced by a drawn sad emoji face."""
    img = Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGB")
    draw = ImageDraw.Draw(img)

    x, y, w, h = blackbox  # [x, y, width, height]
    x2, y2 = x + w, y + h

    # Yellow face
    draw.ellipse([x, y, x2, y2], fill=(255, 220, 0), outline=(200, 170, 0), width=max(1, h // 30))

    # Eyes
    eye_r = max(2, w // 12)
    eye_y = y + h // 3
    for eye_cx in (x + w // 3, x + 2 * w // 3):
        draw.ellipse([eye_cx - eye_r, eye_y - eye_r, eye_cx + eye_r, eye_y + eye_r], fill=(0, 0, 0))

    # Frown — arc from 180° to 360° traces the top half of the ellipse = downward curve
    mouth_pad = w // 4
    mouth_top = y + h // 2
    mouth_bot = y + 3 * h // 4
    draw.arc(
        [x + mouth_pad, mouth_top, x2 - mouth_pad, mouth_bot],
        start=180, end=360,
        fill=(0, 0, 0), width=max(1, h // 20),
    )

    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def _save_image(vid: str, jpeg_bytes: bytes) -> str:
    """Write JPEG bytes to disk and return the filename."""
    filename = f"{vid}.jpg"
    (IMAGES_DIR / filename).write_bytes(jpeg_bytes)
    return filename



# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def violations_ws(ws: WebSocket):
    await _manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep the connection alive; ignore client messages
    except WebSocketDisconnect:
        _manager.disconnect(ws)


@router.post("", status_code=201)
async def create_violation(payload: ViolationIn):
    vid = str(uuid.uuid4())
    jpeg_bytes = _apply_sad_emoji(payload.image, payload.blackbox)
    filename = _save_image(vid, jpeg_bytes)
    db = get_db()
    db.execute(
        "INSERT INTO violations (violationId, type, timestamp, image, blackbox, headbox) VALUES (?,?,?,?,?,?)",
        (vid, payload.type, payload.timestamp, filename,
         json.dumps(payload.blackbox), json.dumps(payload.headbox)),
    )
    db.commit()
    db.close()
    await _manager.broadcast({"violationId": vid, "type": payload.type, "timestamp": payload.timestamp})
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
def get_by_date(startdate: int = Query(...), enddate: int = Query(...), flagged: bool = Query(None), read: bool = Query(None)):
    db = get_db()
    filters = ["timestamp BETWEEN ? AND ?"]
    params: list = [startdate, enddate]
    if flagged is not None:
        filters.append("flagged=?")
        params.append(int(flagged))
    if read is not None:
        filters.append("read=?")
        params.append(int(read))
    rows = db.execute(
        f"SELECT * FROM violations WHERE {' AND '.join(filters)}", params
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
    if not r:
        db.close()
        raise HTTPException(404, "Violation not found")
    db.execute("UPDATE violations SET read=1 WHERE violationId=?", (violationId,))
    db.commit()
    db.close()
    return ViolationImage(
        violationId=r["violationId"],
        imageUrl=f"/violation_images/{r['image']}",
        blackbox=json.loads(r["blackbox"]),
        headbox=json.loads(r["headbox"]),
    )


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
