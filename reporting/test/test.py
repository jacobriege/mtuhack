import base64
import requests
from pathlib import Path

image_b64 = base64.b64encode(Path(__file__).parent.joinpath("obama.jpg").read_bytes()).decode()

payload = {
    "type": "no_hardhat",
    "timestamp": 1718900000,
    "image": image_b64,
    "blackbox": [0, 0, 100, 100],
    "headbox": [20, 10, 80, 50],
}

resp = requests.post("http://localhost:8000/violations", json=payload)
print(resp.status_code, resp.json())
