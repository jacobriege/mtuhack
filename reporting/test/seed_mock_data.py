import base64
import random
import time
import requests
from pathlib import Path

image_b64 = base64.b64encode(Path(__file__).parent.joinpath("obama.jpg").read_bytes()).decode()

VIOLATION_TYPES = ["no_hardhat", "no_west", "emergency"]

now = int(time.time())
ONE_DAY = 86_400
ONE_WEEK = 7 * ONE_DAY


def random_boxes():
    x = random.randint(50, 400)
    y = random.randint(50, 300)
    w = random.randint(150, 500)
    h = random.randint(300, 700)
    blackbox = [x, y, w, h]
    headbox = [x + w // 4, y, w // 2, h // 5]
    return blackbox, headbox


events: list[tuple[int, str]] = []

for _ in range(6):
    events.append((now - random.randint(0, ONE_DAY - 1), random.choice(VIOLATION_TYPES)))

for _ in range(10):
    events.append((now - random.randint(ONE_DAY, ONE_WEEK), random.choice(VIOLATION_TYPES)))

random.shuffle(events)

print(f"Submitting {len(events)} violations...")

for i, (ts, vtype) in enumerate(events):
    blackbox, headbox = random_boxes()
    payload = {
        "type": vtype,
        "timestamp": ts,
        "image": image_b64,
        "blackbox": blackbox,
        "headbox": headbox,
    }
    resp = requests.post("http://localhost:5000/violations", json=payload)
    print(f"[{i + 1:>2}/{len(events)}] type={vtype:<12} ts={ts}  -> {resp.status_code} {resp.json()}")

print("Done.")
