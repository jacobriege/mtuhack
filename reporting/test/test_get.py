import requests
import time

BASE = "http://localhost:5000/violations"

# --- create a violation first so there's something to query ---
import base64
from pathlib import Path

image_b64 = base64.b64encode(Path(__file__).parent.joinpath("obama.jpg").read_bytes()).decode()

resp = requests.post(BASE, json={
    "type": "no_hardhat",
    "timestamp": int(time.time()),
    "image": image_b64,
    "blackbox": [521, 225, 889, 987],
    "headbox": [20, 10, 80, 50],
})
resp.raise_for_status()
vid = resp.json()["violationId"]
print(f"Created violation: {vid}")

# --- GET /violations/unread ---
r = requests.get(f"{BASE}/unread")
print(f"\nUnread ({r.status_code}):", r.json())

# --- GET /violations/bydate ---
r = requests.get(f"{BASE}/bydate", params={"startdate": 1718500000, "enddate": 1719000000})
print(f"\nBy date ({r.status_code}):", r.json())

# --- GET /violations/bydate?flagged=false ---
r = requests.get(f"{BASE}/bydate", params={"startdate": 1718500000, "enddate": 1719000000, "flagged": "false"})
print(f"\nBy date unflagged ({r.status_code}):", r.json())

# --- GET /violations/count ---
r = requests.get(f"{BASE}/count")
print(f"\nCount ({r.status_code}):", r.json())

# --- GET /violations/instance/meta ---
r = requests.get(f"{BASE}/instance/meta", params={"violationId": vid})
print(f"\nMeta ({r.status_code}):", r.json())

# --- GET /violations/instance/image ---
r = requests.get(f"{BASE}/instance/image", params={"violationId": vid})
data = r.json()
image_url = data["imageUrl"]
print(f"\nImage ({r.status_code}): violationId={data['violationId']}, imageUrl={image_url}")
out_dir = Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)
out_path = out_dir / f"{vid}.jpg"
img_resp = requests.get(f"http://localhost:5000{image_url}")
img_resp.raise_for_status()
out_path.write_bytes(img_resp.content)
print(f"Saved image to {out_path}")

# --- GET /violations/instance/flag (toggle) ---
r = requests.get(f"{BASE}/instance/flag", params={"violationId": vid})
print(f"\nFlag ({r.status_code}):", r.json())
