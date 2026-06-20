from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from database import init_db, get_db
from models import ReportIn, ReportOut, ImageOut
from violations import router as violations_router
import shutil

IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Reporting Backend", lifespan=lifespan)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.include_router(violations_router)

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/reports", response_model=ReportOut, status_code=201)
def ingest_report(payload: ReportIn):
    """Ingest a JSON report from the robot/external service."""
    db = get_db()
    report_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO reports (id, robot_id, timestamp, data) VALUES (?, ?, ?, ?)",
        (report_id, payload.robot_id, payload.timestamp, payload.data.model_dump_json()),
    )
    db.commit()
    db.close()
    return ReportOut(id=report_id, robot_id=payload.robot_id, timestamp=payload.timestamp, data=payload.data)


@app.get("/reports", response_model=list[ReportOut])
def list_reports(robot_id: str | None = None):
    """Return all ingested reports, optionally filtered by robot_id."""
    db = get_db()
    if robot_id:
        rows = db.execute(
            "SELECT id, robot_id, timestamp, data FROM reports WHERE robot_id = ?", (robot_id,)
        ).fetchall()
    else:
        rows = db.execute("SELECT id, robot_id, timestamp, data FROM reports").fetchall()
    db.close()

    import json
    return [
        ReportOut(id=r["id"], robot_id=r["robot_id"], timestamp=r["timestamp"], data=json.loads(r["data"]))
        for r in rows
    ]


@app.post("/images", response_model=ImageOut, status_code=201)
def upload_image(file: UploadFile = File(...)):
    """Upload an image captured by the robot; returns the assigned image ID."""
    suffix = Path(file.filename).suffix if file.filename else ".bin"
    image_id = str(uuid.uuid4())
    dest = IMAGES_DIR / f"{image_id}{suffix}"

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    db = get_db()
    db.execute(
        "INSERT INTO images (id, filename) VALUES (?, ?)",
        (image_id, dest.name),
    )
    db.commit()
    db.close()
    return ImageOut(id=image_id, filename=dest.name, url=f"/images/{dest.name}")


@app.get("/images", response_model=list[ImageOut])
def list_images():
    """Return all stored image IDs and their URLs."""
    db = get_db()
    rows = db.execute("SELECT id, filename FROM images").fetchall()
    db.close()
    return [ImageOut(id=r["id"], filename=r["filename"], url=f"/images/{r['filename']}") for r in rows]


@app.get("/images/{image_id}", response_model=ImageOut)
def get_image(image_id: str):
    """Return metadata for a single image by its ID."""
    db = get_db()
    row = db.execute("SELECT id, filename FROM images WHERE id = ?", (image_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")
    return ImageOut(id=row["id"], filename=row["filename"], url=f"/images/{row['filename']}")
